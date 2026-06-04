"""Tests for generate_paper_tables LaTeX output."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
PAPER_ROOT = REPO_ROOT.parent / "paper"
PAPER_EXPERIMENTS = PAPER_ROOT / "experiments"

sys.path.insert(0, str(SCRIPTS))
from generate_paper_tables import (  # noqa: E402
    GeneratorError,
    collect_failure_analysis_rows,
    collect_main_results_rows,
    collect_repair_outcomes_rows,
    escape_latex,
    format_delta_bpr,
    format_regression_rate,
    generate_paper_tables,
    render_failure_analysis_table,
    render_main_results_table,
    render_repair_outcomes_table,
)


def _latex_is_balanced(tex: str) -> None:
    for env in ("table", "tabular"):
        opens = len(re.findall(rf"\\begin\{{{env}\}}", tex))
        closes = len(re.findall(rf"\\end\{{{env}\}}", tex))
        assert opens == closes == 1, f"unbalanced {env}: {opens} vs {closes}"


def _minimal_pilot_summary() -> dict:
    per = {
        label: {
            "cases_evaluated": 2 if label == "C" else 1,
            "cases_failed": 1 if label == "C" else 2,
            "mean_delta_bpr": -0.04 if label == "C" else 0.0,
            "regression_rate": 0.25 if label == "C" else 0.0,
        }
        for label in ("C", "D", "E")
    }
    return {"per_condition": per}


def test_format_helpers() -> None:
    assert format_delta_bpr(0.0392) == "$+0.039$"
    assert format_regression_rate(0.25) == r"25.0\%"
    assert escape_latex("x_y") == r"x\_y"


def test_render_main_results_compiles_structurally() -> None:
    rows = [
        {
            "variant": "default",
            "condition": "E",
            "cases_evaluated": 9,
            "cases_failed": 21,
            "mean_delta_bpr": 0.03921568627450981,
            "regression_rate": 0.0,
        }
    ]
    tex = render_main_results_table(rows)
    _latex_is_balanced(tex)
    assert r"\toprule" in tex and r"\bottomrule" in tex
    assert "default & E & 9 & 21 & $+0.039$ & 0.0\\%" in tex


def test_render_repair_outcomes_table() -> None:
    rows = [
        {
            "variant": "operation-inferred",
            "condition": "E",
            "improved_count": 3,
            "unchanged_count": 20,
            "degraded_count": 0,
            "effective_repair_count": 3,
        }
    ]
    tex = render_repair_outcomes_table(rows)
    _latex_is_balanced(tex)
    assert "operation-inferred & E & 3 & 20 & 0 & 3 \\" in tex


def test_render_failure_analysis_table() -> None:
    rows = [
        {
            "variant": "default",
            "duplicate_transition": 47,
            "missing_state": 6,
            "transition_not_found": 3,
            "invalid_operation_semantics": 8,
        }
    ]
    tex = render_failure_analysis_table(rows)
    _latex_is_balanced(tex)
    assert "default & 47 & 6 & 3 & 8 \\" in tex
    assert "Patch failures" not in tex


def test_generate_from_synthetic_experiments(tmp_path: Path) -> None:
    experiments = tmp_path / "experiments"
    tables = tmp_path / "tables"
    repair_fixture = REPO_ROOT / "tests" / "fixtures" / "repair_outcome_pilot"
    patch_fixture = REPO_ROOT / "tests" / "fixtures" / "patch_failure_pilot"

    for pilot_name in (
        "frozen_pilot_001",
        "diagnostic_granularity_pilot_diverse_operation_aware_001",
        "frozen_main_pilot_001",
    ):
        pilot_dir = experiments / pilot_name
        pilot_dir.mkdir(parents=True)
        (pilot_dir / "runs").symlink_to(
            repair_fixture / "runs", target_is_directory=True
        )
        csv_src = patch_fixture / "diagnostic_granularity_results.csv"
        if csv_src.is_file():
            (pilot_dir / csv_src.name).symlink_to(csv_src)
        (pilot_dir / "diagnostic_granularity_summary.json").write_text(
            json.dumps(_minimal_pilot_summary()), encoding="utf-8"
        )

    main_path, outcomes_path, failure_path = generate_paper_tables(
        experiments_dir=experiments,
        tables_dir=tables,
    )
    for path in (main_path, outcomes_path, failure_path):
        assert path.is_file()
        _latex_is_balanced(path.read_text(encoding="utf-8"))

    assert main_path.name == "main_results.tex"
    assert outcomes_path.name == "repair_outcomes.tex"
    assert failure_path.name == "failure_analysis.tex"


def test_collect_main_results_requires_summary(tmp_path: Path) -> None:
    pilot = tmp_path / "frozen_pilot_001"
    pilot.mkdir()
    with pytest.raises(GeneratorError, match="missing"):
        collect_main_results_rows(tmp_path)


@pytest.mark.skipif(
    not (PAPER_EXPERIMENTS / "frozen_pilot_001").is_dir(),
    reason="paper experiments not present",
)
def test_paper_experiments_main_results_e_row() -> None:
    rows = collect_main_results_rows(PAPER_EXPERIMENTS)
    key = {("default", "E"), ("operation-aware", "E"), ("operation-inferred", "E")}
    got = {(r["variant"], r["condition"]) for r in rows}
    assert key <= got
    by = {(r["variant"], r["condition"]): r for r in rows}
    assert by[("default", "E")]["cases_evaluated"] == 9
    assert by[("default", "E")]["cases_failed"] == 21
    assert by[("operation-inferred", "E")]["cases_evaluated"] == 23


@pytest.mark.skipif(
    not (PAPER_EXPERIMENTS / "frozen_pilot_001").is_dir(),
    reason="paper experiments not present",
)
def test_paper_experiments_failure_and_outcomes() -> None:
    outcomes = collect_repair_outcomes_rows(PAPER_EXPERIMENTS)
    failures = collect_failure_analysis_rows(PAPER_EXPERIMENTS)
    ob = {(r["variant"], r["condition"]): r for r in outcomes}
    assert ob[("operation-inferred", "E")]["effective_repair_count"] == 3
    fb = {r["variant"]: r for r in failures}
    assert fb["default"]["duplicate_transition"] == 47
    assert fb["operation-aware"]["duplicate_transition"] == 41
