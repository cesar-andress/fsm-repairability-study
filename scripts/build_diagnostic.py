#!/usr/bin/env python3
"""
Convert a score_repair.py score report into a diagnostic artefact (v2.0.0).

See docs/diagnostic_generation.md.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMAS_DIR = REPO_ROOT / "schemas"
DIAGNOSTIC_SCHEMA_VERSION = "2.0.0"
VALID_LEVELS = frozenset({"binary", "trace", "localized"})
DEFAULT_FSM_PATH = "unknown_fsm.json"
DEFAULT_SUITE_PATH = "unknown_suite.json"

try:
    import jsonschema
    from jsonschema import Draft202012Validator
except ImportError:  # pragma: no cover
    jsonschema = None  # type: ignore
    Draft202012Validator = None  # type: ignore


class DiagnosticBuildError(Exception):
    """Raised when projection or validation fails."""


def _require_jsonschema() -> None:
    if jsonschema is None or Draft202012Validator is None:
        raise DiagnosticBuildError(
            "jsonschema is required. Install with: "
            "pip install -r environment/requirements.txt"
        )


def _schema_registry():
    _require_jsonschema()
    from referencing import Registry, Resource

    registry: Registry = Registry()
    for path in sorted(SCHEMAS_DIR.glob("*.json")):
        with path.open(encoding="utf-8") as f:
            registry = registry.with_resource(
                path.name, Resource.from_contents(json.load(f))
            )
    return registry


def load_score_report(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise DiagnosticBuildError(f"score report not found: {path}")
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        raise DiagnosticBuildError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise DiagnosticBuildError(f"score report must be a JSON object: {path}")
    return data


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_path(raw: str | None, bases: list[Path]) -> Path | None:
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


def _relative_path(raw: str | None, default: str) -> str:
    if not raw:
        return default
    normalized = str(raw).replace("\\", "/")
    if normalized.startswith("/"):
        normalized = Path(normalized).name
    if re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_./-]*\.[a-zA-Z0-9]+", normalized):
        return normalized
    return default


def _slug_from_path(path_value: str) -> str:
    stem = Path(path_value).stem.lower().replace("-", "_")
    stem = re.sub(r"[^a-z0-9_]", "_", stem)
    stem = re.sub(r"_+", "_", stem).strip("_")
    if not stem or not stem[0].isalpha():
        stem = f"s_{stem}" if stem else "unknown_suite"
    return stem[:128]


def _oracle_suite_id(report: dict[str, Any]) -> str:
    explicit = report.get("oracle_suite_id")
    if isinstance(explicit, str) and re.fullmatch(r"[a-z][a-z0-9_]*", explicit):
        return explicit
    suite_id = report.get("suite_id")
    if isinstance(suite_id, str) and re.fullmatch(r"[a-z][a-z0-9_]*", suite_id):
        return suite_id
    suite_path = report.get("oracle_suite_path")
    if isinstance(suite_path, str) and suite_path:
        return _slug_from_path(suite_path)
    return "unknown_suite"


def diagnostic_id(case_id: str, run_id: str, iteration_index: int, level: str) -> str:
    return f"diag_{case_id}_{run_id}_i{iteration_index}_{level}"


def _compute_bpr(passed_tests: int, total_tests: int) -> float:
    if total_tests <= 0:
        return 1.0
    return passed_tests / total_tests


def _load_test_types(suite_path: str | None, bases: list[Path]) -> dict[str, str]:
    resolved = _resolve_path(suite_path, bases)
    if resolved is None:
        return {}
    with resolved.open(encoding="utf-8") as f:
        suite = json.load(f)
    mapping: dict[str, str] = {}
    for test in suite.get("tests", suite.get("checks", [])):
        tid = test.get("test_id", test.get("check_id"))
        if tid and test.get("type"):
            mapping[tid] = test["type"]
    return mapping


def _oracle_type(failure: dict[str, Any], test_types: dict[str, str]) -> str:
    tid = failure.get("test_id", "")
    if tid in test_types:
        return test_types[tid]
    ft = failure.get("failure_type", "")
    if ft in ("unexpected_transition", "unexpected_acceptance", "unexpected_rejection"):
        return "rejected_event"
    if ft == "final_state_mismatch":
        return "final_state"
    if ft in ("trace_mismatch", "undefined_transition"):
        return "trace"
    return "unknown"


def _failure_categories(failures: list[dict[str, Any]]) -> dict[str, int]:
    final_state = trace = rejection = simulation = nondeterminism = 0
    for failure in failures:
        ft = failure.get("failure_type", "")
        if ft == "final_state_mismatch":
            final_state += 1
        elif ft == "trace_mismatch":
            trace += 1
        elif ft in ("unexpected_acceptance", "unexpected_rejection"):
            rejection += 1
        elif ft == "simulation_error":
            simulation += 1
        elif ft == "nondeterminism":
            nondeterminism += 1
    return {
        "positive_path_failures": final_state + trace,
        "rejection_failures": rejection,
        "final_state_failures": final_state,
        "trace_failures": trace,
        "nondeterminism_failures": nondeterminism,
        "simulation_failures": simulation,
    }


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
    hint = failure.get("diagnostic_hint") or ""
    if level == "binary":
        if hint:
            entry["diagnostic_hint"] = hint
        return entry

    trace_obj = failure.get("trace") or {}
    input_trace: dict[str, Any] = {}
    if trace_obj.get("events") is not None:
        input_trace["events"] = trace_obj["events"]
    if trace_obj.get("from_state") is not None:
        input_trace["from_state"] = trace_obj["from_state"]
    if input_trace:
        entry["input_trace"] = input_trace
    if "expected" in failure:
        entry["expected"] = failure["expected"]
    if "observed" in failure:
        entry["observed"] = failure["observed"]

    expected = failure.get("expected") or {}
    observed = failure.get("observed") or {}
    if "final_state" in expected or oracle_type == "final_state":
        entry["expected_final_state"] = expected.get("final_state")
        entry["observed_final_state"] = observed.get("final_state")
    elif expected.get("states"):
        entry["expected_final_state"] = expected["states"][-1]
        obs_states = observed.get("states") or []
        entry["observed_final_state"] = obs_states[-1] if obs_states else None
    else:
        entry["expected_final_state"] = None
        entry["observed_final_state"] = None

    if hint:
        entry["diagnostic_hint"] = hint
    return entry


def _localization_block(report: dict[str, Any]) -> dict[str, list[Any]]:
    raw = report.get("localization")
    if not isinstance(raw, dict):
        return {
            "suspicious_states": [],
            "suspicious_transitions": [],
            "missing_transition_candidates": [],
            "extra_transition_candidates": [],
        }
    return {
        "suspicious_states": list(raw.get("suspicious_states") or []),
        "suspicious_transitions": list(raw.get("suspicious_transitions") or []),
        "missing_transition_candidates": list(
            raw.get("missing_transition_candidates") or []
        ),
        "extra_transition_candidates": list(raw.get("extra_transition_candidates") or []),
    }


def validate_diagnostic(doc: dict[str, Any]) -> None:
    _require_jsonschema()
    with (SCHEMAS_DIR / "diagnostic.schema.json").open(encoding="utf-8") as f:
        schema = json.load(f)
    validator = Draft202012Validator(schema, registry=_schema_registry())
    errors = sorted(validator.iter_errors(doc), key=lambda e: e.path)
    if errors:
        err = errors[0]
        loc = "/".join(str(p) for p in err.absolute_path)
        msg = f" at {loc}" if loc else ""
        raise DiagnosticBuildError(
            f"diagnostic does not match schema{msg}: {err.message}"
        )


def build_diagnostic(
    report: dict[str, Any],
    level: str,
    *,
    case_id: str,
    run_id: str,
    iteration_index: int,
    generated_at: str | None = None,
    score_report_path: Path | None = None,
    path_bases: list[Path] | None = None,
) -> dict[str, Any]:
    if level not in VALID_LEVELS:
        raise DiagnosticBuildError(
            f"invalid level {level!r}; expected binary, trace, or localized"
        )
    if iteration_index < 0:
        raise DiagnosticBuildError(f"iteration_index must be >= 0, got {iteration_index}")

    bases = list(path_bases or [REPO_ROOT])
    total = int(report.get("total_tests", 0))
    passed = int(report.get("passed_tests", 0))
    failed = int(report.get("failed_tests", max(0, total - passed)))
    failures = list(report.get("failures") or [])
    test_types = _load_test_types(report.get("oracle_suite_path"), bases)

    checksums: dict[str, str] = {}
    if score_report_path and score_report_path.is_file():
        checksums["score_report_sha256"] = _sha256_file(score_report_path)
    else:
        checksums["score_report_sha256"] = _sha256_bytes(
            json.dumps(report, sort_keys=True, separators=(",", ":")).encode("utf-8")
        )

    fsm_resolved = _resolve_path(report.get("fsm_path"), bases)
    if fsm_resolved is not None:
        checksums["source_fsm_sha256"] = _sha256_file(fsm_resolved)
    suite_resolved = _resolve_path(report.get("oracle_suite_path"), bases)
    if suite_resolved is not None:
        checksums["oracle_suite_sha256"] = _sha256_file(suite_resolved)

    diagnostic: dict[str, Any] = {
        "identity": {
            "diagnostic_id": diagnostic_id(case_id, run_id, iteration_index, level),
            "schema_version": DIAGNOSTIC_SCHEMA_VERSION,
            "case_id": case_id,
            "run_id": run_id,
            "iteration_index": iteration_index,
            "diagnostic_level": level,
        },
        "scoring_summary": {
            "oracle_suite_id": _oracle_suite_id(report),
            "total_checks": total,
            "passed_checks": passed,
            "failed_checks": failed,
            "bpr": _compute_bpr(passed, total),
        },
        "failure_categories": _failure_categories(failures),
        "failed_checks": [
            _project_failed_check(f, level, _oracle_type(f, test_types))
            for f in failures
        ],
        "reproducibility": {
            "source_fsm_path": _relative_path(report.get("fsm_path"), DEFAULT_FSM_PATH),
            "oracle_suite_path": _relative_path(
                report.get("oracle_suite_path"), DEFAULT_SUITE_PATH
            ),
            "scorer_version": str(report.get("score_schema_version", "1.0.0")),
            "generated_at": generated_at
            or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "checksums": checksums,
        },
    }

    if level == "localized":
        diagnostic["localization"] = _localization_block(report)

    validate_diagnostic(diagnostic)
    return diagnostic


def write_diagnostic(doc: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--score-report", required=True, type=Path)
    parser.add_argument("--level", required=True, choices=sorted(VALID_LEVELS))
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--iteration-index", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    try:
        report = load_score_report(args.score_report)
        bases = [args.score_report.resolve().parent, REPO_ROOT]
        doc = build_diagnostic(
            report,
            args.level,
            case_id=args.case_id,
            run_id=args.run_id,
            iteration_index=args.iteration_index,
            score_report_path=args.score_report.resolve(),
            path_bases=bases,
        )
        write_diagnostic(doc, args.output)
    except DiagnosticBuildError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(doc, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
