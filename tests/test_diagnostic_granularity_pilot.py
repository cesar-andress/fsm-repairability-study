"""Tests for diagnostic granularity pilot (Ollama mocked)."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from unittest import mock

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
CASE_DIR = REPO_ROOT / "tests" / "fixtures" / "dry_run_case"
OLLAMA_FIXTURES = REPO_ROOT / "tests" / "fixtures" / "ollama"
SCRIPTS = REPO_ROOT / "scripts"

sys.path.insert(0, str(SCRIPTS))
from run_diagnostic_granularity_pilot import (  # noqa: E402
    GRANULARITY_CONDITIONS,
    _best_condition_label,
    aggregate_summary,
    run_diagnostic_granularity_pilot,
)

RAW_PATCH = (OLLAMA_FIXTURES / "raw_patch_fenced.txt").read_text(encoding="utf-8")


@mock.patch("generate_patch_ollama.generate", return_value=RAW_PATCH)
def test_granularity_pilot_three_conditions(mock_generate, tmp_path: Path) -> None:
    out = tmp_path / "granularity"
    summary, rows = run_diagnostic_granularity_pilot(
        cases_dir=CASE_DIR,
        model="test-model",
        max_cases=1,
        output_dir=out,
    )
    assert mock_generate.call_count == 3

    assert len(rows) == 1
    row = rows[0]
    assert row.case_id == "dry_run_case"
    assert row.initial_bpr == pytest.approx(2 / 3)
    for label in GRANULARITY_CONDITIONS:
        assert row.status[label] == "ok"
        assert row.final_bpr[label] == 1.0
        assert row.delta[label] == pytest.approx(1 / 3)

    csv_path = out / "diagnostic_granularity_results.csv"
    assert csv_path.is_file()
    with csv_path.open(encoding="utf-8") as f:
        csv_rows = list(csv.DictReader(f))
    assert csv_rows[0]["case_id"] == "dry_run_case"
    assert float(csv_rows[0]["delta_D"]) == pytest.approx(1 / 3)
    assert csv_rows[0]["best_condition"] in {"C", "D", "E", "C+D", "C+D+E", "C+E", "D+E"}

    assert (out / "diagnostic_granularity_summary.json").is_file()
    for label in GRANULARITY_CONDITIONS:
        pc = summary["per_condition"][label]
        assert pc["mean_delta_bpr"] == pytest.approx(1 / 3)
        assert pc["complete_repair_rate"] == 1.0
        assert pc["regression_rate"] == 0.0


def test_best_condition_picks_highest_delta() -> None:
    from run_diagnostic_granularity_pilot import GranularityCaseRow  # noqa: E402

    row = GranularityCaseRow(
        case_id="x",
        delta={"C": 0.1, "D": 0.3, "E": 0.2},
    )
    assert _best_condition_label(row) == "D"


def test_aggregate_summary_empty() -> None:
    summary = aggregate_summary(
        [],
        model="m",
        cases_dir=CASE_DIR,
        output_dir=Path("/tmp/out"),
        iteration_budget=1,
        started_at="2026-06-03T10:00:00Z",
        completed_at="2026-06-03T11:00:00Z",
    )
    assert summary["per_condition"]["C"]["mean_delta_bpr"] is None
    assert summary["per_condition"]["C"]["complete_repair_rate"] is None
