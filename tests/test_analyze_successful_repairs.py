"""Tests for effective-repair characterization utility."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PILOT_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "successful_repairs_pilot"
PAPER_PILOT = REPO_ROOT.parent / "paper" / "experiments" / "frozen_pilot_001"
SCRIPTS = REPO_ROOT / "scripts"

sys.path.insert(0, str(SCRIPTS))
from analyze_successful_repairs import (  # noqa: E402
    AnalysisError,
    analyze_successful_repairs,
    categories_fixed,
    fixed_test_ids,
    write_outputs,
)


def test_categories_fixed_detects_reduction() -> None:
    pre = {"trace_failures": 2, "rejection_failures": 1}
    post = {"trace_failures": 1, "rejection_failures": 1}
    assert categories_fixed(pre, post) == ["trace_failures"]


def test_compute_tests_fixed_ids() -> None:
    before = {"failures": [{"test_id": "a"}, {"test_id": "b"}]}
    after = {"failures": [{"test_id": "b"}]}
    assert fixed_test_ids(before, after) == ["a"]


def test_analyze_extracts_effective_repair(tmp_path: Path) -> None:
    records, summary = analyze_successful_repairs(PILOT_FIXTURE)
    assert len(records) == 1
    rec = records[0]
    assert rec.system_id == "bike_sys"
    assert rec.condition == "E"
    assert rec.model == "qwen2.5-coder:7b"
    assert rec.patch_operation_count == 1
    assert rec.operation_types == ["add_transition"]
    assert rec.delta_bpr == pytest.approx(0.25)
    assert rec.tests_fixed == ["t1"]
    assert "trace_failures" in rec.failure_categories_fixed

    assert summary["aggregates"]["effective_repair_count"] == 1
    assert summary["aggregates"]["by_condition"]["E"] == 1


def test_non_effective_run_excluded() -> None:
    records, _ = analyze_successful_repairs(PILOT_FIXTURE)
    assert all(r.condition != "C" for r in records)


def test_write_outputs_csv_json(tmp_path: Path) -> None:
    records, summary = analyze_successful_repairs(PILOT_FIXTURE)
    csv_path, json_path = write_outputs(
        PILOT_FIXTURE, records, summary, output_dir=tmp_path
    )
    with csv_path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["operation_types"] == "add_transition"
    doc = json.loads(json_path.read_text(encoding="utf-8"))
    assert len(doc["repairs"]) == 1
    assert doc["aggregates"]["mean_delta_bpr"] == pytest.approx(0.25)


def test_missing_runs_dir_raises(tmp_path: Path) -> None:
    with pytest.raises(AnalysisError, match="missing runs"):
        analyze_successful_repairs(tmp_path / "empty")


@pytest.mark.skipif(not PAPER_PILOT.is_dir(), reason="paper pilot not present")
def test_frozen_pilot_effective_repair_count() -> None:
    _records, summary = analyze_successful_repairs(PAPER_PILOT)
    n = summary["aggregates"]["effective_repair_count"]
    assert n >= 1
    assert summary["aggregates"]["by_model"].get("qwen2.5-coder:7b", 0) == n
