#!/usr/bin/env python3
"""
Aggregate repair effectiveness from diagnostic granularity pilot repair_run.json files.

Read-only inspection of --pilot-dir (does not modify pilot artefacts under runs/).
Writes summaries under analysis/ by default.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CONDITION_LABELS = ("C", "D", "E")
BPR_TOLERANCE = 1e-9

SUMMARY_JSON = "repair_outcome_summary.json"
SUMMARY_CSV = "repair_outcome_summary.csv"
ANALYSIS_DIR = "analysis"

CONDITION_CSV_FIELDS = [
    "condition",
    "cases_attempted",
    "cases_evaluated",
    "improved_count",
    "unchanged_count",
    "degraded_count",
    "complete_repair_count",
    "effective_repair_count",
    "mean_delta_bpr",
    "median_delta_bpr",
]


class AnalysisError(Exception):
    """Raised when pilot directory layout is invalid."""


@dataclass
class EvaluatedRun:
    case_id: str
    condition: str
    initial_bpr: float
    final_bpr: float
    delta_bpr: float
    complete_repair: bool
    effective_repair: bool
    bpr_change: str  # improved | unchanged | degraded


@dataclass
class ConditionAccumulator:
    cases_attempted: int = 0
    evaluated: list[EvaluatedRun] = field(default_factory=list)

    def to_summary(self) -> dict[str, Any]:
        deltas = [r.delta_bpr for r in self.evaluated]
        improved = sum(1 for r in self.evaluated if r.bpr_change == "improved")
        unchanged = sum(1 for r in self.evaluated if r.bpr_change == "unchanged")
        degraded = sum(1 for r in self.evaluated if r.bpr_change == "degraded")
        complete = sum(1 for r in self.evaluated if r.complete_repair)
        effective = sum(1 for r in self.evaluated if r.effective_repair)

        return {
            "cases_attempted": self.cases_attempted,
            "cases_evaluated": len(self.evaluated),
            "improved_count": improved,
            "unchanged_count": unchanged,
            "degraded_count": degraded,
            "complete_repair_count": complete,
            "effective_repair_count": effective,
            "mean_delta_bpr": statistics.mean(deltas) if deltas else None,
            "median_delta_bpr": statistics.median(deltas) if deltas else None,
        }


def _compare_bpr(initial: float, final: float) -> str:
    if final > initial + BPR_TOLERANCE:
        return "improved"
    if final < initial - BPR_TOLERANCE:
        return "degraded"
    return "unchanged"


def _initial_bpr_validation(doc: dict[str, Any]) -> float | None:
    iterations = doc.get("iterations") or []
    if not iterations:
        return None
    raw = iterations[0].get("input_bpr_validation")
    if raw is None:
        return None
    return float(raw)


def _final_bpr_validation(doc: dict[str, Any]) -> float | None:
    outcome = doc.get("outcome") or {}
    raw = outcome.get("final_bpr_validation")
    if raw is None:
        return None
    return float(raw)


def parse_repair_run(path: Path, *, condition: str, case_id: str) -> EvaluatedRun | None:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    initial = _initial_bpr_validation(doc)
    final = _final_bpr_validation(doc)
    if initial is None or final is None:
        return None

    outcome = doc.get("outcome") or {}
    delta = final - initial
    return EvaluatedRun(
        case_id=case_id,
        condition=condition,
        initial_bpr=initial,
        final_bpr=final,
        delta_bpr=delta,
        complete_repair=bool(outcome.get("complete_repair")),
        effective_repair=bool(outcome.get("effective_repair")),
        bpr_change=_compare_bpr(initial, final),
    )


def discover_case_ids(runs_dir: Path) -> list[str]:
    if not runs_dir.is_dir():
        return []
    return sorted(
        p.name for p in runs_dir.iterdir() if p.is_dir() and not p.name.startswith(".")
    )


def analyze_repair_outcomes(pilot_dir: Path) -> dict[str, Any]:
    pilot_dir = pilot_dir.resolve()
    runs_dir = pilot_dir / "runs"
    if not runs_dir.is_dir():
        raise AnalysisError(f"missing runs directory: {runs_dir}")

    case_ids = discover_case_ids(runs_dir)
    accumulators = {label: ConditionAccumulator() for label in CONDITION_LABELS}

    for case_id in case_ids:
        case_dir = runs_dir / case_id
        for label in CONDITION_LABELS:
            cond_dir = case_dir / label
            if not cond_dir.is_dir():
                continue
            accumulators[label].cases_attempted += 1
            run_path = cond_dir / "repair_run.json"
            if not run_path.is_file():
                continue
            evaluated = parse_repair_run(run_path, condition=label, case_id=case_id)
            if evaluated is not None:
                accumulators[label].evaluated.append(evaluated)

    per_condition = {
        label: accumulators[label].to_summary() for label in CONDITION_LABELS
    }

    return {
        "schema_version": "1.0.0",
        "pilot_dir": str(pilot_dir),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "per_condition": per_condition,
    }


def write_outputs(
    pilot_dir: Path,
    summary: dict[str, Any],
    *,
    output_dir: Path | None = None,
) -> tuple[Path, Path]:
    base = (output_dir or pilot_dir / ANALYSIS_DIR).resolve()
    base.mkdir(parents=True, exist_ok=True)
    json_path = base / SUMMARY_JSON
    csv_path = base / SUMMARY_CSV

    json_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CONDITION_CSV_FIELDS)
        writer.writeheader()
        for label in CONDITION_LABELS:
            row = summary["per_condition"][label]
            writer.writerow(
                {
                    "condition": label,
                    "cases_attempted": row["cases_attempted"],
                    "cases_evaluated": row["cases_evaluated"],
                    "improved_count": row["improved_count"],
                    "unchanged_count": row["unchanged_count"],
                    "degraded_count": row["degraded_count"],
                    "complete_repair_count": row["complete_repair_count"],
                    "effective_repair_count": row["effective_repair_count"],
                    "mean_delta_bpr": ""
                    if row["mean_delta_bpr"] is None
                    else row["mean_delta_bpr"],
                    "median_delta_bpr": ""
                    if row["median_delta_bpr"] is None
                    else row["median_delta_bpr"],
                }
            )

    return json_path, csv_path


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
        summary = analyze_repair_outcomes(args.pilot_dir)
        json_path, csv_path = write_outputs(
            args.pilot_dir,
            summary,
            output_dir=args.output_dir,
        )
    except AnalysisError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(summary["per_condition"], indent=2))
    print(f"wrote {json_path}")
    print(f"wrote {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
