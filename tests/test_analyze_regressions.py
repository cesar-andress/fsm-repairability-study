"""Tests for behavioural regression analysis utility."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PILOT_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "regression_pilot"
PAPER_PILOT = REPO_ROOT.parent / "paper" / "experiments" / "frozen_pilot_001"
SCRIPTS = REPO_ROOT / "scripts"

sys.path.insert(0, str(SCRIPTS))
from analyze_regressions import (  # noqa: E402
    AnalysisError,
    analyze_regressions,
    extract_degraded_case,
    write_outputs,
)


def test_extract_degraded_case_from_fixture() -> None:
    cond_dir = (
        PILOT_FIXTURE
        / "runs"
        / "repair__fixture__access_sys__model__r01"
        / "C"
    )
    repair_run = json.loads((cond_dir / "repair_run.json").read_text(encoding="utf-8"))
    rec = extract_degraded_case(
        case_id="repair__fixture__access_sys__model__r01",
        path_label="C",
        cond_dir=cond_dir,
        repair_run=repair_run,
    )
    assert rec is not None
    assert rec.system_id == "access_sys"
    assert rec.condition == "C"
    assert rec.delta_bpr == pytest.approx(-0.2)
    assert rec.operation_types == ["update_transition"]
    assert rec.behavioural_degradation is True


def test_unchanged_bpr_excluded() -> None:
    cond_dir = (
        PILOT_FIXTURE
        / "runs"
        / "repair__fixture__access_sys__model__r01"
        / "E"
    )
    repair_run = json.loads((cond_dir / "repair_run.json").read_text(encoding="utf-8"))
    assert (
        extract_degraded_case(
            case_id="repair__fixture__access_sys__model__r01",
            path_label="E",
            cond_dir=cond_dir,
            repair_run=repair_run,
        )
        is None
    )


def test_analyze_and_write_outputs(tmp_path: Path) -> None:
    records, summary = analyze_regressions(PILOT_FIXTURE)
    assert len(records) == 1
    assert summary["aggregates"]["degraded_count"] == 1
    assert summary["aggregates"]["by_condition"]["C"] == 1
    assert summary["aggregates"]["mean_delta_bpr"] == pytest.approx(-0.2)

    csv_path, json_path = write_outputs(
        PILOT_FIXTURE, records, summary, output_dir=tmp_path
    )
    with csv_path.open(encoding="utf-8") as f:
        row = next(csv.DictReader(f))
    assert row["system_id"] == "access_sys"
    assert float(row["delta_bpr"]) < 0
    doc = json.loads(json_path.read_text(encoding="utf-8"))
    assert len(doc["regressions"]) == 1


def test_missing_runs_raises(tmp_path: Path) -> None:
    with pytest.raises(AnalysisError, match="missing runs"):
        analyze_regressions(tmp_path / "nope")


@pytest.mark.skipif(not PAPER_PILOT.is_dir(), reason="paper pilot not present")
def test_frozen_pilot_degraded_count() -> None:
    _records, summary = analyze_regressions(PAPER_PILOT)
    assert summary["aggregates"]["degraded_count"] == 3
    assert summary["aggregates"]["by_condition"]["C"] == 3
