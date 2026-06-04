#!/usr/bin/env python3
"""
Generate paper-ready LaTeX tables from diagnostic granularity pilot experiments.

Reads pilot outputs under <paper-root>/experiments/ (read-only on runs/).
Writes:
  <paper-root>/tables/main_results.tex
  <paper-root>/tables/failure_analysis.tex
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

# Import sibling analysis modules when run as script or from tests.
_SCRIPTS = REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from analyze_patch_failures import analyze_patch_failures  # noqa: E402
from analyze_repair_outcomes import analyze_repair_outcomes  # noqa: E402

CONDITION_LABELS = ("C", "D", "E")

PILOT_VARIANTS: tuple[tuple[str, str], ...] = (
    ("default", "frozen_pilot_001"),
    ("operation-aware", "diagnostic_granularity_pilot_diverse_operation_aware_001"),
    ("operation-inferred", "frozen_main_pilot_001"),
)

FAILURE_CLASS_COLUMNS = (
    "duplicate_transition",
    "missing_state",
    "transition_not_found",
    "invalid_operation_semantics",
)

MAIN_RESULTS_TEX = "main_results.tex"
FAILURE_ANALYSIS_TEX = "failure_analysis.tex"


class GeneratorError(Exception):
    """Raised when paper layout or pilot inputs are invalid."""


def escape_latex(text: str) -> str:
    replacements = (
        ("\\", r"\textbackslash{}"),
        ("&", r"\&"),
        ("%", r"\%"),
        ("$", r"\$"),
        ("#", r"\#"),
        ("_", r"\_"),
        ("{", r"\{"),
        ("}", r"\}"),
        ("~", r"\textasciitilde{}"),
        ("^", r"\textasciicircum{}"),
    )
    out = text
    for old, new in replacements:
        out = out.replace(old, new)
    return out


def format_delta_bpr(value: float | None) -> str:
    if value is None:
        return "---"
    return f"${value:+.3f}$"


def collect_main_results_rows(experiments_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for variant, pilot_name in PILOT_VARIANTS:
        pilot_dir = experiments_dir / pilot_name
        if not pilot_dir.is_dir():
            raise GeneratorError(f"pilot directory not found: {pilot_dir}")
        summary = analyze_repair_outcomes(pilot_dir)
        for condition in CONDITION_LABELS:
            stats = summary["per_condition"][condition]
            rows.append(
                {
                    "variant": variant,
                    "condition": condition,
                    "cases_evaluated": stats["cases_evaluated"],
                    "improved_count": stats["improved_count"],
                    "degraded_count": stats["degraded_count"],
                    "mean_delta_bpr": stats["mean_delta_bpr"],
                }
            )
    return rows


def collect_failure_analysis_rows(experiments_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for variant, pilot_name in PILOT_VARIANTS:
        pilot_dir = experiments_dir / pilot_name
        if not pilot_dir.is_dir():
            raise GeneratorError(f"pilot directory not found: {pilot_dir}")
        _records, summary = analyze_patch_failures(pilot_dir)
        by_class = summary["aggregates"]["by_failure_class"]
        rows.append(
            {
                "variant": variant,
                "patch_failures": summary["aggregates"]["total_failures"],
                "duplicate_transition": by_class.get("duplicate_transition", 0),
                "missing_state": by_class.get("missing_state", 0),
                "transition_not_found": by_class.get("transition_not_found", 0),
                "invalid_operation_semantics": by_class.get(
                    "invalid_operation_semantics", 0
                ),
            }
        )
    return rows


def render_main_results_table(rows: list[dict[str, Any]]) -> str:
    body_lines = [
        r"\begin{table}[t]",
        r"\centering",
        r"\caption{Repair effectiveness by prompt variant and diagnostic condition "
        r"(30-case diverse pilot). Evaluated runs completed scoring after patch "
        r"generation; $\Delta$BPR is validation BPR change.}",
        r"\label{tab:main_results}",
        r"\begin{tabular}{@{}llrrrr@{}}",
        r"\toprule",
        r"Variant & Condition & Evaluated & Improved & Degraded & Mean $\Delta$BPR \\",
        r"\midrule",
    ]
    for row in rows:
        body_lines.append(
            " & ".join(
                [
                    escape_latex(row["variant"]),
                    row["condition"],
                    str(row["cases_evaluated"]),
                    str(row["improved_count"]),
                    str(row["degraded_count"]),
                    format_delta_bpr(row["mean_delta_bpr"]),
                ]
            )
            + r" \\"
        )
    body_lines.extend(
        [
            r"\bottomrule",
            r"\end{tabular}",
            r"\end{table}",
        ]
    )
    return "\n".join(body_lines) + "\n"


def render_failure_analysis_table(rows: list[dict[str, Any]]) -> str:
    body_lines = [
        r"\begin{table}[t]",
        r"\centering",
        r"\caption{Patch application failure modes by prompt variant (aggregated "
        r"over conditions C, D, and E).}",
        r"\label{tab:failure_analysis}",
        r"\begin{tabular}{@{}lrrrrr@{}}",
        r"\toprule",
        "Variant & Patch failures & Duplicate transition & Missing state & "
        r"Transition not found & Invalid operation semantics \\",
        r"\midrule",
    ]
    for row in rows:
        body_lines.append(
            " & ".join(
                [
                    escape_latex(row["variant"]),
                    str(row["patch_failures"]),
                    str(row["duplicate_transition"]),
                    str(row["missing_state"]),
                    str(row["transition_not_found"]),
                    str(row["invalid_operation_semantics"]),
                ]
            )
            + r" \\"
        )
    body_lines.extend(
        [
            r"\bottomrule",
            r"\end{tabular}",
            r"\end{table}",
        ]
    )
    return "\n".join(body_lines) + "\n"


def file_header(tool: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return (
        f"% Auto-generated by {tool}\n"
        f"% Generated at {ts} (UTC)\n"
        f"% Requires \\usepackage{{booktabs}}\n"
        "\n"
    )


def generate_paper_tables(
    *,
    experiments_dir: Path,
    tables_dir: Path,
) -> tuple[Path, Path]:
    experiments_dir = experiments_dir.resolve()
    tables_dir = tables_dir.resolve()
    if not experiments_dir.is_dir():
        raise GeneratorError(f"experiments directory not found: {experiments_dir}")

    main_rows = collect_main_results_rows(experiments_dir)
    failure_rows = collect_failure_analysis_rows(experiments_dir)

    tables_dir.mkdir(parents=True, exist_ok=True)
    main_path = tables_dir / MAIN_RESULTS_TEX
    failure_path = tables_dir / FAILURE_ANALYSIS_TEX

    tool = "scripts/generate_paper_results_tables.py"
    main_path.write_text(
        file_header(tool) + render_main_results_table(main_rows),
        encoding="utf-8",
    )
    failure_path.write_text(
        file_header(tool) + render_failure_analysis_table(failure_rows),
        encoding="utf-8",
    )
    return main_path, failure_path


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
        "--experiments-dir",
        type=Path,
        default=None,
        help="Pilot experiments directory (default: <paper-root>/experiments)",
    )
    parser.add_argument(
        "--tables-dir",
        type=Path,
        default=None,
        help="Output tables directory (default: <paper-root>/tables)",
    )
    args = parser.parse_args(argv)

    paper_root = (args.paper_root or default_paper_root()).resolve()
    experiments_dir = (args.experiments_dir or paper_root / "experiments").resolve()
    tables_dir = (args.tables_dir or paper_root / "tables").resolve()

    try:
        main_path, failure_path = generate_paper_tables(
            experiments_dir=experiments_dir,
            tables_dir=tables_dir,
        )
    except GeneratorError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"wrote {main_path}")
    print(f"wrote {failure_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
