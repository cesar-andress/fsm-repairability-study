#!/usr/bin/env python3
"""
Diagnostic granularity pilot: compare repair conditions C, D, E on the same cases and model.

Conditions (same iteration budget, single Ollama patch per condition):
  C = patch_binary_feedback
  D = patch_trace_feedback
  E = patch_localized_feedback

Writes diagnostic_granularity_results.csv and diagnostic_granularity_summary.json.
See docs/diagnostic_granularity_pilot.md.
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

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "results" / "diagnostic_granularity_pilot"

sys.path.insert(0, str(REPO_ROOT / "scripts"))

from ollama_client import OllamaConfig  # noqa: E402
from run_pilot_campaign import (  # noqa: E402
    CampaignError,
    CaseResult,
    discover_case_dirs,
    run_case_pipeline,
)

# Study labels → repair condition ids (primary IV levels C, D, E).
GRANULARITY_CONDITIONS: dict[str, str] = {
    "C": "patch_binary_feedback",
    "D": "patch_trace_feedback",
    "E": "patch_localized_feedback",
}

RESULTS_CSV = "diagnostic_granularity_results.csv"
SUMMARY_JSON = "diagnostic_granularity_summary.json"
STUDY_SCHEMA_VERSION = "1.0.0"

RESULT_FIELDS = [
    "case_id",
    "initial_bpr",
    "final_bpr_C",
    "final_bpr_D",
    "final_bpr_E",
    "delta_C",
    "delta_D",
    "delta_E",
    "best_condition",
]


class GranularityPilotError(Exception):
    """Raised when study configuration or aggregation fails."""


@dataclass
class GranularityCaseRow:
    case_id: str
    initial_bpr: float | None = None
    final_bpr: dict[str, float | None] = field(
        default_factory=lambda: {"C": None, "D": None, "E": None}
    )
    delta: dict[str, float | None] = field(
        default_factory=lambda: {"C": None, "D": None, "E": None}
    )
    complete_repair: dict[str, bool] = field(
        default_factory=lambda: {"C": False, "D": False, "E": False}
    )
    regression: dict[str, bool] = field(
        default_factory=lambda: {"C": False, "D": False, "E": False}
    )
    status: dict[str, str] = field(
        default_factory=lambda: {"C": "pending", "D": "pending", "E": "pending"}
    )
    errors: dict[str, str] = field(default_factory=dict)


def _apply_condition_result(row: GranularityCaseRow, label: str, result: CaseResult) -> None:
    row.status[label] = result.status
    if result.error:
        row.errors[label] = result.error
    if result.initial_bpr is not None:
        if row.initial_bpr is None:
            row.initial_bpr = result.initial_bpr
        elif abs(row.initial_bpr - result.initial_bpr) > 1e-9:
            row.errors[label] = (
                row.errors.get(label, "")
                + f"; initial_bpr mismatch {result.initial_bpr} vs {row.initial_bpr}"
            ).strip("; ")
    if result.status != "ok":
        return
    row.final_bpr[label] = result.final_bpr
    row.delta[label] = result.delta_bpr
    row.complete_repair[label] = result.complete_repair
    row.regression[label] = result.regression


def _best_condition_label(row: GranularityCaseRow) -> str:
    candidates: list[tuple[str, float]] = []
    for label in GRANULARITY_CONDITIONS:
        d = row.delta[label]
        if d is not None:
            candidates.append((label, d))
    if not candidates:
        return ""
    best_delta = max(d for _, d in candidates)
    winners = [label for label, d in candidates if d == best_delta]
    return winners[0] if len(winners) == 1 else "+".join(sorted(winners))


def run_case_all_conditions(
    *,
    case_dir: Path,
    model: str,
    output_dir: Path,
    ollama_config: OllamaConfig,
    temperature: float,
    iteration_budget: int,
) -> GranularityCaseRow:
    case_dir = case_dir.resolve()
    with (case_dir / "case.json").open(encoding="utf-8") as f:
        case = json.load(f)
    case_id = case["identity"]["case_id"]
    row = GranularityCaseRow(case_id=case_id)

    if iteration_budget != 1:
        # Pilot wiring uses one Ollama generation + one apply/score cycle per condition.
        row.errors["setup"] = (
            f"iteration_budget={iteration_budget} not implemented; pilot supports 1 only"
        )
        for label in GRANULARITY_CONDITIONS:
            row.status[label] = "skipped"
        return row

    for label, condition in GRANULARITY_CONDITIONS.items():
        cond_dir = output_dir / "runs" / case_id / label
        result = run_case_pipeline(
            case_dir=case_dir,
            condition=condition,
            model=model,
            output_dir=cond_dir,
            ollama_config=ollama_config,
            temperature=temperature,
        )
        _apply_condition_result(row, label, result)

    return row


def aggregate_summary(
    rows: list[GranularityCaseRow],
    *,
    model: str,
    cases_dir: Path,
    output_dir: Path,
    iteration_budget: int,
    started_at: str,
    completed_at: str,
) -> dict[str, Any]:
    per_condition: dict[str, dict[str, Any]] = {}

    for label in GRANULARITY_CONDITIONS:
        ok_rows = [r for r in rows if r.status[label] == "ok" and r.delta[label] is not None]
        deltas = [r.delta[label] for r in ok_rows if r.delta[label] is not None]
        n_ok = len(ok_rows)
        n_complete = sum(1 for r in ok_rows if r.complete_repair[label])
        n_regress = sum(1 for r in ok_rows if r.regression[label])

        per_condition[label] = {
            "repair_condition": GRANULARITY_CONDITIONS[label],
            "cases_evaluated": n_ok,
            "mean_delta_bpr": statistics.mean(deltas) if deltas else None,
            "median_delta_bpr": statistics.median(deltas) if deltas else None,
            "complete_repair_rate": n_complete / n_ok if n_ok else None,
            "regression_rate": n_regress / n_ok if n_ok else None,
        }

    return {
        "schema_version": STUDY_SCHEMA_VERSION,
        "study": "diagnostic_granularity_pilot",
        "purpose": (
            "Evaluate whether repair effectiveness depends on diagnostic granularity "
            "(binary vs trace vs localized feedback). Not a model benchmark."
        ),
        "model": model,
        "iteration_budget": iteration_budget,
        "conditions": dict(GRANULARITY_CONDITIONS),
        "cases_dir": str(cases_dir.resolve()),
        "output_dir": str(output_dir.resolve()),
        "started_at": started_at,
        "completed_at": completed_at,
        "cases_attempted": len(rows),
        "per_condition": per_condition,
    }


def write_results_csv(path: Path, rows: list[GranularityCaseRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "case_id": row.case_id,
                    "initial_bpr": "" if row.initial_bpr is None else row.initial_bpr,
                    "final_bpr_C": "" if row.final_bpr["C"] is None else row.final_bpr["C"],
                    "final_bpr_D": "" if row.final_bpr["D"] is None else row.final_bpr["D"],
                    "final_bpr_E": "" if row.final_bpr["E"] is None else row.final_bpr["E"],
                    "delta_C": "" if row.delta["C"] is None else row.delta["C"],
                    "delta_D": "" if row.delta["D"] is None else row.delta["D"],
                    "delta_E": "" if row.delta["E"] is None else row.delta["E"],
                    "best_condition": _best_condition_label(row),
                }
            )


def run_diagnostic_granularity_pilot(
    *,
    cases_dir: Path,
    model: str,
    max_cases: int,
    output_dir: Path,
    ollama_config: OllamaConfig | None = None,
    temperature: float = 0.0,
    iteration_budget: int = 1,
) -> tuple[dict[str, Any], list[GranularityCaseRow]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    case_dirs = discover_case_dirs(cases_dir, max_cases)
    started_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    config = ollama_config or OllamaConfig()

    rows: list[GranularityCaseRow] = []
    for case_dir in case_dirs:
        rows.append(
            run_case_all_conditions(
                case_dir=case_dir,
                model=model,
                output_dir=output_dir,
                ollama_config=config,
                temperature=temperature,
                iteration_budget=iteration_budget,
            )
        )

    completed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    summary = aggregate_summary(
        rows,
        model=model,
        cases_dir=cases_dir,
        output_dir=output_dir,
        iteration_budget=iteration_budget,
        started_at=started_at,
        completed_at=completed_at,
    )

    write_results_csv(output_dir / RESULTS_CSV, rows)
    (output_dir / SUMMARY_JSON).write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    return summary, rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases-dir", required=True, type=Path)
    parser.add_argument("--model", required=True, help="Single Ollama model (no comparison)")
    parser.add_argument("--max-cases", type=int, default=10)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument(
        "--iteration-budget",
        type=int,
        default=1,
        help="Repair iterations per condition (pilot supports 1 only)",
    )
    args = parser.parse_args(argv)

    try:
        summary, rows = run_diagnostic_granularity_pilot(
            cases_dir=args.cases_dir,
            model=args.model,
            max_cases=args.max_cases,
            output_dir=args.output_dir,
            ollama_config=OllamaConfig(base_url=args.ollama_url),
            temperature=args.temperature,
            iteration_budget=args.iteration_budget,
        )
    except (GranularityPilotError, CampaignError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(summary, indent=2))
    print(f"wrote {args.output_dir / RESULTS_CSV}")
    print(f"wrote {args.output_dir / SUMMARY_JSON}")
    for row in rows:
        print(f"  {row.case_id}  best={_best_condition_label(row) or 'n/a'}")

    any_ok = any(r.status[label] == "ok" for r in rows for label in GRANULARITY_CONDITIONS)
    return 0 if any_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
