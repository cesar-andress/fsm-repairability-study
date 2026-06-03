"""Tests for deterministic repair scoring interface."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "scoring"
SCRIPTS = REPO_ROOT / "scripts"

sys.path.insert(0, str(SCRIPTS))
from score_repair import score_fsm, write_report  # noqa: E402


def _load(name: str) -> dict:
    with (FIXTURES / name).open(encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def suite() -> dict:
    return _load("oracle_suite.json")


def test_bpr_perfect_pass(suite: dict) -> None:
    report = score_fsm(_load("fsm_pass.json"), suite)
    assert report["bpr"] == 1.0
    assert report["passed_tests"] == 3
    assert report["failed_tests"] == 0
    assert report["failures"] == []
    assert report["component_metrics"]["trace_agreement"] == 1.0
    assert report["component_metrics"]["rejected_event_agreement"] == 1.0


def test_bpr_below_one_trace_failure(suite: dict) -> None:
    report = score_fsm(_load("fsm_fail_trace.json"), suite)
    assert report["bpr"] == pytest.approx(2 / 3)
    assert report["failed_tests"] == 1
    assert report["failures"][0]["test_id"] == "trace_ab"
    assert report["failures"][0]["failure_type"] == "trace_mismatch"


def test_rejected_event_agreement_failure(suite: dict) -> None:
    report = score_fsm(_load("fsm_fail_reject.json"), suite)
    reject_failures = [
        f for f in report["failures"] if f["test_id"] == "reject_unknown_z"
    ]
    assert len(reject_failures) == 1
    assert reject_failures[0]["failure_type"] == "unexpected_transition"
    assert report["component_metrics"]["rejected_event_agreement"] == 0.0


def test_failure_diagnostics_structure(suite: dict) -> None:
    report = score_fsm(_load("fsm_fail_trace.json"), suite)
    failure = report["failures"][0]
    for key in (
        "test_id",
        "failure_type",
        "expected",
        "observed",
        "trace",
        "diagnostic_hint",
    ):
        assert key in failure


def test_deterministic_output_structure(suite: dict, tmp_path: Path) -> None:
    out = tmp_path / "score.json"
    report = score_fsm(
        _load("fsm_pass.json"),
        suite,
        fsm_path="fsm_pass.json",
        oracle_suite_path="oracle_suite.json",
    )
    write_report(report, out)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["score_schema_version"] == "1.0.0"
    assert set(data.keys()) >= {
        "fsm_path",
        "oracle_suite_path",
        "total_tests",
        "passed_tests",
        "failed_tests",
        "bpr",
        "component_metrics",
        "failures",
    }
    assert set(data["component_metrics"].keys()) == {
        "final_state_agreement",
        "trace_agreement",
        "rejected_event_agreement",
    }
    again = json.loads(out.read_text(encoding="utf-8"))
    assert again == data


def test_cli_writes_output(suite: dict, tmp_path: Path) -> None:
    out = tmp_path / "cli_score.json"
    cmd = [
        sys.executable,
        str(SCRIPTS / "score_repair.py"),
        "--fsm",
        str(FIXTURES / "fsm_pass.json"),
        "--oracles",
        str(FIXTURES / "oracle_suite.json"),
        "--output",
        str(out),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)
    assert proc.returncode == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["bpr"] == 1.0


def test_guard_boolean_false_ignored() -> None:
    fsm = {
        "id": "guard_test",
        "states": ["s0"],
        "initial_state": "s0",
        "alphabet": ["z"],
        "transitions": [
            {"from": "s0", "event": "z", "to": "s0", "guard": False},
        ],
    }
    mini_suite = {
        "suite_id": "mini",
        "tests": [
            {
                "test_id": "reject_z",
                "type": "rejected_event",
                "from_state": "s0",
                "events": ["z"],
            }
        ],
    }
    report = score_fsm(fsm, mini_suite)
    assert report["bpr"] == 1.0
