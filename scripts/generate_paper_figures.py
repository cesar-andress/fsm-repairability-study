#!/usr/bin/env python3
"""
Generate publication-quality PDF figures for the paper from aggregated pilot results.

Default inputs (under --paper-root):
  results/main_results_table.csv
  experiments/<pilot>/analysis/repair_outcome_summary.json
  experiments/<pilot>/analysis/patch_failure_summary.json

Writes vector PDFs to figures/ (matplotlib only).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

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

FAILURE_CLASSES = (
    "duplicate_transition",
    "missing_state",
    "transition_not_found",
    "invalid_operation_semantics",
)
FAILURE_LABELS = {
    "duplicate_transition": "Duplicate transition",
    "missing_state": "Missing state",
    "transition_not_found": "Transition not found",
    "invalid_operation_semantics": "Invalid operation semantics",
}
FAILURE_COLORS = {
    "duplicate_transition": "#4C72B0",
    "missing_state": "#DD8452",
    "transition_not_found": "#55A868",
    "invalid_operation_semantics": "#C44E52",
}

FIG_REPAIR_SUCCESS = "repair_success_rate.pdf"
FIG_PATCH_FAILURE = "patch_failure_breakdown.pdf"
FIG_EVALUATED = "evaluated_cases_by_variant.pdf"


class FigureGeneratorError(Exception):
    """Raised when inputs are missing or invalid."""


@dataclass(frozen=True)
class VariantBundle:
    variant: str
    repair_outcome: dict[str, Any]
    patch_failure: dict[str, Any]


def apply_publication_style() -> None:
    mpl.rcParams.update(
        {
            "font.family": "serif",
            "font.size": 10,
            "axes.labelsize": 10,
            "axes.titlesize": 11,
            "legend.fontsize": 8,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FigureGeneratorError(f"missing JSON: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_main_results_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FigureGeneratorError(f"missing CSV: {path}")
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def discover_variant_bundles(experiments_dir: Path) -> list[VariantBundle]:
    bundles: list[VariantBundle] = []
    for variant, pilot_name in PILOT_VARIANTS:
        pilot_dir = experiments_dir / pilot_name
        if not pilot_dir.is_dir():
            raise FigureGeneratorError(f"pilot directory not found: {pilot_dir}")
        bundles.append(
            VariantBundle(
                variant=variant,
                repair_outcome=load_json(pilot_dir / REPAIR_OUTCOME_REL),
                patch_failure=load_json(pilot_dir / PATCH_FAILURE_REL),
            )
        )
    return bundles


def success_rate(bundle: VariantBundle, condition: str) -> float:
    stats = bundle.repair_outcome["per_condition"][condition]
    evaluated = int(stats["cases_evaluated"])
    if evaluated == 0:
        return 0.0
    return int(stats["effective_repair_count"]) / evaluated


def plot_repair_success_rate(bundles: list[VariantBundle], output_path: Path) -> None:
    apply_publication_style()
    fig, ax = plt.subplots(figsize=(6.5, 3.5))
    x = range(len(VARIANT_ORDER))
    width = 0.25
    offsets = [-width, 0.0, width]

    for offset, condition in zip(offsets, CONDITION_LABELS):
        rates = [
            success_rate(next(b for b in bundles if b.variant == v), condition)
            for v in VARIANT_ORDER
        ]
        positions = [xi + offset for xi in x]
        ax.bar(
            positions,
            rates,
            width=width,
            label=f"Condition {condition}",
            edgecolor="white",
            linewidth=0.4,
        )

    ax.set_ylabel("Effective repair rate")
    ax.set_xlabel("Prompt variant")
    ax.set_title("Repair success rate on evaluated runs")
    ax.set_xticks(list(x))
    ax.set_xticklabels(VARIANT_ORDER, rotation=15, ha="right")
    ax.set_ylim(0, 1.0)
    ax.yaxis.set_major_formatter(mpl.ticker.PercentFormatter(1.0))
    ax.legend(loc="upper right", frameon=False)
    fig.tight_layout()
    fig.savefig(output_path, format="pdf", bbox_inches="tight")
    plt.close(fig)


def plot_patch_failure_breakdown(bundles: list[VariantBundle], output_path: Path) -> None:
    apply_publication_style()
    fig, ax = plt.subplots(figsize=(6.5, 3.5))
    x = range(len(VARIANT_ORDER))
    bottoms = [0.0] * len(VARIANT_ORDER)

    for failure_class in FAILURE_CLASSES:
        values = []
        for variant in VARIANT_ORDER:
            bundle = next(b for b in bundles if b.variant == variant)
            by_class = bundle.patch_failure["aggregates"]["by_failure_class"]
            values.append(by_class.get(failure_class, 0))
        ax.bar(
            x,
            values,
            bottom=bottoms,
            label=FAILURE_LABELS[failure_class],
            color=FAILURE_COLORS[failure_class],
            edgecolor="white",
            linewidth=0.4,
        )
        bottoms = [b + v for b, v in zip(bottoms, values)]

    ax.set_ylabel("Patch application failures")
    ax.set_xlabel("Prompt variant")
    ax.set_title("Patch failure mode breakdown (conditions C--E)")
    ax.set_xticks(list(x))
    ax.set_xticklabels(VARIANT_ORDER, rotation=15, ha="right")
    ax.legend(loc="upper right", frameon=False, ncol=2)
    fig.tight_layout()
    fig.savefig(output_path, format="pdf", bbox_inches="tight")
    plt.close(fig)


def plot_evaluated_cases(rows: list[dict[str, str]], output_path: Path) -> None:
    apply_publication_style()
    fig, ax = plt.subplots(figsize=(6.5, 3.5))
    x = range(len(VARIANT_ORDER))
    width = 0.25
    offsets = [-width, 0.0, width]

    by_key = {(r["variant"], r["condition"]): r for r in rows}

    for offset, condition in zip(offsets, CONDITION_LABELS):
        counts = [
            int(by_key[(v, condition)]["evaluated"])
            for v in VARIANT_ORDER
        ]
        positions = [xi + offset for xi in x]
        ax.bar(
            positions,
            counts,
            width=width,
            label=f"Condition {condition}",
            edgecolor="white",
            linewidth=0.4,
        )

    ax.set_ylabel("Evaluated cases")
    ax.set_xlabel("Prompt variant")
    ax.set_title("Evaluated case--condition runs by variant")
    ax.set_xticks(list(x))
    ax.set_xticklabels(VARIANT_ORDER, rotation=15, ha="right")
    ax.set_ylim(0, 30)
    ax.legend(loc="upper right", frameon=False)
    fig.tight_layout()
    fig.savefig(output_path, format="pdf", bbox_inches="tight")
    plt.close(fig)


def generate_paper_figures(
    *,
    main_results_csv: Path,
    experiments_dir: Path,
    figures_dir: Path,
) -> tuple[Path, Path, Path]:
    rows = load_main_results_csv(main_results_csv)
    bundles = discover_variant_bundles(experiments_dir)

    figures_dir.mkdir(parents=True, exist_ok=True)
    success_path = figures_dir / FIG_REPAIR_SUCCESS
    failure_path = figures_dir / FIG_PATCH_FAILURE
    evaluated_path = figures_dir / FIG_EVALUATED

    plot_repair_success_rate(bundles, success_path)
    plot_patch_failure_breakdown(bundles, failure_path)
    plot_evaluated_cases(rows, evaluated_path)
    return success_path, failure_path, evaluated_path


def default_paper_root() -> Path:
    candidate = REPO_ROOT.parent / "paper"
    if candidate.is_dir():
        return candidate
    return REPO_ROOT / "paper"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--paper-root",
        type=Path,
        default=None,
        help="Paper workspace root (default: ../paper next to study repo)",
    )
    parser.add_argument(
        "--main-results-csv",
        type=Path,
        default=None,
        help="Main results table CSV (default: <paper-root>/results/main_results_table.csv)",
    )
    parser.add_argument(
        "--experiments-dir",
        type=Path,
        default=None,
        help="Experiments root for per-pilot analysis JSON (default: <paper-root>/experiments)",
    )
    parser.add_argument(
        "--figures-dir",
        type=Path,
        default=None,
        help="Output directory for PDF figures (default: <paper-root>/figures)",
    )
    args = parser.parse_args(argv)

    paper_root = (args.paper_root or default_paper_root()).resolve()
    main_results_csv = (
        args.main_results_csv or paper_root / "results" / "main_results_table.csv"
    ).resolve()
    experiments_dir = (args.experiments_dir or paper_root / "experiments").resolve()
    figures_dir = (args.figures_dir or paper_root / "figures").resolve()

    try:
        paths = generate_paper_figures(
            main_results_csv=main_results_csv,
            experiments_dir=experiments_dir,
            figures_dir=figures_dir,
        )
    except FigureGeneratorError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    for path in paths:
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
