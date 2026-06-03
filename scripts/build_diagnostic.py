#!/usr/bin/env python3
"""
Project a deterministic score report into a repair feedback diagnostic artefact.

See docs/diagnostic_generation.md and docs/diagnostic_model.md.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMAS_DIR = REPO_ROOT / "schemas"

DIAGNOSTIC_SCHEMA_VERSION = "2.0.0"
VALID_LEVELS = frozenset({"binary", "trace", "localized"})

SIMULATION_FAILURE_TYPES = frozenset(
    {
        "simulation_error",
        "fsm_integrity_error",
        "undefined_transition",
        "invalid_check_spec",
        "unsupported_check_type",
    }
)

try:
    import jsonschema
    from jsonschema import Draft202012Validator
except ImportError:  # pragma: no cover
    jsonschema = None  # type: ignore
    Draft202012Validator = None  # type: ignore


class DiagnosticBuildError(Exception):
    """Raised when projection inputs or output validation fail."""


def _schema_registry():
    if jsonschema is None:
        return None
    from referencing import Registry, Resource

    registry: Registry = Registry()
    for path in sorted(SCHEMAS_DIR.glob("*.json")):
        with path.open(encoding="utf-8") as f:
            contents = json.load(f)
        registry = registry.with_resource(path.name, Resource.from_contents(contents))
    return registry


def load_score_report(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise DiagnosticBuildError(f"score report not found: {path}")
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        raise DiagnosticBuildError(f"invalid JSON in score report {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise DiagnosticBuildError(f"score report must be a JSON object: {path}")
    return data


def _resolve_existing_path(
    raw: str | None,
    bases: list[Path],
) -> Path | None:
    if not raw:
        return None
    candidate = Path(raw)
    if candidate.is_file():
        return candidate.resolve()
    for base in bases:
        joined = (base / candidate).resolve()
        if joined.is_file():
            return joined
    return None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _compute_bpr(passed_tests: int, total_tests: int) -> float:
    if total_tests <= 0:
        return 1.0
    return passed_tests / total_tests


def _load_test_types(oracle_suite_path: str | None, bases: list[Path]) -> dict[str, str]:
    resolved = _resolve_existing_path(oracle_suite_path, bases)
    if resolved is None:
        return {}
    try:
        with resolved.open(encoding="utf-8") as f:
            suite = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        raise DiagnosticBuildError(
            f"cannot read oracle suite for check types: {resolved}: {exc}"
        ) from exc
    tests = suite.get("tests", suite.get("checks", []))
    mapping: dict[str, str] = {}
    for test in tests:
        tid = test.get("test_id", test.get("check_id"))
        ttype = test.get("type")
        if tid and ttype:
            mapping[tid] = ttype
    return mapping


def _infer_oracle_type(failure: dict[str, Any], test_types: dict[str, str]) -> str:
    test_id = failure.get("test_id", "")
    if test_id in test_types:
        return test_types[test_id]
    failure_type = failure.get("failure_type", "")
    if failure_type == "unexpected_transition":
        return "rejected_event"
    if failure_type == "final_state_mismatch":
        return "final_state"
    if failure_type in ("trace_mismatch", "undefined_transition"):
        return "trace"
    if failure_type == "fsm_integrity_error":
        return "unknown"
    return "unknown"


def _failure_categories(
    failures: list[dict[str, Any]],
    oracle_types: list[str],
) -> dict[str, int]:
    categories = {
        "positive_path_failures": 0,
        "rejection_failures": 0,
        "final_state_failures": 0,
        "trace_failures": 0,
        "nondeterminism_failures": 0,
        "simulation_failures": 0,
    }
    for failure, oracle_type in zip(failures, oracle_types, strict=True):
        failure_type = failure.get("failure_type", "other")
        if oracle_type in ("trace", "final_state"):
            categories["positive_path_failures"] += 1
        if oracle_type == "rejected_event":
            categories["rejection_failures"] += 1
        if failure_type == "final_state_mismatch":
            categories["final_state_failures"] += 1
        if failure_type == "trace_mismatch":
            categories["trace_failures"] += 1
        if failure_type == "nondeterminism_conflict":
            categories["nondeterminism_failures"] += 1
        if failure_type in SIMULATION_FAILURE_TYPES:
            categories["simulation_failures"] += 1
    return categories


def _project_failed_check(
    failure: dict[str, Any],
    level: str,
    oracle_type: str,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "check_id": failure["test_id"],
        "oracle_type": oracle_type,
        "failure_type": failure["failure_type"],
    }
    if level == "binary":
        return entry

    trace = failure.get("trace") or {}
    input_trace: dict[str, Any] = {}
    if trace.get("events") is not None:
        input_trace["events"] = trace["events"]
    if trace.get("from_state") is not None:
        input_trace["from_state"] = trace["from_state"]
    if input_trace:
        entry["input_trace"] = input_trace

    if "expected" in failure:
        entry["expected"] = failure["expected"]
    if "observed" in failure:
        entry["observed"] = failure["observed"]

    expected = failure.get("expected") or {}
    observed = failure.get("observed") or {}
    if oracle_type == "final_state" or "final_state" in expected:
        entry["expected_final_state"] = expected.get("final_state")
        entry["observed_final_state"] = observed.get("final_state")
    elif expected.get("states") is not None:
        states = expected["states"]
        obs_states = observed.get("states") or []
        entry["expected_final_state"] = states[-1] if states else None
        entry["observed_final_state"] = obs_states[-1] if obs_states else None
    else:
        entry["expected_final_state"] = None
        entry["observed_final_state"] = None

    hint = failure.get("diagnostic_hint", "")
    if hint:
        entry["diagnostic_hint"] = hint
    return entry


def _empty_localization() -> dict[str, list[Any]]:
    return {
        "suspicious_states": [],
        "suspicious_transitions": [],
        "missing_transition_candidates": [],
        "extra_transition_candidates": [],
    }


def _project_localization(score_report: dict[str, Any]) -> dict[str, list[Any]]:
    raw = score_report.get("localization")
    if not isinstance(raw, dict):
        return _empty_localization()
    return {
        "suspicious_states": list(raw.get("suspicious_states") or []),
        "suspicious_transitions": list(raw.get("suspicious_transitions") or []),
        "missing_transition_candidates": list(
            raw.get("missing_transition_candidates") or []
        ),
        "extra_transition_candidates": list(raw.get("extra_transition_candidates") or []),
    }


def _reproducibility_block(
    score_report: dict[str, Any],
    *,
    generated_at: str,
    bases: list[Path],
) -> dict[str, Any]:
    fsm_raw = score_report.get("fsm_path") or "unknown_fsm.json"
    suite_raw = score_report.get("oracle_suite_path") or "unknown_suite.json"
    fsm_resolved = _resolve_existing_path(str(fsm_raw), bases)
    suite_resolved = _resolve_existing_path(str(suite_raw), bases)

    if fsm_resolved is None:
        raise DiagnosticBuildError(
            f"cannot compute checksum: FSM path not found: {fsm_raw!r} "
            f"(searched under {[str(b) for b in bases]})"
        )
    if suite_resolved is None:
        raise DiagnosticBuildError(
            f"cannot compute checksum: oracle suite path not found: {suite_raw!r} "
            f"(searched under {[str(b) for b in bases]})"
        )

    return {
        "source_fsm_path": str(fsm_raw),
        "oracle_suite_path": str(suite_raw),
        "scorer_version": str(score_report.get("score_schema_version", "1.0.0")),
        "generated_at": generated_at,
        "checksums": {
            "source_fsm_sha256": _sha256_file(fsm_resolved),
            "oracle_suite_sha256": _sha256_file(suite_resolved),
        },
    }


def validate_diagnostic_document(doc: dict[str, Any]) -> None:
    if jsonschema is None or Draft202012Validator is None:
        return
    schema_path = SCHEMAS_DIR / "diagnostic.schema.json"
    with schema_path.open(encoding="utf-8") as f:
        schema = json.load(f)
    registry = _schema_registry()
    validator = Draft202012Validator(schema, registry=registry)
    errors = sorted(validator.iter_errors(doc), key=lambda e: e.path)
    if errors:
        detail = errors[0].message
        path = "/".join(str(p) for p in errors[0].absolute_path)
        if path:
            raise DiagnosticBuildError(
                f"diagnostic JSON does not match schema at {path}: {detail}"
            )
        raise DiagnosticBuildError(f"diagnostic JSON does not match schema: {detail}")


def build_diagnostic(
    score_report: dict[str, Any],
    level: str,
    *,
    case_id: str,
    run_id: str,
    iteration_index: int,
    generated_at: str | None = None,
    path_resolution_bases: list[Path] | None = None,
    validate: bool = True,
) -> dict[str, Any]:
    """
    Project one score report to a diagnostic artefact without mutating the report.
    """
    if level not in VALID_LEVELS:
        raise DiagnosticBuildError(
            f"invalid diagnostic level {level!r}; expected one of: "
            + ", ".join(sorted(VALID_LEVELS))
        )

    if iteration_index < 0:
        raise DiagnosticBuildError(
            f"iteration_index must be >= 0, got {iteration_index}"
        )

    bases = list(path_resolution_bases or [REPO_ROOT])
    if REPO_ROOT not in bases:
        bases.append(REPO_ROOT)

    total = int(score_report.get("total_tests", 0))
    passed = int(score_report.get("passed_tests", 0))
    failed = int(score_report.get("failed_tests", max(0, total - passed)))
    bpr = _compute_bpr(passed, total)

    failures = list(score_report.get("failures") or [])
    test_types = _load_test_types(score_report.get("oracle_suite_path"), bases)
    oracle_types = [_infer_oracle_type(f, test_types) for f in failures]

    diagnostic: dict[str, Any] = {
        "identity": {
            "diagnostic_id": f"{case_id}__{run_id}__iter{iteration_index:02d}",
            "schema_version": DIAGNOSTIC_SCHEMA_VERSION,
            "case_id": case_id,
            "run_id": run_id,
            "iteration_index": iteration_index,
            "diagnostic_level": level,
        },
        "scoring_summary": {
            "oracle_suite_id": score_report.get("suite_id") or "unknown_suite",
            "total_checks": total,
            "passed_checks": passed,
            "failed_checks": failed,
            "bpr": bpr,
        },
        "failure_categories": _failure_categories(failures, oracle_types),
        "failed_checks": [
            _project_failed_check(f, level, ot)
            for f, ot in zip(failures, oracle_types, strict=True)
        ],
        "reproducibility": _reproducibility_block(
            score_report,
            generated_at=generated_at
            or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            bases=bases,
        ),
    }

    if level == "localized":
        diagnostic["localization"] = _project_localization(score_report)

    if validate:
        validate_diagnostic_document(diagnostic)

    return diagnostic


def write_diagnostic(diagnostic: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(diagnostic, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--score-report",
        required=True,
        type=Path,
        help="Input score report JSON from score_repair.py",
    )
    parser.add_argument(
        "--level",
        required=True,
        choices=sorted(VALID_LEVELS),
        help="Diagnostic projection level: binary, trace, or localized",
    )
    parser.add_argument("--case-id", required=True, help="Repair case identifier")
    parser.add_argument("--run-id", required=True, help="Repair run identifier")
    parser.add_argument(
        "--iteration-index",
        required=True,
        type=int,
        help="Zero-based repair iteration index",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Output diagnostic JSON path",
    )
    parser.add_argument(
        "--no-schema-check",
        action="store_true",
        help="Skip jsonschema validation of the output",
    )
    args = parser.parse_args(argv)

    try:
        report = load_score_report(args.score_report)
        bases = [args.score_report.resolve().parent, REPO_ROOT]
        diagnostic = build_diagnostic(
            report,
            args.level,
            case_id=args.case_id,
            run_id=args.run_id,
            iteration_index=args.iteration_index,
            path_resolution_bases=bases,
            validate=not args.no_schema_check,
        )
        write_diagnostic(diagnostic, args.output)
    except DiagnosticBuildError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(diagnostic, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
