#!/usr/bin/env python3
"""
Generate paper-ready LaTeX tables from diagnostic granularity pilot experiments.

Reads pilot outputs under <paper-root>/experiments/ (read-only on runs/).
Writes:
  <paper-root>/tables/main_results.tex
  <paper-root>/tables/repair_outcomes.tex
  <paper-root>/tables/failure_analysis.tex
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

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

MAIN_RESULTS_TEX = "main_results.tex"
REPAIR_OUTCOMES_TEX = "repair_outcomes.tex"
FAILURE_ANALYSIS_TEX = "failure_analysis.tex"

SUMMARY_JSON = "diagnostic_granularity_summary.json"

FAILURE_CLASS_COLUMNS = (
    "duplicate_transition",
    "missing_state",
    "transition_not_found",
    "invalid_operation_semantics",
)


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


def format_regression_rate(value: float | None) -> str:
    if value is None:
        return "---"
    return f"{100.0 * value:.1f}\\%"


def load_pilot_summary(pilot_dir: Path) -> dict[str, Any]:
    path = pilot_dir / SUMMARY_JSON
    if not path.is_file():
        raise GeneratorError(f"missing {SUMMARY_JSON} in {pilot_dir}")
    return json.loads(path.read_text(encoding="utf-8"))


def collect_main_results_rows(experiments_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for variant, pilot_name in PILOT_VARIANTS:
        pilot_dir = experiments_dir / pilot_name
        if not pilot_dir.is_dir():
            raise GeneratorError(f"pilot directory not found: {pilot_dir}")
        summary = load_pilot_summary(pilot_dir)
        for condition in CONDITION_LABELS:
            stats = summary["per_condition"][condition]
            rows.append(
                {
                    "variant": variant,
                    "condition": condition,
                    "cases_evaluated": stats["cases_evaluated"],
                    "cases_failed": stats["cases_failed"],
                    "mean_delta_bpr": stats["mean_delta_bpr"],
                    "regression_rate": stats["regression_rate"],
                }
            )
    return rows


def collect_repair_outcomes_rows(experiments_dir: Path) -> list[dict[str, Any]]:
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
                    "improved_count": stats["improved_count"],
                    "unchanged_count": stats["unchanged_count"],
                    "degraded_count": stats["degraded_count"],
                    "effective_repair_count": stats["effective_repair_count"],
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
                "duplicate_transition": by_class.get("duplicate_transition", 0),
                "missing_state": by_class.get("missing_state", 0),
                "transition_not_found": by_class.get("transition_not_found", 0),
                "invalid_operation_semantics": by_class.get(
                    "invalid_operation_semantics", 0
                ),
            }
        )
    return rows


def file_header(tool: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return (
        f"% Auto-generated by {tool}\n"
        f"% Generated at {ts} (UTC)\n"
        f"% Requires \\usepackage{{booktabs,tabularx}}\n"
        "\n"
    )


def wrap_table(
    *,
    caption: str,
    label: str,
    column_spec: str,
    header: str,
    body_rows: list[str],
    tabcolsep: str = "3.5pt",
    tabularx_width: str = r"\linewidth",
    center_makebox: bool = False,
    use_tabular_star: bool = False,
) -> str:
    if use_tabular_star:
        begin_table = f"\\begin{{tabular*}}{{{tabularx_width}}}{{{column_spec}}}"
        end_table = r"\end{tabular*}"
    else:
        begin_table = f"\\begin{{tabularx}}{{{tabularx_width}}}{{{column_spec}}}"
        end_table = r"\end{tabularx}"
    tabular_block = [
        rf"\setlength{{\tabcolsep}}{{{tabcolsep}}}",
        begin_table,
        r"\toprule",
        header + r" \\",
        r"\midrule",
        *body_rows,
        r"\bottomrule",
        end_table,
    ]
    if center_makebox:
        body_lines = [r"\makebox[\linewidth][c]{%", *tabular_block, r"}%"]
    else:
        body_lines = tabular_block
    lines = [
        r"\begin{table}[t]",
        r"\centering",
        f"\\caption{{{caption}}}",
        f"\\label{{{label}}}",
        r"\footnotesize",
        *body_lines,
        r"\end{table}",
    ]
    return "\n".join(lines) + "\n"


def render_main_results_table(rows: list[dict[str, Any]]) -> str:
    body = [
        " & ".join(
            [
                escape_latex(row["variant"]),
                row["condition"],
                str(row["cases_evaluated"]),
                str(row["cases_failed"]),
                format_delta_bpr(row["mean_delta_bpr"]),
                format_regression_rate(row["regression_rate"]),
            ]
        )
        + r" \\"
        for row in rows
    ]
    return wrap_table(
        caption=(
            "Descriptive pilot summary of protocol executability readouts and mean "
            "validation \\BPR{} change by variant and condition. "
            "Arms were frozen separately; cross-arm contrasts are descriptive only."
        ),
        label="tab:main_results",
        column_spec=(
            "@{\\extracolsep{\\fill}}"
            ">{\\raggedright\\hyphenpenalty=10000\\exhyphenpenalty=10000\\arraybackslash}"
            "p{2.72cm} c r r r r@{}"
        ),
        header=(
            "Variant & Cond. & Eval. & Fail. & Mean $\\Delta$BPR & Regr.\\ (\\%)"
        ),
        body_rows=body,
        tabularx_width=r"0.96\linewidth",
        center_makebox=True,
        use_tabular_star=True,
    )


def render_repair_outcomes_table(rows: list[dict[str, Any]]) -> str:
    body = [
        " & ".join(
            [
                escape_latex(row["variant"]),
                row["condition"],
                str(row["improved_count"]),
                str(row["unchanged_count"]),
                str(row["degraded_count"]),
                str(row["effective_repair_count"]),
            ]
        )
        + r" \\"
        for row in rows
    ]
    return wrap_table(
        caption=(
            "Descriptive pilot summary of protocol effectiveness readouts on evaluated "
            "slots by variant and condition. "
            "Arms were frozen separately; cross-arm contrasts are descriptive only."
        ),
        label="tab:repair_outcomes",
        column_spec=(
            "@{\\extracolsep{\\fill}}"
            ">{\\raggedright\\hyphenpenalty=10000\\exhyphenpenalty=10000\\arraybackslash}"
            "p{3.05cm} c r r r r@{}"
        ),
        header="Variant & Cond. & Impr. & Unch. & Degr. & Eff.",
        body_rows=body,
        tabcolsep="5pt",
        tabularx_width=r"\linewidth",
        center_makebox=True,
        use_tabular_star=True,
    )


def render_failure_analysis_table(rows: list[dict[str, Any]]) -> str:
    body = [
        " & ".join(
            [
                escape_latex(row["variant"]),
                str(row["duplicate_transition"]),
                str(row["missing_state"]),
                str(row["transition_not_found"]),
                str(row["invalid_operation_semantics"]),
            ]
        )
        + r" \\"
        for row in rows
    ]
    return wrap_table(
        caption=(
            "Descriptive pilot summary of patch-engine rejections by variant. "
            "Counts are pooled over \\condC--\\condE{} and do not support "
            "condition-level inference."
        ),
        label="tab:failure_analysis",
        column_spec=(
            "@{}>{\\raggedright\\arraybackslash}p{1.55cm}"
            "*{4}{>{\\centering\\arraybackslash}X}@{}"
        ),
        header=(
            "Variant & \\shortstack{Duplicate\\\\trans.} & "
            "\\shortstack{Missing\\\\state} & "
            "\\shortstack{Trans.\\\\not found} & "
            "\\shortstack{Invalid\\\\semantics}"
        ),
        body_rows=body,
        tabcolsep="3pt",
    )


def generate_paper_tables(
    *,
    experiments_dir: Path,
    tables_dir: Path,
) -> tuple[Path, Path, Path]:
    experiments_dir = experiments_dir.resolve()
    tables_dir = tables_dir.resolve()
    if not experiments_dir.is_dir():
        raise GeneratorError(f"experiments directory not found: {experiments_dir}")

    main_rows = collect_main_results_rows(experiments_dir)
    outcome_rows = collect_repair_outcomes_rows(experiments_dir)
    failure_rows = collect_failure_analysis_rows(experiments_dir)

    tables_dir.mkdir(parents=True, exist_ok=True)
    tool = "scripts/generate_paper_tables.py"
    header = file_header(tool)

    main_path = tables_dir / MAIN_RESULTS_TEX
    outcomes_path = tables_dir / REPAIR_OUTCOMES_TEX
    failure_path = tables_dir / FAILURE_ANALYSIS_TEX

    main_path.write_text(header + render_main_results_table(main_rows), encoding="utf-8")
    outcomes_path.write_text(
        header + render_repair_outcomes_table(outcome_rows), encoding="utf-8"
    )
    failure_path.write_text(
        header + render_failure_analysis_table(failure_rows), encoding="utf-8"
    )
    return main_path, outcomes_path, failure_path


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
        main_path, outcomes_path, failure_path = generate_paper_tables(
            experiments_dir=experiments_dir,
            tables_dir=tables_dir,
        )
    except GeneratorError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"wrote {main_path}")
    print(f"wrote {outcomes_path}")
    print(f"wrote {failure_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
