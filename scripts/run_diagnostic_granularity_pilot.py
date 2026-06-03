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
from generate_patch_ollama import (  # noqa: E402
    PROMPT_VARIANTS,
    resolve_prompt_variant_for_condition,
)
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

CONDITION_LABELS = tuple(GRANULARITY_CONDITIONS.keys())

RESULT_FIELDS = [
    "case_id",
    "initial_bpr",
    *(f"status_{label}" for label in CONDITION_LABELS),
    *(f"error_{label}" for label in CONDITION_LABELS),
    *(f"patch_valid_{label}" for label in CONDITION_LABELS),
    *(f"patch_applied_{label}" for label in CONDITION_LABELS),
    *(f"outcome_{label}" for label in CONDITION_LABELS),
    "final_bpr_C",
    "final_bpr_D",
    "final_bpr_E",
    "delta_C",
    "delta_D",
    "delta_E",
    "best_condition",
]

FAILURE_CATEGORY_TO_STATUS: dict[str, str] = {
    "generation_failure": "generation_error",
    "invalid_patch": "invalid_patch",
    "patch_application_failure": "patch_application_error",
    "scoring_failure": "scoring_error",
    "other_failure": "runner_error",
}

TERMINAL_OK = "ok"
TERMINAL_ABSTAINED = "abstained"
TERMINAL_SKIPPED = "skipped"


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
    patch_valid: dict[str, str] = field(
        default_factory=lambda: {"C": "", "D": "", "E": ""}
    )
    patch_applied: dict[str, str] = field(
        default_factory=lambda: {"C": "", "D": "", "E": ""}
    )
    outcome: dict[str, str] = field(
        default_factory=lambda: {"C": "", "D": "", "E": ""}
    )
    failure_category: dict[str, str] = field(default_factory=dict)


def _bool_csv(value: bool | None) -> str:
    if value is None:
        return ""
    return "true" if value else "false"


def _patch_valid_csv(value: bool | None, *, abstained: bool = False) -> str:
    if abstained:
        return "n/a"
    return _bool_csv(value)


def classify_failure(result: CaseResult) -> str:
    """Map pipeline errors to summary failure category keys."""
    if result.status in (TERMINAL_OK, TERMINAL_ABSTAINED, TERMINAL_SKIPPED):
        return ""
    msg = (result.error or "").lower()
    if "patch validation" in msg or "patch schema" in msg or "validate patch" in msg:
        return "invalid_patch"
    if "patch application" in msg or "apply_patch" in msg or "patchengine" in msg:
        return "patch_application_failure"
    if (
        "ollama" in msg
        or "model response" in msg
        or "prompt template" in msg
        or "patch generation" in msg
        or "no json object" in msg
    ):
        return "generation_failure"
    if "score" in msg or "scoring" in msg or "diagnostic" in msg:
        return "scoring_failure"
    return "other_failure"


def pipeline_status(result: CaseResult) -> str:
    """CSV / row status for a case–condition pipeline result."""
    if result.status == TERMINAL_OK:
        return TERMINAL_OK
    if result.status == TERMINAL_ABSTAINED:
        return TERMINAL_ABSTAINED
    if result.status == TERMINAL_SKIPPED:
        return TERMINAL_SKIPPED
    category = classify_failure(result)
    return FAILURE_CATEGORY_TO_STATUS.get(category, "runner_error")


def write_condition_error_file(cond_dir: Path, message: str) -> None:
    if not message.strip():
        return
    cond_dir.mkdir(parents=True, exist_ok=True)
    (cond_dir / "error.txt").write_text(message.strip() + "\n", encoding="utf-8")


def _apply_condition_result(
    row: GranularityCaseRow,
    label: str,
    result: CaseResult,
    *,
    cond_dir: Path,
) -> None:
    status = pipeline_status(result)
    row.status[label] = status
    if result.error:
        row.errors[label] = result.error
        write_condition_error_file(cond_dir, result.error)
    abstained = status == TERMINAL_ABSTAINED
    row.patch_valid[label] = _patch_valid_csv(result.patch_valid, abstained=abstained)
    row.patch_applied[label] = _bool_csv(result.patch_applied)
    row.outcome[label] = result.outcome_class if status in (TERMINAL_OK, TERMINAL_ABSTAINED) else ""

    if result.initial_bpr is not None:
        if row.initial_bpr is None:
            row.initial_bpr = result.initial_bpr
        elif abs(row.initial_bpr - result.initial_bpr) > 1e-9:
            mismatch = (
                f"initial_bpr mismatch {result.initial_bpr} vs {row.initial_bpr}"
            )
            row.errors[label] = (
                f"{row.errors.get(label, '')}; {mismatch}".strip("; ")
            )

    if status not in (TERMINAL_OK, TERMINAL_ABSTAINED):
        row.failure_category[label] = classify_failure(result)
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
    prompt_variant_requested: str = "default",
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
        effective_variant = resolve_prompt_variant_for_condition(
            prompt_variant_requested, condition
        )
        result = run_case_pipeline(
            case_dir=case_dir,
            condition=condition,
            model=model,
            output_dir=cond_dir,
            work_dir=cond_dir,
            ollama_config=ollama_config,
            temperature=temperature,
            prompt_variant=effective_variant,
        )
        _apply_condition_result(row, label, result, cond_dir=cond_dir)

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
    prompt_variant_requested: str = "default",
) -> dict[str, Any]:
    prompt_variant_by_condition = {
        label: resolve_prompt_variant_for_condition(
            prompt_variant_requested, GRANULARITY_CONDITIONS[label]
        )
        for label in GRANULARITY_CONDITIONS
    }
    per_condition: dict[str, dict[str, Any]] = {}

    n_cases = len(rows)

    for label in GRANULARITY_CONDITIONS:
        terminal_rows = (TERMINAL_OK, TERMINAL_ABSTAINED)
        ok_rows = [
            r
            for r in rows
            if r.status[label] in terminal_rows and r.delta[label] is not None
        ]
        abstention_rows = [r for r in rows if r.status[label] == TERMINAL_ABSTAINED]
        failed_rows = [
            r
            for r in rows
            if r.status[label] not in (*terminal_rows, TERMINAL_SKIPPED, "pending")
        ]
        deltas = [r.delta[label] for r in ok_rows if r.delta[label] is not None]
        n_ok = len(ok_rows)
        n_complete = sum(1 for r in ok_rows if r.complete_repair[label])
        n_regress = sum(1 for r in ok_rows if r.regression[label])

        def _count_category(category: str) -> int:
            return sum(
                1 for r in failed_rows if r.failure_category.get(label) == category
            )

        per_condition[label] = {
            "repair_condition": GRANULARITY_CONDITIONS[label],
            "cases_attempted": n_cases,
            "cases_evaluated": n_ok,
            "cases_failed": len(failed_rows),
            "invalid_patch_count": _count_category("invalid_patch"),
            "abstention_count": len(abstention_rows),
            "patch_application_failure_count": _count_category(
                "patch_application_failure"
            ),
            "generation_failure_count": _count_category("generation_failure"),
            "scoring_failure_count": _count_category("scoring_failure"),
            "runner_failure_count": _count_category("other_failure"),
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
        "prompt_variant": prompt_variant_requested,
        "prompt_variant_requested": prompt_variant_requested,
        "prompt_variant_by_condition": prompt_variant_by_condition,
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
            record: dict[str, Any] = {
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
            for label in CONDITION_LABELS:
                record[f"status_{label}"] = row.status[label]
                record[f"error_{label}"] = row.errors.get(label, "")
                record[f"patch_valid_{label}"] = row.patch_valid[label]
                record[f"patch_applied_{label}"] = row.patch_applied[label]
                record[f"outcome_{label}"] = row.outcome[label]
            writer.writerow(record)


def run_diagnostic_granularity_pilot(
    *,
    cases_dir: Path,
    model: str,
    max_cases: int,
    output_dir: Path,
    ollama_config: OllamaConfig | None = None,
    temperature: float = 0.0,
    iteration_budget: int = 1,
    prompt_variant: str = "default",
) -> tuple[dict[str, Any], list[GranularityCaseRow]]:
    if prompt_variant not in PROMPT_VARIANTS:
        raise GranularityPilotError(
            f"prompt_variant {prompt_variant!r} is not supported; "
            f"expected one of: {', '.join(sorted(PROMPT_VARIANTS))}"
        )
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
                prompt_variant_requested=prompt_variant,
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
        prompt_variant_requested=prompt_variant,
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
    parser.add_argument(
        "--prompt-variant",
        choices=sorted(PROMPT_VARIANTS),
        default="default",
        help=(
            "Requested prompt variant; operation-inferred applies only to E "
            "(C/D use default). See docs/diagnostic_granularity_pilot.md."
        ),
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
            prompt_variant=args.prompt_variant,
        )
    except (GranularityPilotError, CampaignError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(summary, indent=2))
    print(f"wrote {args.output_dir / RESULTS_CSV}")
    print(f"wrote {args.output_dir / SUMMARY_JSON}")
    for row in rows:
        print(f"  {row.case_id}  best={_best_condition_label(row) or 'n/a'}")

    any_ok = any(
        r.status[label] == TERMINAL_OK for r in rows for label in GRANULARITY_CONDITIONS
    )
    return 0 if any_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
