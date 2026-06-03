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
    GranularityCaseRow,
    _apply_condition_result,
    _best_condition_label,
    aggregate_summary,
    classify_failure,
    run_diagnostic_granularity_pilot,
)
from run_pilot_campaign import CaseResult  # noqa: E402

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
        assert pc["cases_attempted"] == 1
        assert pc["cases_evaluated"] == 1
        assert pc["cases_failed"] == 0
        assert pc["generation_failure_count"] == 0
        assert pc["mean_delta_bpr"] == pytest.approx(1 / 3)
        assert pc["complete_repair_rate"] == 1.0
        assert pc["regression_rate"] == 0.0
        assert csv_rows[0][f"status_{label}"] == "ok"
        assert csv_rows[0][f"patch_applied_{label}"] == "true"
        assert csv_rows[0][f"error_{label}"] == ""


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
    assert summary["per_condition"]["C"]["cases_attempted"] == 0
    assert summary["per_condition"]["C"]["cases_evaluated"] == 0
    assert summary["per_condition"]["C"]["cases_failed"] == 0
    assert summary["per_condition"]["C"]["mean_delta_bpr"] is None
    assert summary["per_condition"]["C"]["complete_repair_rate"] is None


def test_classify_failure_categories() -> None:
    assert classify_failure(
        CaseResult(case_id="x", status="failed", error="patch validation failed")
    ) == "invalid_patch"
    assert classify_failure(
        CaseResult(case_id="x", status="failed", error="patch application failed: x")
    ) == "patch_application_failure"
    assert classify_failure(
        CaseResult(case_id="x", status="failed", error="Ollama request failed")
    ) == "generation_failure"
    assert classify_failure(
        CaseResult(case_id="x", status="failed", error="diagnostic does not match schema")
    ) == "scoring_failure"


def test_summary_separates_evaluated_and_failed() -> None:
    row = GranularityCaseRow(case_id="c1", initial_bpr=0.5)
    row.status["C"] = "ok"
    row.delta["C"] = 0.1
    row.status["D"] = "failed"
    row.failure_category["D"] = "scoring_failure"
    row.errors["D"] = "diagnostic build failed"
    row.status["E"] = "failed"
    row.failure_category["E"] = "generation_failure"
    summary = aggregate_summary(
        [row],
        model="m",
        cases_dir=CASE_DIR,
        output_dir=Path("/tmp/out"),
        iteration_budget=1,
        started_at="2026-06-03T10:00:00Z",
        completed_at="2026-06-03T11:00:00Z",
    )
    assert summary["per_condition"]["C"]["cases_evaluated"] == 1
    assert summary["per_condition"]["C"]["cases_failed"] == 0
    assert summary["per_condition"]["D"]["cases_evaluated"] == 0
    assert summary["per_condition"]["D"]["cases_failed"] == 1
    assert summary["per_condition"]["D"]["scoring_failure_count"] == 1
    assert summary["per_condition"]["E"]["generation_failure_count"] == 1


@mock.patch("run_diagnostic_granularity_pilot.run_case_pipeline")
def test_one_condition_failure_does_not_abort_pilot(
    mock_pipeline: mock.MagicMock, tmp_path: Path
) -> None:
    def fake_pipeline(**kwargs: object) -> CaseResult:
        condition = kwargs["condition"]
        output_dir = kwargs["output_dir"]
        case_dir = kwargs["case_dir"]
        case = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
        case_id = case["identity"]["case_id"]
        if condition == "patch_trace_feedback":
            return CaseResult(
                case_id=case_id,
                status="failed",
                error="diagnostic does not match schema: bad field",
                initial_bpr=2 / 3,
            )
        return CaseResult(
            case_id=case_id,
            status="ok",
            initial_bpr=2 / 3,
            final_bpr=1.0,
            delta_bpr=1 / 3,
            complete_repair=True,
            patch_valid=True,
            patch_applied=True,
            outcome_class="complete_repair",
            work_dir=output_dir / case_id,
        )

    mock_pipeline.side_effect = fake_pipeline
    out = tmp_path / "granularity_partial"
    summary, rows = run_diagnostic_granularity_pilot(
        cases_dir=CASE_DIR,
        model="test-model",
        max_cases=1,
        output_dir=out,
    )
    assert mock_pipeline.call_count == 3
    assert rows[0].status["C"] == "ok"
    assert rows[0].status["D"] == "failed"
    assert rows[0].status["E"] == "ok"

    with (out / "diagnostic_granularity_results.csv").open(encoding="utf-8") as f:
        csv_row = next(csv.DictReader(f))
    assert csv_row["status_D"] == "failed"
    assert "diagnostic" in csv_row["error_D"].lower()
    assert csv_row["status_C"] == "ok"
    assert (out / "runs" / "dry_run_case" / "D" / "error.txt").is_file()

    assert summary["per_condition"]["D"]["cases_evaluated"] == 0
    assert summary["per_condition"]["D"]["cases_failed"] == 1
    assert summary["per_condition"]["D"]["scoring_failure_count"] == 1
    assert summary["per_condition"]["C"]["cases_evaluated"] == 1


def test_all_attempted_cases_appear_in_csv(tmp_path: Path) -> None:
    root = tmp_path / "two_cases"
    for name in ("alpha", "beta"):
        case_dir = root / name
        case_dir.mkdir(parents=True)
        for fname, src in (
            ("case.json", CASE_DIR / "case.json"),
            ("candidate_fsm.json", CASE_DIR / "candidate_fsm.json"),
            ("reference_fsm.json", CASE_DIR / "reference_fsm.json"),
            ("oracle_suite.json", CASE_DIR / "oracle_suite.json"),
        ):
            text = src.read_text(encoding="utf-8")
            if fname == "case.json":
                doc = json.loads(text)
                doc["identity"]["case_id"] = name
                text = json.dumps(doc, indent=2) + "\n"
            (case_dir / fname).write_text(text, encoding="utf-8")

    out = tmp_path / "granularity_two"
    with mock.patch(
        "run_diagnostic_granularity_pilot.run_case_pipeline",
        side_effect=lambda **kw: CaseResult(
            case_id=json.loads((kw["case_dir"] / "case.json").read_text())["identity"][
                "case_id"
            ],
            status="failed",
            error="patch validation failed",
            initial_bpr=0.5,
        ),
    ):
        _summary, rows = run_diagnostic_granularity_pilot(
            cases_dir=root,
            model="test-model",
            max_cases=10,
            output_dir=out,
        )

    assert len(rows) == 2
    with (out / "diagnostic_granularity_results.csv").open(encoding="utf-8") as f:
        csv_rows = list(csv.DictReader(f))
    assert len(csv_rows) == 2
    assert {r["case_id"] for r in csv_rows} == {"alpha", "beta"}
    for row in csv_rows:
        assert row["status_C"] == "failed"
        assert row["error_C"]


def test_failed_condition_writes_error_txt(tmp_path: Path) -> None:
    out = tmp_path / "granularity_errfile"
    cond_dir = out / "runs" / "dry_run_case" / "D"
    row = GranularityCaseRow(case_id="dry_run_case")
    result = CaseResult(
        case_id="dry_run_case",
        status="failed",
        error="patch validation failed: ops",
    )
    _apply_condition_result(row, "D", result, cond_dir=cond_dir)
    err_path = cond_dir / "error.txt"
    assert err_path.is_file()
    assert "patch validation" in err_path.read_text(encoding="utf-8")
    assert row.failure_category["D"] == "invalid_patch"
