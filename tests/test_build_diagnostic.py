"""Tests for deterministic diagnostic projection."""

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
    _diagnostic_id,
    build_diagnostic,
    load_score_report,
    validate_diagnostic_document,
)
from score_repair import score_fsm, write_report  # noqa: E402

FIXED_TIME = "2026-06-03T12:00:00Z"
CASE_ID = "fixture_case"
RUN_ID = "fixture_case__patch_trace_feedback__r001"
FORBIDDEN_BINARY_FIELDS = frozenset(
    {
        "input_trace",
        "expected",
        "observed",
        "expected_final_state",
        "observed_final_state",
    }
)


@pytest.fixture
def fail_trace_score_report() -> dict:
    suite = json.loads((FIXTURES / "oracle_suite.json").read_text(encoding="utf-8"))
    fsm = json.loads((FIXTURES / "fsm_fail_trace.json").read_text(encoding="utf-8"))
    return score_fsm(
        fsm,
        suite,
        fsm_path="fsm_fail_trace.json",
        oracle_suite_path="oracle_suite.json",
    )


@pytest.fixture
def score_report_path(tmp_path: Path, fail_trace_score_report: dict) -> Path:
    for name in ("fsm_fail_trace.json", "oracle_suite.json"):
        (tmp_path / name).write_text(
            (FIXTURES / name).read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    path = tmp_path / "score_fail_trace.json"
    report = dict(fail_trace_score_report)
    report["fsm_path"] = "fsm_fail_trace.json"
    report["oracle_suite_path"] = "oracle_suite.json"
    write_report(report, path)
    return path


def _build(
    report: dict,
    level: str,
    *,
    iteration_index: int = 0,
    bases: list[Path] | None = None,
    score_report_path: Path | None = None,
) -> dict:
    return build_diagnostic(
        report,
        level,
        case_id=CASE_ID,
        run_id=RUN_ID,
        iteration_index=iteration_index,
        generated_at=FIXED_TIME,
        path_resolution_bases=bases or [FIXTURES, REPO_ROOT],
        score_report_path=score_report_path,
    )


def test_binary_diagnostic_does_not_leak_trace_or_final_state_fields(
    fail_trace_score_report: dict,
) -> None:
    diag = _build(fail_trace_score_report, "binary")
    assert diag["identity"]["diagnostic_level"] == "binary"
    assert "localization" not in diag
    failed = diag["failed_checks"][0]
    assert failed["check_id"] == "trace_ab"
    assert FORBIDDEN_BINARY_FIELDS.isdisjoint(failed.keys())
    assert failed["diagnostic_hint"] == "Loop via a then b back to s0"


def test_trace_diagnostic_includes_trace_witnesses(
    fail_trace_score_report: dict,
) -> None:
    diag = _build(fail_trace_score_report, "trace")
    failed = diag["failed_checks"][0]
    assert failed["input_trace"] == {"events": ["a", "b"]}
    assert "states" in failed["expected"]
    assert "states" in failed["observed"]
    assert failed["expected_final_state"] == "s0"
    assert failed["observed_final_state"] == "s1"
    assert "localization" not in diag


def test_localized_diagnostic_includes_empty_localization_when_absent(
    fail_trace_score_report: dict,
) -> None:
    diag = _build(fail_trace_score_report, "localized")
    loc = diag["localization"]
    assert loc["suspicious_states"] == []
    assert loc["suspicious_transitions"] == []
    assert loc["missing_transition_candidates"] == []
    assert loc["extra_transition_candidates"] == []


def test_bpr_recomputed_from_passed_and_total_tests(
    fail_trace_score_report: dict,
) -> None:
    diag = _build(fail_trace_score_report, "trace")
    summary = diag["scoring_summary"]
    assert summary["total_checks"] == fail_trace_score_report["total_tests"]
    assert summary["passed_checks"] == fail_trace_score_report["passed_tests"]
    assert summary["failed_checks"] == fail_trace_score_report["failed_tests"]
    assert summary["bpr"] == pytest.approx(
        fail_trace_score_report["passed_tests"] / fail_trace_score_report["total_tests"]
    )
    assert summary["oracle_suite_id"] == "loop_oracle_v1"


def test_invalid_diagnostic_level_raises_clear_error(
    fail_trace_score_report: dict,
) -> None:
    with pytest.raises(DiagnosticBuildError, match="invalid diagnostic level"):
        build_diagnostic(
            fail_trace_score_report,
            "verbose",
            case_id=CASE_ID,
            run_id=RUN_ID,
            iteration_index=0,
            path_resolution_bases=[FIXTURES],
        )


def test_diagnostic_id_is_deterministic(fail_trace_score_report: dict) -> None:
    expected = _diagnostic_id(CASE_ID, RUN_ID, 0, "trace")
    assert expected == "fixture_case__fixture_case__patch_trace_feedback__r001__iter00__trace"
    diag = _build(fail_trace_score_report, "trace")
    assert diag["identity"]["diagnostic_id"] == expected
    again = _build(fail_trace_score_report, "trace", iteration_index=0)
    assert again["identity"]["diagnostic_id"] == expected
    other_level = _build(fail_trace_score_report, "binary")
    assert other_level["identity"]["diagnostic_id"] == _diagnostic_id(
        CASE_ID, RUN_ID, 0, "binary"
    )


def test_output_validates_against_diagnostic_schema(
    fail_trace_score_report: dict,
    score_report_path: Path,
) -> None:
    for level in ("binary", "trace", "localized"):
        diag = _build(
            fail_trace_score_report,
            level,
            score_report_path=score_report_path,
        )
        validate_diagnostic_document(diag)
        assert diag["identity"]["schema_version"] == "2.0.0"
        assert "score_report_sha256" in diag["reproducibility"]["checksums"]
        assert "source_fsm_sha256" in diag["reproducibility"]["checksums"]
        assert "oracle_suite_sha256" in diag["reproducibility"]["checksums"]


def test_failure_category_mapping(fail_trace_score_report: dict) -> None:
    diag = _build(fail_trace_score_report, "trace")
    cats = diag["failure_categories"]
    assert cats["trace_failures"] == 1
    assert cats["positive_path_failures"] == 1
    assert cats["final_state_failures"] == 0
    assert cats["rejection_failures"] == 0


def test_oracle_suite_id_from_path_when_suite_id_missing(
    fail_trace_score_report: dict,
) -> None:
    report = dict(fail_trace_score_report)
    del report["suite_id"]
    diag = _build(report, "binary")
    assert diag["scoring_summary"]["oracle_suite_id"] == "oracle_suite"


def test_score_report_not_mutated(fail_trace_score_report: dict) -> None:
    snapshot = json.dumps(fail_trace_score_report, sort_keys=True)
    _build(fail_trace_score_report, "localized")
    assert json.dumps(fail_trace_score_report, sort_keys=True) == snapshot


def test_cli_writes_valid_diagnostic(score_report_path: Path, tmp_path: Path) -> None:
    out = tmp_path / "diag_binary.json"
    cmd = [
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
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)
    assert proc.returncode == 0, proc.stderr
    diag = json.loads(out.read_text(encoding="utf-8"))
    validate_diagnostic_document(diag)
    assert diag["identity"]["diagnostic_id"].endswith("__binary")


def test_load_score_report_missing_file(tmp_path: Path) -> None:
    with pytest.raises(DiagnosticBuildError, match="score report not found"):
        load_score_report(tmp_path / "missing.json")
