"""Tests for repair outcome analysis (read-only pilot inspection)."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PILOT_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "repair_outcome_pilot"
SCRIPTS = REPO_ROOT / "scripts"
PAPER_EXPERIMENTS = REPO_ROOT.parent / "paper" / "experiments"

PAPER_PILOTS = {
    "frozen_pilot_001": PAPER_EXPERIMENTS / "frozen_pilot_001",
    "operation_aware": PAPER_EXPERIMENTS
    / "diagnostic_granularity_pilot_diverse_operation_aware_001",
    "frozen_main_pilot_001": PAPER_EXPERIMENTS / "frozen_main_pilot_001",
}

sys.path.insert(0, str(SCRIPTS))
from analyze_repair_outcomes import (  # noqa: E402
    AnalysisError,
    analyze_repair_outcomes,
    parse_repair_run,
    write_outputs,
)


def _fixture_snapshot() -> dict[str, str]:
    snap: dict[str, str] = {}
    for path in sorted(PILOT_FIXTURE.rglob("*")):
        if path.is_file() and "analysis" not in path.parts:
            snap[str(path.relative_to(PILOT_FIXTURE))] = path.read_text(encoding="utf-8")
    return snap


def test_improved_outcome_counted(tmp_path: Path) -> None:
    summary = analyze_repair_outcomes(PILOT_FIXTURE)
    c = summary["per_condition"]["C"]
    assert c["cases_evaluated"] == 2
    assert c["improved_count"] == 1
    assert c["unchanged_count"] == 1
    assert c["degraded_count"] == 0


def test_degraded_outcome_counted(tmp_path: Path) -> None:
    summary = analyze_repair_outcomes(PILOT_FIXTURE)
    d = summary["per_condition"]["D"]
    assert d["degraded_count"] == 1
    assert d["improved_count"] == 1


def test_unchanged_outcome_counted(tmp_path: Path) -> None:
    summary = analyze_repair_outcomes(PILOT_FIXTURE)
    c = summary["per_condition"]["C"]
    assert c["unchanged_count"] == 1
    assert c["mean_delta_bpr"] == pytest.approx(0.125, rel=1e-6)


def test_missing_repair_run_not_evaluated(tmp_path: Path) -> None:
    summary = analyze_repair_outcomes(PILOT_FIXTURE)
    e = summary["per_condition"]["E"]
    assert e["cases_attempted"] == 2
    assert e["cases_evaluated"] == 1
    assert e["improved_count"] == 1


def test_failed_run_directory_without_repair_run(tmp_path: Path) -> None:
    """Condition dir exists (attempted) but pipeline left no repair_run.json."""
    summary = analyze_repair_outcomes(PILOT_FIXTURE)
    e = summary["per_condition"]["E"]
    assert e["cases_attempted"] - e["cases_evaluated"] == 1


def test_complete_and_effective_repair_flags(tmp_path: Path) -> None:
    summary = analyze_repair_outcomes(PILOT_FIXTURE)
    assert summary["per_condition"]["D"]["complete_repair_count"] == 1
    assert summary["per_condition"]["E"]["effective_repair_count"] == 1


def test_analyze_does_not_modify_pilot_fixture(tmp_path: Path) -> None:
    before = _fixture_snapshot()
    summary = analyze_repair_outcomes(PILOT_FIXTURE)
    write_outputs(PILOT_FIXTURE, summary, output_dir=tmp_path)
    after = _fixture_snapshot()
    assert before == after
    assert not (PILOT_FIXTURE / "analysis").exists()


def test_write_outputs_json_and_csv(tmp_path: Path) -> None:
    summary = analyze_repair_outcomes(PILOT_FIXTURE)
    json_path, csv_path = write_outputs(
        PILOT_FIXTURE, summary, output_dir=tmp_path / "analysis"
    )
    doc = json.loads(json_path.read_text(encoding="utf-8"))
    assert set(doc["per_condition"]) == {"C", "D", "E"}
    assert doc["per_condition"]["C"]["cases_attempted"] == 2

    with csv_path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 3
    assert rows[0]["condition"] == "C"
    assert int(rows[0]["improved_count"]) == 1


def test_parse_repair_run_returns_none_for_invalid(tmp_path: Path) -> None:
    bad = tmp_path / "repair_run.json"
    bad.write_text("{not json", encoding="utf-8")
    assert parse_repair_run(bad, condition="C", case_id="x") is None


def test_missing_runs_dir_raises() -> None:
    with pytest.raises(AnalysisError, match="missing runs"):
        analyze_repair_outcomes(REPO_ROOT / "tests" / "fixtures" / "dry_run_case")


@pytest.mark.parametrize(
    "pilot_key,expected_evaluated_e",
    [
        ("frozen_pilot_001", 9),
        ("operation_aware", 13),
        ("frozen_main_pilot_001", 23),
    ],
)
def test_paper_pilot_dirs_aggregate_condition_e(
    pilot_key: str, expected_evaluated_e: int
) -> None:
    pilot_dir = PAPER_PILOTS[pilot_key]
    if not pilot_dir.is_dir():
        pytest.skip(f"paper pilot not present: {pilot_dir}")
    summary = analyze_repair_outcomes(pilot_dir)
    assert summary["per_condition"]["E"]["cases_evaluated"] == expected_evaluated_e
    assert summary["per_condition"]["E"]["cases_attempted"] == 30
