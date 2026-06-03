"""Tests for score_report.json -> diagnostic.json projection."""

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
from build_diagnostic import (  # noqa: E402
    DiagnosticBuildError,
    build_diagnostic,
    diagnostic_id,
    validate_diagnostic,
)
from score_repair import score_fsm  # noqa: E402

CASE_ID = "case01"
RUN_ID = "case01_run01"
FIXED_TIME = "2026-06-03T12:00:00Z"
EVIDENCE_FIELDS = frozenset(
    {
        "input_trace",
        "expected",
        "observed",
        "expected_final_state",
        "observed_final_state",
    }
)


@pytest.fixture
def score_report() -> dict:
    return json.loads(
        (FIXTURES / "score_report_fail_trace.json").read_text(encoding="utf-8")
    )


@pytest.fixture
def score_report_path(tmp_path: Path, score_report: dict) -> Path:
    for name in ("fsm_fail_trace.json", "oracle_suite.json"):
        (tmp_path / name).write_text(
            (FIXTURES / name).read_text(encoding="utf-8"), encoding="utf-8"
        )
    path = tmp_path / "score_report.json"
    path.write_text(json.dumps(score_report, indent=2) + "\n", encoding="utf-8")
    return path


def _build(report: dict, level: str, **kwargs: object) -> dict:
    defaults = {
        "case_id": CASE_ID,
        "run_id": RUN_ID,
        "iteration_index": 0,
        "generated_at": FIXED_TIME,
        "path_bases": [FIXTURES, REPO_ROOT],
    }
    defaults.update(kwargs)
    return build_diagnostic(report, level, **defaults)  # type: ignore[arg-type]


def test_binary_does_not_leak_detailed_evidence(score_report: dict) -> None:
    diag = _build(score_report, "binary")
    assert "localization" not in diag
    failed = diag["failed_checks"][0]
    assert EVIDENCE_FIELDS.isdisjoint(failed.keys())
    assert failed["check_id"] == "trace_ab"
    assert failed["diagnostic_hint"] == "Loop via a then b back to s0"


def test_trace_includes_detailed_evidence(score_report: dict) -> None:
    diag = _build(score_report, "trace")
    failed = diag["failed_checks"][0]
    assert failed["input_trace"] == {"events": ["a", "b"]}
    assert "states" in failed["expected"]
    assert "states" in failed["observed"]
    assert failed["expected_final_state"] == "s0"
    assert failed["observed_final_state"] == "s1"
    assert "localization" not in diag


def test_localized_includes_empty_localization_when_absent(score_report: dict) -> None:
    diag = _build(score_report, "localized")
    loc = diag["localization"]
    assert loc == {
        "suspicious_states": [],
        "suspicious_transitions": [],
        "missing_transition_candidates": [],
        "extra_transition_candidates": [],
    }


def test_bpr_is_recomputed_not_trusted_from_input(score_report: dict) -> None:
    assert score_report["bpr"] == 0.99
    diag = _build(score_report, "trace")
    assert diag["scoring_summary"]["bpr"] == pytest.approx(2 / 3)
    assert diag["scoring_summary"]["total_checks"] == 3
    assert diag["scoring_summary"]["passed_checks"] == 2
    assert diag["scoring_summary"]["failed_checks"] == 1


def test_deterministic_diagnostic_id(score_report: dict) -> None:
    expected = diagnostic_id(CASE_ID, RUN_ID, 0, "trace")
    assert expected == "diag_case01_case01_run01_i0_trace"
    assert _build(score_report, "trace")["identity"]["diagnostic_id"] == expected
    assert _build(score_report, "binary")["identity"]["diagnostic_id"] == diagnostic_id(
        CASE_ID, RUN_ID, 0, "binary"
    )


def test_invalid_level_clear_error(score_report: dict) -> None:
    with pytest.raises(DiagnosticBuildError, match="invalid level"):
        build_diagnostic(
            score_report,
            "full",
            case_id=CASE_ID,
            run_id=RUN_ID,
            iteration_index=0,
            path_bases=[FIXTURES],
        )


def test_output_validates_against_schema(
    score_report: dict, score_report_path: Path
) -> None:
    for level in ("binary", "trace", "localized"):
        doc = build_diagnostic(
            score_report,
            level,
            case_id=CASE_ID,
            run_id=RUN_ID,
            iteration_index=0,
            generated_at=FIXED_TIME,
            score_report_path=score_report_path,
            path_bases=[score_report_path.parent, FIXTURES, REPO_ROOT],
        )
        validate_diagnostic(doc)
        assert doc["identity"]["schema_version"] == "2.0.0"
        assert "score_report_sha256" in doc["reproducibility"]["checksums"]


def test_score_report_not_mutated(score_report: dict) -> None:
    before = json.dumps(score_report, sort_keys=True)
    _build(score_report, "localized")
    assert json.dumps(score_report, sort_keys=True) == before


def test_cli_exit_success(score_report_path: Path, tmp_path: Path) -> None:
    out = tmp_path / "out.json"
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "build_diagnostic.py"),
            "--score-report",
            str(score_report_path),
            "--level",
            "binary",
            "--case-id",
            CASE_ID,
            "--run-id",
            RUN_ID,
            "--iteration-index",
            "0",
            "--output",
            str(out),
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert proc.returncode == 0, proc.stderr
    doc = json.loads(out.read_text(encoding="utf-8"))
    validate_diagnostic(doc)


def test_live_score_repair_fixture() -> None:
    suite = json.loads((FIXTURES / "oracle_suite.json").read_text(encoding="utf-8"))
    fsm = json.loads((FIXTURES / "fsm_fail_trace.json").read_text(encoding="utf-8"))
    report = score_fsm(
        fsm,
        suite,
        fsm_path="fsm_fail_trace.json",
        oracle_suite_path="oracle_suite.json",
    )
    diag = _build(report, "trace")
    assert diag["failed_checks"][0]["check_id"] == "trace_ab"
