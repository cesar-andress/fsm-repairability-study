#!/usr/bin/env python3
"""
Characterize effective repairs (BPR improvement) from diagnostic granularity pilots.

Read-only scan of --pilot-dir runs/*/repair_run.json.
Writes analysis/successful_repairs.csv and analysis/successful_repairs.json.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from build_diagnostic import _failure_categories  # noqa: E402

CONDITION_LABELS = ("C", "D", "E")
ANALYSIS_DIR = "analysis"
CSV_NAME = "successful_repairs.csv"
JSON_NAME = "successful_repairs.json"

REPAIR_CONDITION_TO_LABEL = {
    "patch_binary_feedback": "C",
    "patch_trace_feedback": "D",
    "patch_localized_feedback": "E",
}

CSV_FIELDS = [
    "case_id",
    "condition",
    "system_id",
    "model",
    "patch_operation_count",
    "operation_types",
    "delta_bpr",
    "initial_bpr_validation",
    "final_bpr_validation",
    "failure_categories_fixed",
    "tests_fixed_count",
    "tests_fixed",
]


class AnalysisError(Exception):
    """Raised when pilot layout is invalid."""


@dataclass
class SuccessfulRepairRecord:
    case_id: str
    condition: str
    system_id: str
    model: str
    patch_operation_count: int
    operation_types: list[str]
    delta_bpr: float
    initial_bpr_validation: float
    final_bpr_validation: float
    failure_categories_fixed: list[str]
    tests_fixed: list[str]

    def to_csv_row(self) -> dict[str, str]:
        return {
            "case_id": self.case_id,
            "condition": self.condition,
            "system_id": self.system_id,
            "model": self.model,
            "patch_operation_count": str(self.patch_operation_count),
            "operation_types": ";".join(self.operation_types),
            "delta_bpr": str(self.delta_bpr),
            "initial_bpr_validation": str(self.initial_bpr_validation),
            "final_bpr_validation": str(self.final_bpr_validation),
            "failure_categories_fixed": ";".join(self.failure_categories_fixed),
            "tests_fixed_count": str(len(self.tests_fixed)),
            "tests_fixed": ";".join(self.tests_fixed),
        }

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "condition": self.condition,
            "system_id": self.system_id,
            "model": self.model,
            "patch_operation_count": self.patch_operation_count,
            "operation_types": self.operation_types,
            "delta_bpr": self.delta_bpr,
            "initial_bpr_validation": self.initial_bpr_validation,
            "final_bpr_validation": self.final_bpr_validation,
            "failure_categories_fixed": self.failure_categories_fixed,
            "tests_fixed": self.tests_fixed,
        }


def load_score_report(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def load_patch_operations(cond_dir: Path, repair_run: dict[str, Any]) -> tuple[int, list[str]]:
    run_dir = cond_dir / "run"
    paths_to_try: list[Path] = []
    iterations = repair_run.get("iterations") or []
    if iterations:
        rel = iterations[0].get("generated_patch_path")
        if rel:
            paths_to_try.append(run_dir / str(rel))
    paths_to_try.extend(
        [
            run_dir / "patches" / "iter_000_source.json",
            cond_dir / "ollama" / "patch.json",
        ]
    )
    for path in paths_to_try:
        if not path.is_file():
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        ops = doc.get("operations") or []
        types = [str(op.get("op", "")) for op in ops if isinstance(op, dict)]
        return len(ops), types
    return 0, []


def failure_categories_from_score(score: dict[str, Any]) -> dict[str, int]:
    failures = score.get("failures") or []
    if not isinstance(failures, list):
        failures = []
    return _failure_categories(failures)


def pre_failure_categories(cond_dir: Path, run_dir: Path) -> dict[str, int]:
    diag_path = run_dir / "diagnostics" / "iter_000_feedback.json"
    if diag_path.is_file():
        try:
            doc = json.loads(diag_path.read_text(encoding="utf-8"))
            cats = doc.get("failure_categories")
            if isinstance(cats, dict):
                return {str(k): int(v) for k, v in cats.items()}
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass
    before = load_score_report(run_dir / "scores" / "iter_000_input_validation.json")
    if before:
        return failure_categories_from_score(before)
    return {}


def post_failure_categories(run_dir: Path) -> dict[str, int]:
    after = load_score_report(run_dir / "scores" / "iter_001_validation.json")
    if after:
        return failure_categories_from_score(after)
    return {}


def fixed_test_ids(before: dict[str, Any] | None, after: dict[str, Any] | None) -> list[str]:
    if not before or not after:
        return []
    before_ids = {
        str(f["test_id"])
        for f in (before.get("failures") or [])
        if isinstance(f, dict) and f.get("test_id")
    }
    after_ids = {
        str(f["test_id"])
        for f in (after.get("failures") or [])
        if isinstance(f, dict) and f.get("test_id")
    }
    return sorted(before_ids - after_ids)


def categories_fixed(
    pre: dict[str, int], post: dict[str, int]
) -> list[str]:
    keys = sorted(set(pre) | set(post))
    fixed: list[str] = []
    for key in keys:
        if pre.get(key, 0) > post.get(key, 0):
            fixed.append(key)
    return fixed


def condition_label(repair_run: dict[str, Any], path_label: str) -> str:
    execution = repair_run.get("execution") or {}
    cond_id = execution.get("repair_condition")
    return REPAIR_CONDITION_TO_LABEL.get(str(cond_id), path_label)


def extract_effective_repair(
    *,
    case_id: str,
    path_label: str,
    cond_dir: Path,
    repair_run: dict[str, Any],
) -> SuccessfulRepairRecord | None:
    outcome = repair_run.get("outcome") or {}
    if not outcome.get("effective_repair"):
        return None

    iterations = repair_run.get("iterations") or []
    if not iterations:
        return None
    initial = iterations[0].get("input_bpr_validation")
    final = outcome.get("final_bpr_validation")
    if initial is None or final is None:
        return None
    initial_f = float(initial)
    final_f = float(final)
    if final_f <= initial_f:
        return None

    identity = repair_run.get("identity") or {}
    execution = repair_run.get("execution") or {}
    system_id = str(identity.get("system_id", "unknown"))
    model = str(execution.get("model_name") or "unknown")

    op_count, op_types = load_patch_operations(cond_dir, repair_run)
    if op_count == 0:
        cost = repair_run.get("cost") or {}
        op_count = int(cost.get("patch_operations_total", 0))

    run_dir = cond_dir / "run"
    pre_cats = pre_failure_categories(cond_dir, run_dir)
    post_cats = post_failure_categories(run_dir)
    before_score = load_score_report(run_dir / "scores" / "iter_000_input_validation.json")
    after_score = load_score_report(run_dir / "scores" / "iter_001_validation.json")
    fixed_tests = fixed_test_ids(before_score, after_score)

    return SuccessfulRepairRecord(
        case_id=case_id,
        condition=condition_label(repair_run, path_label),
        system_id=system_id,
        model=model,
        patch_operation_count=op_count,
        operation_types=op_types,
        delta_bpr=final_f - initial_f,
        initial_bpr_validation=initial_f,
        final_bpr_validation=final_f,
        failure_categories_fixed=categories_fixed(pre_cats, post_cats),
        tests_fixed=fixed_tests,
    )


def discover_effective_repairs(pilot_dir: Path) -> list[SuccessfulRepairRecord]:
    runs_dir = pilot_dir / "runs"
    if not runs_dir.is_dir():
        raise AnalysisError(f"missing runs directory: {runs_dir}")

    records: list[SuccessfulRepairRecord] = []
    for case_dir in sorted(runs_dir.iterdir()):
        if not case_dir.is_dir():
            continue
        case_id = case_dir.name
        for label in CONDITION_LABELS:
            cond_dir = case_dir / label
            run_path = cond_dir / "repair_run.json"
            if not run_path.is_file():
                continue
            try:
                repair_run = json.loads(run_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            rec = extract_effective_repair(
                case_id=case_id,
                path_label=label,
                cond_dir=cond_dir,
                repair_run=repair_run,
            )
            if rec is not None:
                records.append(rec)
    return records


def compute_aggregates(records: list[SuccessfulRepairRecord]) -> dict[str, Any]:
    by_condition: Counter[str] = Counter()
    by_system: Counter[str] = Counter()
    by_model: Counter[str] = Counter()
    op_type_counts: Counter[str] = Counter()
    category_fixed_counts: Counter[str] = Counter()
    deltas: list[float] = []
    op_counts: list[int] = []

    for rec in records:
        by_condition[rec.condition] += 1
        by_system[rec.system_id] += 1
        by_model[rec.model] += 1
        deltas.append(rec.delta_bpr)
        op_counts.append(rec.patch_operation_count)
        for op in rec.operation_types:
            op_type_counts[op] += 1
        for cat in rec.failure_categories_fixed:
            category_fixed_counts[cat] += 1

    def _mean(vals: list[float]) -> float | None:
        return sum(vals) / len(vals) if vals else None

    return {
        "effective_repair_count": len(records),
        "by_condition": dict(sorted(by_condition.items())),
        "by_system_id": dict(sorted(by_system.items())),
        "by_model": dict(sorted(by_model.items())),
        "mean_delta_bpr": _mean(deltas),
        "mean_patch_operation_count": _mean([float(x) for x in op_counts]),
        "operation_type_counts": dict(sorted(op_type_counts.items())),
        "failure_categories_fixed_counts": dict(sorted(category_fixed_counts.items())),
        "total_tests_fixed": sum(len(r.tests_fixed) for r in records),
    }


def analyze_successful_repairs(pilot_dir: Path) -> tuple[list[SuccessfulRepairRecord], dict[str, Any]]:
    pilot_dir = pilot_dir.resolve()
    records = discover_effective_repairs(pilot_dir)
    summary = {
        "schema_version": "1.0.0",
        "pilot_dir": str(pilot_dir),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "aggregates": compute_aggregates(records),
        "repairs": [r.to_json_dict() for r in records],
    }
    return records, summary


def write_outputs(
    pilot_dir: Path,
    records: list[SuccessfulRepairRecord],
    summary: dict[str, Any],
    *,
    output_dir: Path | None = None,
) -> tuple[Path, Path]:
    out = (output_dir or pilot_dir / ANALYSIS_DIR).resolve()
    out.mkdir(parents=True, exist_ok=True)
    csv_path = out / CSV_NAME
    json_path = out / JSON_NAME

    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for rec in records:
            writer.writerow(rec.to_csv_row())

    json_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return csv_path, json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pilot-dir",
        required=True,
        type=Path,
        help="Diagnostic granularity pilot output root (read-only)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help=f"Write summaries here (default: <pilot-dir>/{ANALYSIS_DIR})",
    )
    args = parser.parse_args(argv)

    try:
        records, summary = analyze_successful_repairs(args.pilot_dir)
        csv_path, json_path = write_outputs(
            args.pilot_dir,
            records,
            summary,
            output_dir=args.output_dir,
        )
    except AnalysisError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    agg = summary["aggregates"]
    print(json.dumps(agg, indent=2))
    print(f"wrote {csv_path}")
    print(f"wrote {json_path}")
    print(f"effective repairs: {agg['effective_repair_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
