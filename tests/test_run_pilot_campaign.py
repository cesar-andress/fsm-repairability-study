"""Tests for pilot repair campaign runner (Ollama mocked)."""

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
from run_pilot_campaign import (  # noqa: E402
    CampaignError,
    aggregate_campaign_summary,
    discover_case_dirs,
    run_pilot_campaign,
)

RAW_PATCH = (OLLAMA_FIXTURES / "raw_patch_fenced.txt").read_text(encoding="utf-8")


def test_discover_single_case_dir() -> None:
    dirs = discover_case_dirs(CASE_DIR, max_cases=5)
    assert dirs == [CASE_DIR.resolve()]


def test_discover_parent_with_subdirs(tmp_path: Path) -> None:
    root = tmp_path / "cases"
    (root / "alpha").mkdir(parents=True)
    (root / "beta").mkdir(parents=True)
    for name in ("alpha", "beta"):
        (root / name / "case.json").write_text(
            json.dumps(
                {
                    "identity": {"case_id": name, "system_id": "s", "campaign_id": "c"},
                    "inputs": {"requirement_text": "r", "candidate_fsm": "c.json"},
                }
            ),
            encoding="utf-8",
        )
        (root / name / "c.json").write_text("{}", encoding="utf-8")
    found = discover_case_dirs(root, max_cases=1)
    assert len(found) == 1


@mock.patch("generate_patch_ollama.generate", return_value=RAW_PATCH)
def test_pilot_campaign_mocked_ollama(mock_generate, tmp_path: Path) -> None:
    out = tmp_path / "campaign"
    summary, results = run_pilot_campaign(
        cases_dir=CASE_DIR,
        condition="patch_trace_feedback",
        model="test-model",
        max_cases=1,
        output_dir=out,
    )

    assert summary["cases_attempted"] == 1
    assert summary["cases_succeeded"] == 1
    assert summary["metrics"]["failures"] == 0
    assert summary["metrics"]["complete_repair_rate"] == 1.0
    mock_generate.assert_called_once()

    row = results[0]
    assert row.status == "ok"
    assert row.initial_bpr == pytest.approx(2 / 3)
    assert row.final_bpr == 1.0
    assert row.repaired is True
    assert row.patch_operations >= 1

    assert (out / "campaign_summary.json").is_file()
    assert (out / "campaign_results.csv").is_file()
    assert (out / "dry_run_case" / "repair_run.json").is_file()

    with (out / "campaign_results.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["case_id"] == "dry_run_case"
    assert float(rows[0]["delta_bpr"]) == pytest.approx(1 / 3)


def test_aggregate_summary_counts_failures() -> None:
    from run_pilot_campaign import CaseResult  # noqa: E402

    results = [
        CaseResult(
            case_id="a",
            status="ok",
            initial_bpr=0.5,
            final_bpr=1.0,
            delta_bpr=0.5,
            repaired=True,
            complete_repair=True,
        ),
        CaseResult(case_id="b", status="failed", error="ollama down"),
    ]
    summary = aggregate_campaign_summary(
        results=results,
        condition="patch_trace_feedback",
        model="m",
        cases_dir=CASE_DIR,
        output_dir=Path("/tmp/out"),
        started_at="2026-06-03T10:00:00Z",
        completed_at="2026-06-03T11:00:00Z",
    )
    assert summary["metrics"]["failures"] == 1
    assert summary["metrics"]["repair_rate"] == 1.0


def test_invalid_condition_raises() -> None:
    with pytest.raises(CampaignError, match="not supported"):
        run_pilot_campaign(
            cases_dir=CASE_DIR,
            condition="baseline_no_repair",
            model="m",
            max_cases=1,
            output_dir=Path("/tmp/x"),
        )
