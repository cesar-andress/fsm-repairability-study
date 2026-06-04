"""Tests for replication package builder."""

from __future__ import annotations

import json
import zipfile
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
PAPER_ROOT = REPO_ROOT.parent / "paper"

sys.path.insert(0, str(SCRIPTS))
from package_replication_bundle import (  # noqa: E402
    PackageError,
    dedupe_selection,
    package_replication_bundle,
    SelectedRun,
)


def _write_minimal_paper_tree(root: Path) -> None:
    results = root / "results"
    results.mkdir(parents=True)
    (results / "main_results_table.csv").write_text(
        "variant,condition,evaluated\n", encoding="utf-8"
    )
    (root / "tables").mkdir()
    (root / "tables" / "main_results.tex").write_text("% table\n", encoding="utf-8")
    (root / "figures").mkdir()
    (root / "figures" / "fig.pdf").write_bytes(b"%PDF-1.4\n")

    for slug, folder in (
        ("frozen_pilot_001", "frozen_pilot_001"),
        (
            "operation_aware_001",
            "diagnostic_granularity_pilot_diverse_operation_aware_001",
        ),
        ("frozen_main_pilot_001", "frozen_main_pilot_001"),
    ):
        pilot = root / "experiments" / folder
        pilot.mkdir(parents=True)
        (pilot / "diagnostic_granularity_summary.json").write_text(
            json.dumps({"per_condition": {}}), encoding="utf-8"
        )
        analysis = pilot / "analysis"
        analysis.mkdir()
        (analysis / "successful_repairs.json").write_text(
            json.dumps(
                {
                    "repairs": [
                        {
                            "case_id": f"repair__fixture__{slug}__r01",
                            "condition": "E",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        (analysis / "regression_summary.json").write_text(
            json.dumps({"regressions": []}), encoding="utf-8"
        )
        cond_dir = (
            pilot
            / "runs"
            / f"repair__fixture__{slug}__r01"
            / "E"
        )
        cond_dir.mkdir(parents=True)
        (cond_dir / "repair_run.json").write_text(
            json.dumps(
                {
                    "identity": {"system_id": "fixture"},
                    "execution": {"model_name": "test"},
                    "iterations": [{"input_bpr_validation": 0.5}],
                    "outcome": {"final_bpr_validation": 0.6, "effective_repair": True},
                }
            ),
            encoding="utf-8",
        )
        (cond_dir / "run" / "patches").mkdir(parents=True)
        (cond_dir / "run" / "patches" / "iter_000_source.json").write_text(
            '{"operations":[]}', encoding="utf-8"
        )


def test_dedupe_selection() -> None:
    runs = [
        SelectedRun("p1", "c1", "E", "effective_repair"),
        SelectedRun("p1", "c1", "E", "effective_repair"),
    ]
    assert len(dedupe_selection(runs)) == 1


def test_package_creates_bundle_and_zip(tmp_path: Path) -> None:
    paper = tmp_path / "paper"
    _write_minimal_paper_tree(paper)
    bundle = tmp_path / "replication_package"
    zpath = tmp_path / "replication_package.zip"

    out_dir, out_zip = package_replication_bundle(
        paper_root=paper,
        bundle_dir=bundle,
        zip_path=zpath,
        study_repo=REPO_ROOT,
    )
    assert out_dir.is_dir()
    assert (out_dir / "README.md").is_file()
    assert (out_dir / "metadata.json").is_file()
    assert (out_dir / "summaries" / "main_results_table.csv").is_file()
    assert (out_dir / "tables" / "main_results.tex").is_file()
    assert (out_dir / "repair_runs" / "frozen_pilot_001").is_dir()

    meta = json.loads((out_dir / "metadata.json").read_text(encoding="utf-8"))
    assert meta["upload_target"] == "Zenodo"
    assert meta["selected_repair_run_count"] >= 1

    assert out_zip.is_file()
    with zipfile.ZipFile(out_zip) as zf:
        names = zf.namelist()
    assert any(n.endswith("README.md") for n in names)
    assert any("replication_package/metadata.json" in n for n in names)


def test_missing_experiments_raises(tmp_path: Path) -> None:
    paper = tmp_path / "paper"
    paper.mkdir()
    with pytest.raises(PackageError, match="missing experiments"):
        package_replication_bundle(
            paper_root=paper,
            bundle_dir=tmp_path / "bundle",
            zip_path=tmp_path / "bundle.zip",
            study_repo=REPO_ROOT,
        )


@pytest.mark.skipif(not PAPER_ROOT.is_dir(), reason="paper tree not present")
def test_package_real_paper_tree(tmp_path: Path) -> None:
    bundle = tmp_path / "replication_package"
    zpath = tmp_path / "replication_package.zip"
    package_replication_bundle(
        paper_root=PAPER_ROOT,
        bundle_dir=bundle,
        zip_path=zpath,
        study_repo=REPO_ROOT,
    )
    meta = json.loads((bundle / "metadata.json").read_text(encoding="utf-8"))
    assert meta["selected_repair_run_count"] >= 3
    assert zpath.stat().st_size > 1000
