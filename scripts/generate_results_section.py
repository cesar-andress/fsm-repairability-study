#!/usr/bin/env python3
"""
Generate an objective Results narrative fragment from pilot aggregates.

Reads:
  <paper-root>/results/main_results_table.csv
  <paper-root>/experiments/<pilot>/analysis/repair_outcome_summary.json
  <paper-root>/experiments/<pilot>/analysis/patch_failure_summary.json

Writes:
  <paper-root>/generated/results_generated.tex

Uses deterministic sentence templates only; no causal explanations or
inferential claims.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

CONDITION_LABELS = ("C", "D", "E")
VARIANT_ORDER = ("default", "operation-aware", "operation-inferred")

PILOT_VARIANTS: tuple[tuple[str, str], ...] = (
    ("default", "frozen_pilot_001"),
    ("operation-aware", "diagnostic_granularity_pilot_diverse_operation_aware_001"),
    ("operation-inferred", "frozen_main_pilot_001"),
)

REPAIR_OUTCOME_REL = Path("analysis") / "repair_outcome_summary.json"
PATCH_FAILURE_REL = Path("analysis") / "patch_failure_summary.json"

OUTPUT_NAME = "results_generated.tex"

FORBIDDEN_PHRASES = (
    "statistically significant",
    "statistical significance",
    "p-value",
    "p value",
    "caused by",
    "likely because",
    "suggests that",
    "indicates that",
    "we attribute",
    "this is due to",
)


class GeneratorError(Exception):
    """Raised when required inputs are missing or invalid."""


@dataclass(frozen=True)
class MainResultRow:
    variant: str
    condition: str
    evaluated: int
    failed: int
    patch_failures: int
    abstentions: int
    mean_delta: float
    regression: float


@dataclass(frozen=True)
class OutcomeStats:
    cases_evaluated: int
    improved_count: int
    unchanged_count: int
    degraded_count: int
    complete_repair_count: int
    effective_repair_count: int
    mean_delta_bpr: float | None


@dataclass(frozen=True)
class FailureStats:
    total_failures: int
    by_class: dict[str, int]


def escape_latex_variant(variant: str) -> str:
    return r"\texttt{" + variant.replace("-", "-") + "}"


def format_mean_delta(value: float) -> str:
    return f"${value:+.3f}$"


def format_percent_fraction(value: float) -> str:
    return f"{100.0 * value:.1f}\\%"


def load_main_results_csv(path: Path) -> dict[tuple[str, str], MainResultRow]:
    if not path.is_file():
        raise GeneratorError(f"missing CSV: {path}")
    rows: dict[tuple[str, str], MainResultRow] = {}
    with path.open(encoding="utf-8", newline="") as f:
        for raw in csv.DictReader(f):
            key = (raw["variant"], raw["condition"])
            rows[key] = MainResultRow(
                variant=raw["variant"],
                condition=raw["condition"],
                evaluated=int(raw["evaluated"]),
                failed=int(raw["failed"]),
                patch_failures=int(raw["patch_failures"]),
                abstentions=int(raw["abstentions"]),
                mean_delta=float(raw["mean_delta"]),
                regression=float(raw["regression"]),
            )
    return rows


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise GeneratorError(f"missing JSON: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_outcomes_by_variant(experiments_dir: Path) -> dict[str, dict[str, OutcomeStats]]:
    result: dict[str, dict[str, OutcomeStats]] = {}
    for variant, pilot_name in PILOT_VARIANTS:
        doc = load_json(experiments_dir / pilot_name / REPAIR_OUTCOME_REL)
        per: dict[str, OutcomeStats] = {}
        for cond in CONDITION_LABELS:
            s = doc["per_condition"][cond]
            per[cond] = OutcomeStats(
                cases_evaluated=int(s["cases_evaluated"]),
                improved_count=int(s["improved_count"]),
                unchanged_count=int(s["unchanged_count"]),
                degraded_count=int(s["degraded_count"]),
                complete_repair_count=int(s["complete_repair_count"]),
                effective_repair_count=int(s["effective_repair_count"]),
                mean_delta_bpr=s.get("mean_delta_bpr"),
            )
        result[variant] = per
    return result


def load_failures_by_variant(experiments_dir: Path) -> dict[str, FailureStats]:
    result: dict[str, FailureStats] = {}
    for variant, pilot_name in PILOT_VARIANTS:
        doc = load_json(experiments_dir / pilot_name / PATCH_FAILURE_REL)
        by_class = {
            str(k): int(v)
            for k, v in doc["aggregates"]["by_failure_class"].items()
        }
        result[variant] = FailureStats(
            total_failures=int(doc["aggregates"]["total_failures"]),
            by_class=by_class,
        )
    return result


def dominant_failure_class(by_class: dict[str, int]) -> tuple[str, int]:
    if not by_class:
        return ("none", 0)
    label = max(by_class, key=by_class.get)
    return (label, by_class[label])


def effective_repair_rate(stats: OutcomeStats) -> float:
    if stats.cases_evaluated == 0:
        return 0.0
    return stats.effective_repair_count / stats.cases_evaluated


def line_throughput_row(row: MainResultRow) -> str:
    v = escape_latex_variant(row.variant)
    return (
        f"For prompt variant {v} and condition~{row.condition}, "
        f"{row.evaluated} case--condition runs were evaluated and "
        f"{row.failed} failed; among evaluated runs the mean validation "
        f"$\\Delta\\mathrm{{BPR}}$ was {format_mean_delta(row.mean_delta)} "
        f"and the regression rate was {format_percent_fraction(row.regression)} "
        f"(Table~\\ref{{tab:main_results}})."
    )


def line_outcome_row(variant: str, cond: str, stats: OutcomeStats) -> str:
    v = escape_latex_variant(variant)
    rate = effective_repair_rate(stats)
    return (
        f"On evaluated runs for {v} and condition~{cond}, "
        f"{stats.improved_count} improved, {stats.unchanged_count} were unchanged, "
        f"{stats.degraded_count} degraded, "
        f"{stats.effective_repair_count} were effective repairs, and "
        f"{stats.complete_repair_count} were complete repairs "
        f"(effective repair rate {format_percent_fraction(rate)}; "
        f"Table~\\ref{{tab:repair_outcomes}}, Figure~\\ref{{fig:repair-success}})."
    )


def line_failure_variant(variant: str, stats: FailureStats) -> str:
    v = escape_latex_variant(variant)
    label, count = dominant_failure_class(stats.by_class)
    label_tex = label.replace("_", r"\_")
    return (
        f"For {v}, {stats.total_failures} patch application failures were recorded "
        f"over conditions~C--E; the most frequent failure class was "
        f"\\texttt{{{label_tex}}} ({count} occurrences) "
        f"(Table~\\ref{{tab:failure_analysis}}, Figure~\\ref{{fig:patch-failure}})."
    )


def line_condition_e_comparison(
    main_rows: dict[tuple[str, str], MainResultRow],
    outcomes: dict[str, dict[str, OutcomeStats]],
) -> list[str]:
    lines: list[str] = []
    for variant in VARIANT_ORDER:
        row = main_rows[(variant, "E")]
        out = outcomes[variant]["E"]
        v = escape_latex_variant(variant)
        abst = (
            f", with {row.abstentions} abstentions"
            if row.abstentions > 0
            else ""
        )
        lines.append(
            f"Under localized feedback (condition~E), {v} completed "
            f"{row.evaluated} evaluated runs and {row.failed} failed runs{abst}; "
            f"patch application failures totalled {row.patch_failures} in the CSV summary; "
            f"{out.effective_repair_count} evaluated runs were marked effective repairs "
            f"(Table~\\ref{{tab:main_results}}, Table~\\ref{{tab:repair_outcomes}})."
        )
    return lines


def total_complete_repairs(outcomes: dict[str, dict[str, OutcomeStats]]) -> int:
    return sum(
        stats.complete_repair_count
        for per in outcomes.values()
        for stats in per.values()
    )


def build_results_tex(
    main_rows: dict[tuple[str, str], MainResultRow],
    outcomes: dict[str, dict[str, OutcomeStats]],
    failures: dict[str, FailureStats],
) -> str:
    parts: list[str] = []
    parts.append(
        "% Auto-generated by scripts/generate_results_section.py\n"
        f"% Generated at {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')} (UTC)\n"
        "% Descriptive pilot results; do not edit by hand.\n\n"
    )

    parts.append(
        "This subsection is generated from frozen pilot aggregates. "
        "Counts and rates are descriptive only; the text does not report "
        "inferential statistics or causal explanations.\n\n"
    )

    parts.append(
        "Figure~\\ref{fig:evaluated-cases} visualizes evaluated case--condition counts "
        "by prompt variant and diagnostic condition.\n\n"
    )

    parts.append("\\paragraph{Throughput and validation $\\Delta\\mathrm{BPR}$.}\n")
    parts.append(
        "Table~\\ref{tab:main_results} lists evaluated and failed runs, "
        "mean $\\Delta\\mathrm{BPR}$ on evaluated runs, and regression rates.\n\n"
    )
    for variant in VARIANT_ORDER:
        for cond in CONDITION_LABELS:
            parts.append(line_throughput_row(main_rows[(variant, cond)]) + "\n\n")

    parts.append("\\paragraph{Behavioural outcomes on evaluated runs.}\n")
    parts.append(
        "Table~\\ref{tab:repair_outcomes} and Figure~\\ref{fig:repair-success} "
        "summarize outcome class counts on runs with a recorded "
        "\\texttt{repair\\_run.json}.\n\n"
    )
    for variant in VARIANT_ORDER:
        for cond in CONDITION_LABELS:
            parts.append(
                line_outcome_row(variant, cond, outcomes[variant][cond]) + "\n\n"
            )

    complete_total = total_complete_repairs(outcomes)
    parts.append(
        f"Across all prompt variants and conditions in this freeze, "
        f"{complete_total} complete repairs "
        f"($\\mathrm{{BPR}}_{{\\mathrm{{final}}}} = 1$) were recorded in "
        f"\\texttt{{repair\\_run.json}} outcome fields.\n\n"
    )

    parts.append("\\paragraph{Patch application failure modes.}\n")
    parts.append(
        "Table~\\ref{tab:failure_analysis} and Figure~\\ref{fig:patch-failure} "
        "aggregate patch-application failures by class (conditions~C--E pooled per variant).\n\n"
    )
    for variant in VARIANT_ORDER:
        parts.append(line_failure_variant(variant, failures[variant]) + "\n\n")

    parts.append("\\paragraph{Localized feedback (condition~E) across prompt variants.}\n")
    for line in line_condition_e_comparison(main_rows, outcomes):
        parts.append(line + "\n\n")

    parts.append(
        "\\paragraph{Pilot scope reminder.}\n"
        "The freeze covers 30 diverse repair cases, one repair iteration per "
        "case--condition, and a single local coder model; the generated text "
        "reports observed counts and rates only and is not a population-level benchmark.\n"
    )

    return "".join(parts)


def validate_no_forbidden_phrases(tex: str) -> None:
    lower = tex.lower()
    for phrase in FORBIDDEN_PHRASES:
        if phrase in lower:
            raise GeneratorError(f"forbidden phrase in generated text: {phrase!r}")


def generate_results_section(
    *,
    main_results_csv: Path,
    experiments_dir: Path,
    output_path: Path,
) -> Path:
    main_rows = load_main_results_csv(main_results_csv)
    outcomes = load_outcomes_by_variant(experiments_dir)
    failures = load_failures_by_variant(experiments_dir)

    expected = {(v, c) for v in VARIANT_ORDER for c in CONDITION_LABELS}
    if set(main_rows) != expected:
        missing = expected - set(main_rows)
        extra = set(main_rows) - expected
        raise GeneratorError(
            f"CSV keys mismatch; missing={missing!r} extra={extra!r}"
        )

    tex = build_results_tex(main_rows, outcomes, failures)
    validate_no_forbidden_phrases(tex)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(tex, encoding="utf-8")
    return output_path


def default_paper_root() -> Path:
    candidate = REPO_ROOT.parent / "paper"
    if candidate.is_dir():
        return candidate
    return REPO_ROOT / "paper"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paper-root", type=Path, default=None)
    parser.add_argument("--main-results-csv", type=Path, default=None)
    parser.add_argument("--experiments-dir", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)

    paper_root = (args.paper_root or default_paper_root()).resolve()
    main_csv = (args.main_results_csv or paper_root / "results" / "main_results_table.csv").resolve()
    experiments = (args.experiments_dir or paper_root / "experiments").resolve()
    output = (args.output or paper_root / "generated" / OUTPUT_NAME).resolve()

    try:
        path = generate_results_section(
            main_results_csv=main_csv,
            experiments_dir=experiments,
            output_path=output,
        )
    except GeneratorError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
