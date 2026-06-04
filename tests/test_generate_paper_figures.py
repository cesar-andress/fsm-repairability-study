"""Tests for paper figure generation (matplotlib PDF output)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
PAPER_ROOT = REPO_ROOT.parent / "paper"
PAPER_EXPERIMENTS = PAPER_ROOT / "experiments"

pytest.importorskip("matplotlib")

sys.path.insert(0, str(SCRIPTS))
from generate_paper_figures import (  # noqa: E402
    FIG_EVALUATED,
    FIG_PATCH_FAILURE,
    FIG_REPAIR_SUCCESS,
    FigureGeneratorError,
    discover_variant_bundles,
    generate_paper_figures,
    load_main_results_csv,
    success_rate,
)


def _is_pdf(path: Path) -> bool:
    return path.read_bytes()[:4] == b"%PDF"


def _repair_outcome_fixture() -> dict:
    per = {
        label: {
            "cases_attempted": 30,
            "cases_evaluated": 10 if label == "E" else 5,
            "improved_count": 2 if label == "E" else 0,
            "unchanged_count": 8 if label == "E" else 5,
            "degraded_count": 0,
            "complete_repair_count": 0,
            "effective_repair_count": 2 if label == "E" else 0,
            "mean_delta_bpr": 0.01,
            "median_delta_bpr": 0.0,
        }
        for label in ("C", "D", "E")
    }
    return {"schema_version": "1.0.0", "per_condition": per}


def _patch_failure_fixture() -> dict:
    return {
        "schema_version": "1.0.0",
        "aggregates": {
            "total_failures": 10,
            "by_failure_class": {
                "duplicate_transition": 7,
                "missing_state": 1,
                "transition_not_found": 1,
                "invalid_operation_semantics": 1,
            },
        },
    }


def _write_pilot_analysis(pilot_dir: Path) -> None:
    analysis = pilot_dir / "analysis"
    analysis.mkdir(parents=True)
    (analysis / "repair_outcome_summary.json").write_text(
        json.dumps(_repair_outcome_fixture()), encoding="utf-8"
    )
    (analysis / "patch_failure_summary.json").write_text(
        json.dumps(_patch_failure_fixture()), encoding="utf-8"
    )


def _write_main_results_csv(path: Path) -> None:
    lines = [
        "variant,condition,evaluated,failed,patch_failures,abstentions,mean_delta,regression",
    ]
    for variant in ("default", "operation-aware", "operation-inferred"):
        for cond, ev in (("C", 5), ("D", 8), ("E", 12)):
            lines.append(f"{variant},{cond},{ev},0,0,0,0.0,0.0")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.fixture()
def synthetic_paper_tree(tmp_path: Path) -> tuple[Path, Path, Path]:
    results_csv = tmp_path / "results" / "main_results_table.csv"
    experiments = tmp_path / "experiments"
    figures = tmp_path / "figures"
    _write_main_results_csv(results_csv)
    for _variant, pilot_name in (
        ("default", "frozen_pilot_001"),
        ("operation-aware", "diagnostic_granularity_pilot_diverse_operation_aware_001"),
        ("operation-inferred", "frozen_main_pilot_001"),
    ):
        _write_pilot_analysis(experiments / pilot_name)
    return results_csv, experiments, figures


def test_success_rate_from_fixture(synthetic_paper_tree: tuple[Path, Path, Path]) -> None:
    _csv, experiments, _fig = synthetic_paper_tree
    bundles = discover_variant_bundles(experiments)
    default = next(b for b in bundles if b.variant == "default")
    assert success_rate(default, "E") == pytest.approx(0.2)


def test_generate_writes_valid_pdfs(synthetic_paper_tree: tuple[Path, Path, Path]) -> None:
    results_csv, experiments, figures = synthetic_paper_tree
    paths = generate_paper_figures(
        main_results_csv=results_csv,
        experiments_dir=experiments,
        figures_dir=figures,
    )
    assert paths[0].name == FIG_REPAIR_SUCCESS
    assert paths[1].name == FIG_PATCH_FAILURE
    assert paths[2].name == FIG_EVALUATED
    for path in paths:
        assert path.stat().st_size > 500
        assert _is_pdf(path)


def test_missing_csv_raises(tmp_path: Path) -> None:
    with pytest.raises(FigureGeneratorError, match="missing CSV"):
        load_main_results_csv(tmp_path / "missing.csv")


def test_missing_analysis_json_raises(tmp_path: Path) -> None:
    pilot = tmp_path / "experiments" / "frozen_pilot_001"
    pilot.mkdir(parents=True)
    with pytest.raises(FigureGeneratorError, match="missing JSON"):
        discover_variant_bundles(tmp_path / "experiments")


@pytest.mark.skipif(
    not (PAPER_ROOT / "results" / "main_results_table.csv").is_file(),
    reason="paper results CSV not present",
)
def test_generate_from_paper_tree(tmp_path: Path) -> None:
    figures = tmp_path / "figures"
    paths = generate_paper_figures(
        main_results_csv=PAPER_ROOT / "results" / "main_results_table.csv",
        experiments_dir=PAPER_EXPERIMENTS,
        figures_dir=figures,
    )
    assert len(paths) == 3
    for path in paths:
        assert _is_pdf(path)
