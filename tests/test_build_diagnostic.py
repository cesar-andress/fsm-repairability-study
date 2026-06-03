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
    normalize_failure_type,
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


LONG_CASE_ID = (
    "repair__c1_pilot_ollama_behavioral__vending_machine__llama3_1_8b__r01"
)
LONG_RUN_ID = (
    "repair__c1_pilot_ollama_behavioral__vending_machine__llama3_1_8b__r01"
    "__patch_binary_feedback__pilot"
)


def test_deterministic_diagnostic_id(score_report: dict) -> None:
    expected = diagnostic_id(CASE_ID, RUN_ID, 0, "trace")
    assert expected == _build(score_report, "trace")["identity"]["diagnostic_id"]
    assert _build(score_report, "trace")["identity"]["diagnostic_id"] == expected
    assert _build(score_report, "binary")["identity"]["diagnostic_id"] == diagnostic_id(
        CASE_ID, RUN_ID, 0, "binary"
    )


def test_long_case_and_run_ids_produce_valid_diagnostic_id(score_report: dict) -> None:
    diag = _build(
        score_report,
        "binary",
        case_id=LONG_CASE_ID,
        run_id=LONG_RUN_ID,
    )
    did = diag["identity"]["diagnostic_id"]
    assert len(did) <= 128
    assert did.startswith("diag_")
    assert did.endswith("_i0_binary")
    assert diag["identity"]["case_id"] == LONG_CASE_ID
    assert diag["identity"]["run_id"] == LONG_RUN_ID
    validate_diagnostic(diag)


def test_different_levels_produce_different_diagnostic_id(score_report: dict) -> None:
    ids = {
        _build(score_report, level)["identity"]["diagnostic_id"]
        for level in ("binary", "trace", "localized")
    }
    assert len(ids) == 3


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


def _score_report_with_failure_types(
    failures: list[dict],
    *,
    total_tests: int = 3,
    passed_tests: int = 1,
) -> dict:
    return {
        "score_schema_version": "1.0.0",
        "total_tests": total_tests,
        "passed_tests": passed_tests,
        "failed_tests": len(failures),
        "bpr": passed_tests / total_tests,
        "failures": failures,
        "fsm_path": "fsm_fail_trace.json",
        "oracle_suite_path": "oracle_suite.json",
    }


def test_invalid_test_spec_normalized_to_invalid_check_spec() -> None:
    report = _score_report_with_failure_types(
        [
            {
                "test_id": "bad_reject",
                "failure_type": "invalid_test_spec",
                "diagnostic_hint": "rejected_event requires exactly one event",
            }
        ],
        total_tests=1,
        passed_tests=0,
    )
    diag = _build(report, "binary")
    assert diag["failed_checks"][0]["failure_type"] == "invalid_check_spec"
    validate_diagnostic(diag)


def test_failure_type_aliases_map_to_schema_names() -> None:
    assert normalize_failure_type("invalid_test_spec") == "invalid_check_spec"
    assert normalize_failure_type("invalid_oracle_spec") == "invalid_check_spec"
    assert normalize_failure_type("unsupported_test_type") == "unsupported_check_type"
    assert normalize_failure_type("trace_mismatch") == "trace_mismatch"


def test_category_counts_unchanged_for_behavioral_failures(score_report: dict) -> None:
    baseline = _build(score_report, "trace")["failure_categories"]
    report = _score_report_with_failure_types(
        [
            {
                "test_id": "trace_ab",
                "failure_type": "trace_mismatch",
                "trace": {"events": ["a", "b"]},
                "expected": {"states": ["s0", "s1", "s0"]},
                "observed": {"states": ["s0", "s1", "s1"]},
            },
            {
                "test_id": "bad_reject",
                "failure_type": "invalid_test_spec",
            },
        ],
        total_tests=3,
        passed_tests=1,
    )
    mixed = _build(report, "trace")["failure_categories"]
    assert mixed == baseline


def test_valid_failure_types_unchanged_in_projection(score_report: dict) -> None:
    diag = _build(score_report, "trace")
    assert diag["failed_checks"][0]["failure_type"] == "trace_mismatch"


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
