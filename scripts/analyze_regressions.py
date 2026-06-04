#!/usr/bin/env python3
"""
Characterize behavioural regressions (BPR decrease) from diagnostic granularity pilots.

Read-only scan of --pilot-dir runs/*/repair_run.json.
Writes analysis/regression_summary.csv and analysis/regression_summary.json.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from analyze_successful_repairs import (  # noqa: E402
    CONDITION_LABELS,
    condition_label,
    load_patch_operations,
)

BPR_TOLERANCE = 1e-9
ANALYSIS_DIR = "analysis"
CSV_NAME = "regression_summary.csv"
JSON_NAME = "regression_summary.json"

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
    "behavioural_degradation",
    "regression_detected",
]


class AnalysisError(Exception):
    """Raised when pilot layout is invalid."""


@dataclass
class RegressionRecord:
    case_id: str
    condition: str
    system_id: str
    model: str
    patch_operation_count: int
    operation_types: list[str]
    delta_bpr: float
    initial_bpr_validation: float
    final_bpr_validation: float
    behavioural_degradation: bool
    regression_detected: bool

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
            "behavioural_degradation": str(self.behavioural_degradation).lower(),
            "regression_detected": str(self.regression_detected).lower(),
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
            "behavioural_degradation": self.behavioural_degradation,
            "regression_detected": self.regression_detected,
        }


def extract_degraded_case(
    *,
    case_id: str,
    path_label: str,
    cond_dir: Path,
    repair_run: dict[str, Any],
) -> RegressionRecord | None:
    iterations = repair_run.get("iterations") or []
    if not iterations:
        return None
    initial = iterations[0].get("input_bpr_validation")
    outcome = repair_run.get("outcome") or {}
    final = outcome.get("final_bpr_validation")
    if initial is None or final is None:
        return None

    initial_f = float(initial)
    final_f = float(final)
    if final_f >= initial_f - BPR_TOLERANCE:
        return None

    identity = repair_run.get("identity") or {}
    execution = repair_run.get("execution") or {}
    system_id = str(identity.get("system_id", "unknown"))
    model = str(execution.get("model_name") or "unknown")

    op_count, op_types = load_patch_operations(cond_dir, repair_run)
    if op_count == 0:
        cost = repair_run.get("cost") or {}
        op_count = int(cost.get("patch_operations_total", 0))

    return RegressionRecord(
        case_id=case_id,
        condition=condition_label(repair_run, path_label),
        system_id=system_id,
        model=model,
        patch_operation_count=op_count,
        operation_types=op_types,
        delta_bpr=final_f - initial_f,
        initial_bpr_validation=initial_f,
        final_bpr_validation=final_f,
        behavioural_degradation=bool(outcome.get("behavioural_degradation")),
        regression_detected=bool(outcome.get("regression_detected")),
    )


def discover_regressions(pilot_dir: Path) -> list[RegressionRecord]:
    runs_dir = pilot_dir / "runs"
    if not runs_dir.is_dir():
        raise AnalysisError(f"missing runs directory: {runs_dir}")

    records: list[RegressionRecord] = []
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
            rec = extract_degraded_case(
                case_id=case_id,
                path_label=label,
                cond_dir=cond_dir,
                repair_run=repair_run,
            )
            if rec is not None:
                records.append(rec)
    return records


def compute_aggregates(records: list[RegressionRecord]) -> dict[str, Any]:
    by_condition: Counter[str] = Counter()
    by_system: Counter[str] = Counter()
    by_model: Counter[str] = Counter()
    op_type_counts: Counter[str] = Counter()
    deltas: list[float] = []
    op_counts: list[int] = []
    behavioural_flags = 0
    regression_flags = 0

    for rec in records:
        by_condition[rec.condition] += 1
        by_system[rec.system_id] += 1
        by_model[rec.model] += 1
        deltas.append(rec.delta_bpr)
        op_counts.append(rec.patch_operation_count)
        for op in rec.operation_types:
            op_type_counts[op] += 1
        if rec.behavioural_degradation:
            behavioural_flags += 1
        if rec.regression_detected:
            regression_flags += 1

    def _mean(vals: list[float]) -> float | None:
        return sum(vals) / len(vals) if vals else None

    return {
        "degraded_count": len(records),
        "by_condition": dict(sorted(by_condition.items())),
        "by_system_id": dict(sorted(by_system.items())),
        "by_model": dict(sorted(by_model.items())),
        "mean_delta_bpr": _mean(deltas),
        "mean_patch_operation_count": _mean([float(x) for x in op_counts]),
        "operation_type_counts": dict(sorted(op_type_counts.items())),
        "behavioural_degradation_count": behavioural_flags,
        "regression_detected_count": regression_flags,
    }


def analyze_regressions(pilot_dir: Path) -> tuple[list[RegressionRecord], dict[str, Any]]:
    pilot_dir = pilot_dir.resolve()
    records = discover_regressions(pilot_dir)
    summary = {
        "schema_version": "1.0.0",
        "pilot_dir": str(pilot_dir),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "aggregates": compute_aggregates(records),
        "regressions": [r.to_json_dict() for r in records],
    }
    return records, summary


def write_outputs(
    pilot_dir: Path,
    records: list[RegressionRecord],
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
        records, summary = analyze_regressions(args.pilot_dir)
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
    print(f"degraded cases: {agg['degraded_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
