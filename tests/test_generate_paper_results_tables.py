"""Tests for paper LaTeX table generation."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
PAPER_ROOT = REPO_ROOT.parent / "paper"
PAPER_EXPERIMENTS = PAPER_ROOT / "experiments"

sys.path.insert(0, str(SCRIPTS))
from generate_paper_results_tables import (  # noqa: E402
    GeneratorError,
    collect_failure_analysis_rows,
    collect_main_results_rows,
    escape_latex,
    format_delta_bpr,
    generate_paper_tables,
    render_failure_analysis_table,
    render_main_results_table,
)


def _latex_is_balanced(tex: str) -> bool:
    """Rough check that tabular/table environments are balanced."""
    for env in ("table", "tabular"):
        opens = len(re.findall(rf"\\begin\{{{env}\}}", tex))
        closes = len(re.findall(rf"\\end\{{{env}\}}", tex))
        assert opens == closes == 1, f"unbalanced {env}: {opens} opens, {closes} closes"


def test_escape_latex_special_chars() -> None:
    assert escape_latex("a_b") == r"a\_b"
    assert escape_latex("100%") == r"100\%"


def test_format_delta_bpr() -> None:
    assert format_delta_bpr(0.0392) == "$+0.039$"
    assert format_delta_bpr(-0.042) == "$-0.042$"
    assert format_delta_bpr(None) == "---"


def test_render_main_results_valid_tabular() -> None:
    rows = [
        {
            "variant": "default",
            "condition": "E",
            "cases_evaluated": 9,
            "improved_count": 3,
            "degraded_count": 0,
            "mean_delta_bpr": 0.03921568627450981,
        }
    ]
    tex = render_main_results_table(rows)
    _latex_is_balanced(tex)
    assert r"\toprule" in tex
    assert r"\bottomrule" in tex
    assert "default & E & 9 & 3 & 0 & $+0.039$ \\" in tex


def test_render_failure_analysis_valid_tabular() -> None:
    rows = [
        {
            "variant": "operation-aware",
            "patch_failures": 55,
            "duplicate_transition": 41,
            "missing_state": 1,
            "transition_not_found": 7,
            "invalid_operation_semantics": 6,
        }
    ]
    tex = render_failure_analysis_table(rows)
    _latex_is_balanced(tex)
    assert "operation-aware & 55 & 41 & 1 & 7 & 6 \\" in tex


def test_generate_from_fixture_pilots(tmp_path: Path) -> None:
    experiments = tmp_path / "experiments"
    tables = tmp_path / "tables"

    repair_fixture = REPO_ROOT / "tests" / "fixtures" / "repair_outcome_pilot"
    patch_fixture = REPO_ROOT / "tests" / "fixtures" / "patch_failure_pilot"

    default_dir = experiments / "frozen_pilot_001"
    aware_dir = experiments / "diagnostic_granularity_pilot_diverse_operation_aware_001"
    inferred_dir = experiments / "frozen_main_pilot_001"

    for target in (default_dir, aware_dir, inferred_dir):
        target.mkdir(parents=True)
        # Symlink runs + csv from fixtures (copy minimal tree for patch + repair)
        if target == default_dir:
            src_repair, src_patch = repair_fixture, patch_fixture
        elif target == aware_dir:
            src_repair, src_patch = repair_fixture, patch_fixture
        else:
            src_repair, src_patch = repair_fixture, patch_fixture

        (target / "runs").symlink_to(src_repair / "runs", target_is_directory=True)
        csv_name = "diagnostic_granularity_results.csv"
        if (src_patch / csv_name).is_file():
            (target / csv_name).symlink_to(src_patch / csv_name)

    main_path, failure_path = generate_paper_tables(
        experiments_dir=experiments,
        tables_dir=tables,
    )
    assert main_path.is_file()
    assert failure_path.is_file()
    main_tex = main_path.read_text(encoding="utf-8")
    failure_tex = failure_path.read_text(encoding="utf-8")
    _latex_is_balanced(main_tex)
    _latex_is_balanced(failure_tex)
    assert main_tex.count(r"\\") >= 9
    assert failure_tex.count("default &") == 1


def test_collect_main_results_requires_pilot(tmp_path: Path) -> None:
    with pytest.raises(GeneratorError, match="not found"):
        collect_main_results_rows(tmp_path / "experiments")


@pytest.mark.skipif(
    not (PAPER_EXPERIMENTS / "frozen_pilot_001").is_dir(),
    reason="paper experiments not present",
)
def test_generate_paper_tables_matches_known_e_counts(tmp_path: Path) -> None:
    tables = tmp_path / "tables"
    generate_paper_tables(experiments_dir=PAPER_EXPERIMENTS, tables_dir=tables)
    rows = collect_main_results_rows(PAPER_EXPERIMENTS)
    by_key = {(r["variant"], r["condition"]): r for r in rows}
    assert by_key[("default", "E")]["cases_evaluated"] == 9
    assert by_key[("operation-aware", "E")]["cases_evaluated"] == 13
    assert by_key[("operation-inferred", "E")]["cases_evaluated"] == 23


@pytest.mark.skipif(
    not (PAPER_EXPERIMENTS / "frozen_pilot_001").is_dir(),
    reason="paper experiments not present",
)
def test_failure_analysis_paper_pilots_totals() -> None:
    rows = collect_failure_analysis_rows(PAPER_EXPERIMENTS)
    by_variant = {r["variant"]: r for r in rows}
    assert by_variant["default"]["patch_failures"] == 64
    assert by_variant["default"]["duplicate_transition"] == 47
    assert by_variant["operation-inferred"]["patch_failures"] == 45
    assert by_variant["operation-inferred"]["duplicate_transition"] == 35
