"""Tests for per-condition prompt variant dispatch."""

from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path
from unittest import mock

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
CASE_DIR = REPO_ROOT / "tests" / "fixtures" / "dry_run_case"
SCRIPTS = REPO_ROOT / "scripts"

sys.path.insert(0, str(SCRIPTS))
from generate_patch_ollama import (  # noqa: E402
    resolve_prompt_variant_for_condition,
)
from run_diagnostic_granularity_pilot import (  # noqa: E402
    GRANULARITY_CONDITIONS,
    aggregate_summary,
    run_diagnostic_granularity_pilot,
)
from run_pilot_campaign import CaseResult, run_pilot_campaign  # noqa: E402


@pytest.mark.parametrize(
    ("global_variant", "condition", "expected"),
    [
        ("default", "patch_binary_feedback", "default"),
        ("default", "patch_trace_feedback", "default"),
        ("default", "patch_localized_feedback", "default"),
        ("operation-aware", "patch_binary_feedback", "operation-aware"),
        ("operation-aware", "patch_trace_feedback", "operation-aware"),
        ("operation-aware", "patch_localized_feedback", "operation-aware"),
        ("operation-inferred", "patch_binary_feedback", "default"),
        ("operation-inferred", "patch_trace_feedback", "default"),
        ("operation-inferred", "patch_localized_feedback", "operation-inferred"),
    ],
)
def test_resolve_prompt_variant_for_condition(
    global_variant: str, condition: str, expected: str
) -> None:
    assert (
        resolve_prompt_variant_for_condition(global_variant, condition) == expected
    )


def test_aggregate_summary_prompt_variant_fields() -> None:
    summary = aggregate_summary(
        [],
        model="m",
        cases_dir=CASE_DIR,
        output_dir=Path("/tmp/out"),
        iteration_budget=1,
        started_at="2026-06-03T10:00:00Z",
        completed_at="2026-06-03T11:00:00Z",
        prompt_variant_requested="operation-inferred",
    )
    assert summary["prompt_variant"] == "operation-inferred"
    assert summary["prompt_variant_requested"] == "operation-inferred"
    assert summary["prompt_variant_by_condition"] == {
        "C": "default",
        "D": "default",
        "E": "operation-inferred",
    }


@mock.patch("run_diagnostic_granularity_pilot.run_case_pipeline")
def test_operation_inferred_dispatches_only_e(mock_pipeline: mock.MagicMock) -> None:
    mock_pipeline.return_value = CaseResult(case_id="dry_run_case", status="ok")
    run_diagnostic_granularity_pilot(
        cases_dir=CASE_DIR,
        model="test-model",
        max_cases=1,
        output_dir=Path("/tmp/granularity_oi_dispatch"),
        prompt_variant="operation-inferred",
    )
    assert mock_pipeline.call_count == 3
    by_condition = {
        call.kwargs["condition"]: call.kwargs["prompt_variant"]
        for call in mock_pipeline.call_args_list
    }
    assert by_condition["patch_binary_feedback"] == "default"
    assert by_condition["patch_trace_feedback"] == "default"
    assert by_condition["patch_localized_feedback"] == "operation-inferred"


@mock.patch("run_diagnostic_granularity_pilot.run_case_pipeline")
def test_operation_aware_dispatches_all_conditions(
    mock_pipeline: mock.MagicMock,
) -> None:
    mock_pipeline.return_value = CaseResult(case_id="dry_run_case", status="ok")
    run_diagnostic_granularity_pilot(
        cases_dir=CASE_DIR,
        model="test-model",
        max_cases=1,
        output_dir=Path("/tmp/granularity_oa_dispatch"),
        prompt_variant="operation-aware",
    )
    for call in mock_pipeline.call_args_list:
        assert call.kwargs["prompt_variant"] == "operation-aware"


@mock.patch("run_diagnostic_granularity_pilot.run_case_pipeline")
def test_default_dispatches_all_conditions(mock_pipeline: mock.MagicMock) -> None:
    mock_pipeline.return_value = CaseResult(case_id="dry_run_case", status="ok")
    run_diagnostic_granularity_pilot(
        cases_dir=CASE_DIR,
        model="test-model",
        max_cases=1,
        output_dir=Path("/tmp/granularity_default_dispatch"),
    )
    for call in mock_pipeline.call_args_list:
        assert call.kwargs["prompt_variant"] == "default"


@mock.patch("run_diagnostic_granularity_pilot.run_case_pipeline")
def test_granularity_summary_records_operation_inferred_mapping(
    mock_pipeline: mock.MagicMock, tmp_path: Path
) -> None:
    mock_pipeline.return_value = CaseResult(case_id="dry_run_case", status="ok")
    out = tmp_path / "granularity_oi_summary"
    summary, _rows = run_diagnostic_granularity_pilot(
        cases_dir=CASE_DIR,
        model="test-model",
        max_cases=1,
        output_dir=out,
        prompt_variant="operation-inferred",
    )
    assert summary["prompt_variant_requested"] == "operation-inferred"
    assert summary["prompt_variant_by_condition"] == {
        "C": "default",
        "D": "default",
        "E": "operation-inferred",
    }
    doc = json.loads(
        (out / "diagnostic_granularity_summary.json").read_text(encoding="utf-8")
    )
    assert doc["prompt_variant_by_condition"]["C"] == "default"
    assert doc["prompt_variant_by_condition"]["E"] == "operation-inferred"


@mock.patch("run_pilot_campaign.run_case_pipeline")
def test_pilot_campaign_operation_inferred_on_binary_uses_default(
    mock_pipeline: mock.MagicMock, tmp_path: Path
) -> None:
    mock_pipeline.return_value = CaseResult(case_id="dry_run_case", status="ok")
    summary, _ = run_pilot_campaign(
        cases_dir=CASE_DIR,
        condition="patch_binary_feedback",
        model="test-model",
        max_cases=1,
        output_dir=tmp_path / "pilot_oi",
        prompt_variant="operation-inferred",
    )
    assert mock_pipeline.call_args.kwargs["prompt_variant"] == "default"
    assert summary["prompt_variant_requested"] == "operation-inferred"
    assert summary["prompt_variant_effective"] == "default"
