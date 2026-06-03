#!/usr/bin/env python3
"""
Dry-run repair condition orchestrator (no LLM / no Ollama).

Validates the experimental loop shape:
  FSM -> score -> diagnostic -> patch -> apply -> score -> repair_run

See docs/repair_condition_runner.md.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMAS_DIR = REPO_ROOT / "schemas"
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from apply_patch import (  # noqa: E402
    PatchEngineError,
    apply_patch,
    load_fsm,
    load_patch,
    validate_patch_document,
    write_fsm,
)
from build_diagnostic import (  # noqa: E402
    DiagnosticBuildError,
    build_diagnostic,
    write_diagnostic,
)
from score_repair import score_fsm, write_report  # noqa: E402

REPAIR_RUN_SCHEMA_VERSION = "2.0.0"
SUPPORTED_CONDITIONS = frozenset(
    {
        "baseline_no_repair",
        "patch_binary_feedback",
        "patch_trace_feedback",
        "patch_localized_feedback",
    }
)
CONDITION_TO_DIAGNOSTIC_LEVEL = {
    "patch_binary_feedback": "binary",
    "patch_trace_feedback": "trace",
    "patch_localized_feedback": "localized",
}

try:
    import jsonschema
    from jsonschema import Draft202012Validator
except ImportError:  # pragma: no cover
    jsonschema = None  # type: ignore
    Draft202012Validator = None  # type: ignore


class RunnerError(Exception):
    """Raised when dry-run orchestration fails."""


def _require_jsonschema() -> None:
    if jsonschema is None or Draft202012Validator is None:
        raise RunnerError(
            "jsonschema is required. Install with: "
            "pip install -r environment/requirements.txt"
        )


def _schema_registry():
    _require_jsonschema()
    from referencing import Registry, Resource

    registry: Registry = Registry()
    for path in sorted(SCHEMAS_DIR.glob("*.json")):
        with path.open(encoding="utf-8") as f:
            registry = registry.with_resource(path.name, Resource.from_contents(json.load(f)))
    return registry


def validate_repair_run(doc: dict[str, Any]) -> None:
    _require_jsonschema()
    with (SCHEMAS_DIR / "repair_run.schema.json").open(encoding="utf-8") as f:
        schema = json.load(f)
    validator = Draft202012Validator(schema, registry=_schema_registry())
    errors = sorted(validator.iter_errors(doc), key=lambda e: e.path)
    if errors:
        err = errors[0]
        loc = "/".join(str(p) for p in err.absolute_path)
        raise RunnerError(f"repair_run invalid{(' at ' + loc) if loc else ''}: {err.message}")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _checksum_map(entries: list[tuple[str, Path]]) -> dict[str, str]:
    """Build a named SHA-256 map for existing files (schema requires minProperties: 1)."""
    result: dict[str, str] = {}
    for name, path in entries:
        if path.is_file():
            result[name] = _sha256_file(path)
    if not result:
        raise RunnerError("no output artifacts available for output_checksums")
    return result


def _rel(path: Path, base: Path) -> str:
    try:
        return str(path.resolve().relative_to(base.resolve())).replace("\\", "/")
    except ValueError:
        return path.name


def load_case_bundle(case_dir: Path) -> dict[str, Any]:
    case_path = case_dir / "case.json"
    if not case_path.is_file():
        raise RunnerError(f"case.json not found in {case_dir}")
    with case_path.open(encoding="utf-8") as f:
        case = json.load(f)
    if not isinstance(case, dict):
        raise RunnerError("case.json must be a JSON object")
    return case


def resolve_fsm(case_dir: Path, ref: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(ref, dict):
        return copy.deepcopy(ref)
    path = case_dir / ref
    if not path.is_file():
        raise RunnerError(f"FSM file not found: {path}")
    return load_fsm(path)


def resolve_oracle_suite(case_dir: Path, binding: dict[str, Any]) -> tuple[dict[str, Any], Path]:
    if "suite_path" in binding:
        path = case_dir / binding["suite_path"]
    else:
        suite_id = binding.get("suite_id", "oracle_suite")
        path = case_dir / f"{suite_id}.json"
        if not path.is_file():
            path = REPO_ROOT / "datasets" / "oracle_suites" / f"{suite_id}.json"
    if not path.is_file():
        raise RunnerError(f"oracle suite not found for binding: {binding}")
    with path.open(encoding="utf-8") as f:
        return json.load(f), path


def _score_and_write(
    fsm: dict[str, Any],
    suite: dict[str, Any],
    *,
    fsm_path: Path,
    suite_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    report = score_fsm(
        fsm,
        suite,
        fsm_path=str(fsm_path),
        oracle_suite_path=str(suite_path),
    )
    write_report(report, output_path)
    return report


VALID_EXECUTION_BACKENDS = frozenset({"none", "ollama", "other"})


def _build_execution_block(
    condition: str,
    *,
    started: str,
    completed: str,
    max_iterations: int,
    execution_backend: str | None = None,
    model_name: str | None = None,
    model_digest: str | None = None,
    temperature: float | None = None,
    seed: int | None = None,
) -> dict[str, Any]:
    """Assemble execution metadata; baseline A always uses backend none."""
    if condition == "baseline_no_repair":
        return {
            "repair_condition": condition,
            "model_name": None,
            "model_digest": None,
            "execution_backend": "none",
            "started_at": started,
            "completed_at": completed,
            "max_iterations": 0,
            "temperature": 0.0,
            "seed": None,
        }

    backend = execution_backend or "none"
    if backend not in VALID_EXECUTION_BACKENDS:
        raise RunnerError(
            f"invalid execution_backend {backend!r}; "
            f"expected one of: {', '.join(sorted(VALID_EXECUTION_BACKENDS))}"
        )

    return {
        "repair_condition": condition,
        "model_name": model_name,
        "model_digest": model_digest,
        "execution_backend": backend,
        "started_at": started,
        "completed_at": completed,
        "max_iterations": max_iterations,
        "temperature": 0.0 if temperature is None else temperature,
        "seed": seed,
    }


def _outcome_class(
    initial_validation_bpr: float,
    final_validation_bpr: float,
    *,
    patch_applied: bool,
) -> str:
    if final_validation_bpr >= 1.0:
        return "complete_repair"
    if patch_applied and final_validation_bpr > initial_validation_bpr:
        return "effective_repair"
    if patch_applied and final_validation_bpr < initial_validation_bpr:
        return "behavioural_degradation"
    if not patch_applied and final_validation_bpr == initial_validation_bpr:
        return "no_improvement"
    return "no_improvement"


def run_dry_repair_condition(
    *,
    case_dir: Path,
    condition: str,
    work_dir: Path,
    patch_source: Path | None = None,
    run_id: str | None = None,
    started_at: str | None = None,
    completed_at: str | None = None,
    execution_backend: str | None = None,
    model_name: str | None = None,
    model_digest: str | None = None,
    temperature: float | None = None,
    seed: int | None = None,
) -> dict[str, Any]:
    if condition not in SUPPORTED_CONDITIONS:
        raise RunnerError(
            f"unsupported condition {condition!r}; expected one of: "
            + ", ".join(sorted(SUPPORTED_CONDITIONS))
        )
    if condition != "baseline_no_repair" and patch_source is None:
        raise RunnerError(f"--patch-source is required for condition {condition}")
    if condition == "baseline_no_repair" and patch_source is not None:
        raise RunnerError("baseline_no_repair does not accept --patch-source")

    case_dir = case_dir.resolve()
    work_dir = work_dir.resolve()
    work_dir.mkdir(parents=True, exist_ok=True)

    case = load_case_bundle(case_dir)
    case_snapshot = copy.deepcopy(case)
    identity = case["identity"]
    case_id = identity["case_id"]
    system_id = identity["system_id"]
    run_id = run_id or f"{case_id}__{condition}__dry001"

    started = started_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    completed = completed_at or started

    shutil.copy2(case_dir / "case.json", work_dir / "case.json")
    feedback_binding = case["oracles"]["feedback_oracles"]
    validation_binding = case["oracles"]["validation_oracles"]
    feedback_suite, feedback_suite_path = resolve_oracle_suite(case_dir, feedback_binding)
    validation_suite, validation_suite_path = resolve_oracle_suite(
        case_dir, validation_binding
    )

    candidate = resolve_fsm(case_dir, case["inputs"]["candidate_fsm"])
    candidates_dir = work_dir / "candidates"
    candidates_dir.mkdir(exist_ok=True)
    initial_path = candidates_dir / "initial.json"
    write_fsm(candidate, initial_path)

    scores_dir = work_dir / "scores"
    diagnostics_dir = work_dir / "diagnostics"
    patches_dir = work_dir / "patches"
    for d in (scores_dir, diagnostics_dir, patches_dir):
        d.mkdir(exist_ok=True)

    score_initial_fb = scores_dir / "iter_000_input_feedback.json"
    score_initial_val = scores_dir / "iter_000_input_validation.json"
    report_init_fb = _score_and_write(
        candidate,
        feedback_suite,
        fsm_path=initial_path,
        suite_path=feedback_suite_path,
        output_path=score_initial_fb,
    )
    report_init_val = _score_and_write(
        candidate,
        validation_suite,
        fsm_path=initial_path,
        suite_path=validation_suite_path,
        output_path=score_initial_val,
    )
    input_bpr_feedback = report_init_fb["bpr"]
    input_bpr_validation = report_init_val["bpr"]

    iterations: list[dict[str, Any]] = []
    oracle_executions = 2
    patch_ops_total = 0
    final_candidate_path = initial_path
    final_bpr_feedback = input_bpr_feedback
    final_bpr_validation = input_bpr_validation
    regression_any = False
    overfitting_any = False
    patch_applied = False

    if condition != "baseline_no_repair":
        level = CONDITION_TO_DIAGNOSTIC_LEVEL[condition]
        diag_path = diagnostics_dir / "iter_000_feedback.json"
        diagnostic = build_diagnostic(
            report_init_fb,
            level,
            case_id=case_id,
            run_id=run_id,
            iteration_index=0,
            generated_at=started,
            score_report_path=score_initial_fb,
            path_bases=[work_dir, case_dir, REPO_ROOT],
        )
        write_diagnostic(diagnostic, diag_path)

        patch_path = patches_dir / "iter_000_source.json"
        shutil.copy2(patch_source, patch_path)
        patch_doc = load_patch(patch_path, validate_schema=True)
        validate_patch_document(patch_doc)
        patch_valid = True
        patch_ops = len(patch_doc.get("operations", []))

        output_path = candidates_dir / "iter_001.json"
        try:
            repaired = apply_patch(candidate, patch_doc)
            write_fsm(repaired, output_path)
            patch_applied = True
            patch_ops_total = patch_ops
        except PatchEngineError as exc:
            raise RunnerError(f"patch application failed: {exc}") from exc

        score_out_fb = scores_dir / "iter_001_feedback.json"
        score_out_val = scores_dir / "iter_001_validation.json"
        report_out_fb = _score_and_write(
            repaired,
            feedback_suite,
            fsm_path=output_path,
            suite_path=feedback_suite_path,
            output_path=score_out_fb,
        )
        report_out_val = _score_and_write(
            repaired,
            validation_suite,
            fsm_path=output_path,
            suite_path=validation_suite_path,
            output_path=score_out_val,
        )
        oracle_executions += 2

        output_bpr_feedback = report_out_fb["bpr"]
        output_bpr_validation = report_out_val["bpr"]
        regression = output_bpr_validation < input_bpr_validation
        overfitting = (
            output_bpr_feedback > input_bpr_feedback
            and output_bpr_validation <= input_bpr_validation
        )
        regression_any = regression
        overfitting_any = overfitting

        iterations.append(
            {
                "iteration_index": 0,
                "input_candidate_path": _rel(initial_path, work_dir),
                "input_bpr_feedback": input_bpr_feedback,
                "input_bpr_validation": input_bpr_validation,
                "feedback_summary_path": _rel(diag_path, work_dir),
                "generated_patch_path": _rel(patch_path, work_dir),
                "patch_valid": patch_valid,
                "patch_applied": patch_applied,
                "output_candidate_path": _rel(output_path, work_dir),
                "output_bpr_feedback": output_bpr_feedback,
                "output_bpr_validation": output_bpr_validation,
                "regression_detected": regression,
                "overfitting_detected": overfitting,
                "error_type": "none",
                "error_message": "",
                "patch_operation_count": patch_ops_total,
            }
        )

        final_candidate_path = output_path
        final_bpr_feedback = output_bpr_feedback
        final_bpr_validation = output_bpr_validation

    max_iterations = 0 if condition == "baseline_no_repair" else 1
    outcome_class = _outcome_class(
        input_bpr_validation,
        final_bpr_validation,
        patch_applied=patch_applied,
    )

    output_checksum_entries: list[tuple[str, Path]] = [
        (_rel(final_candidate_path, work_dir), final_candidate_path),
        (_rel(score_initial_fb, work_dir), score_initial_fb),
        (_rel(score_initial_val, work_dir), score_initial_val),
    ]
    if condition != "baseline_no_repair":
        output_checksum_entries.extend(
            [
                (_rel(diag_path, work_dir), diag_path),
                (_rel(patch_path, work_dir), patch_path),
                (_rel(score_out_fb, work_dir), score_out_fb),
                (_rel(score_out_val, work_dir), score_out_val),
            ]
        )

    repair_run: dict[str, Any] = {
        "schema_version": REPAIR_RUN_SCHEMA_VERSION,
        "identity": {
            "run_id": run_id,
            "case_id": case_id,
            "system_id": system_id,
        },
        "execution": _build_execution_block(
            condition,
            started=started,
            completed=completed,
            max_iterations=max_iterations,
            execution_backend=execution_backend,
            model_name=model_name,
            model_digest=model_digest,
            temperature=temperature,
            seed=seed,
        ),
        "inputs": {
            "input_case_path": "case.json",
            "initial_candidate_path": _rel(initial_path, work_dir),
            "feedback_oracle_set_id": feedback_binding["suite_id"],
            "validation_oracle_set_id": validation_binding["suite_id"],
        },
        "iterations": iterations,
        "outcome": {
            "final_candidate_path": _rel(final_candidate_path, work_dir),
            "final_bpr_feedback": final_bpr_feedback,
            "final_bpr_validation": final_bpr_validation,
            "outcome_class": outcome_class,
            "complete_repair": final_bpr_validation >= 1.0,
            "effective_repair": patch_applied
            and final_bpr_validation > input_bpr_validation,
            "behavioural_degradation": patch_applied
            and final_bpr_validation < input_bpr_validation,
            "regression_detected": regression_any,
            "overfitting_detected": overfitting_any,
            "iterations_to_outcome": 0,
        },
        "cost": {
            "prompt_tokens_estimated": 0,
            "completion_tokens_estimated": 0,
            "wall_time_seconds": 0.0,
            "oracle_executions": oracle_executions,
            "patch_operations_total": patch_ops_total,
        },
        "reproducibility": {
            "code_version": "dry-run",
            "command": "python scripts/run_repair_condition.py",
            "environment_id": "dry_run_orchestrator",
            "input_checksums": {
                "case.json": _sha256_file(work_dir / "case.json"),
            },
            "output_checksums": _checksum_map(output_checksum_entries),
        },
    }

    if patch_source and patch_source.is_file():
        repair_run["reproducibility"]["input_checksums"]["patch_source.json"] = (
            _sha256_file(patch_source)
        )

    if json.dumps(case, sort_keys=True) != json.dumps(case_snapshot, sort_keys=True):
        raise RunnerError("case bundle was mutated (internal error)")

    return repair_run


def write_repair_run(doc: dict[str, Any], path: Path) -> None:
    """Write repair_run.json. Does not embed a checksum of itself (see docs/repair_run_format.md)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    validate_repair_run(doc)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-dir", required=True, type=Path)
    parser.add_argument("--condition", required=True)
    parser.add_argument("--patch-source", type=Path, default=None)
    parser.add_argument("--output-run", required=True, type=Path)
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument(
        "--execution-backend",
        choices=sorted(VALID_EXECUTION_BACKENDS),
        default=None,
        help="Repair engine backend (default: none; baseline A always none)",
    )
    parser.add_argument(
        "--model-name",
        default=None,
        help="Engine model tag when backend is ollama (repair engine metadata)",
    )
    parser.add_argument(
        "--model-digest",
        default=None,
        help="Optional frozen model content digest",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=None,
        help="Decoding temperature recorded in repair_run (default: 0.0)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Optional generation seed recorded in repair_run",
    )
    args = parser.parse_args(argv)

    try:
        repair_run = run_dry_repair_condition(
            case_dir=args.case_dir,
            condition=args.condition,
            work_dir=args.work_dir,
            patch_source=args.patch_source,
            execution_backend=args.execution_backend,
            model_name=args.model_name,
            model_digest=args.model_digest,
            temperature=args.temperature,
            seed=args.seed,
        )
        write_repair_run(repair_run, args.output_run)
    except (RunnerError, DiagnosticBuildError, PatchEngineError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(repair_run, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
