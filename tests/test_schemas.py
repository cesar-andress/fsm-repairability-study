"""Contract tests for JSON schemas and validation."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = REPO_ROOT / "schemas"
SCRIPTS = REPO_ROOT / "scripts"

import sys

sys.path.insert(0, str(SCRIPTS))
from validate_fsm import validate_fsm_document, validate_referential_integrity  # noqa: E402


def _schema_registry() -> Registry:
    registry: Registry = Registry()
    for path in sorted(SCHEMAS.glob("*.json")):  # includes repair_condition.schema.json
        with path.open(encoding="utf-8") as f:
            contents = json.load(f)
        registry = registry.with_resource(
            path.name,
            Resource.from_contents(contents),
        )
    return registry


def _validator(name: str) -> Draft202012Validator:
    with (SCHEMAS / name).open(encoding="utf-8") as f:
        schema = json.load(f)
    return Draft202012Validator(schema, registry=_schema_registry())


@pytest.fixture
def minimal_fsm() -> dict:
    return {
        "schema_version": "1.0.0",
        "id": "fsm_test_01",
        "states": ["s0", "s1"],
        "initial_state": "s0",
        "alphabet": ["a"],
        "transitions": [{"from": "s0", "event": "a", "to": "s1"}],
    }


def test_fsm_schema_accepts_minimal_example(minimal_fsm: dict) -> None:
    with (SCHEMAS / "fsm.schema.json").open(encoding="utf-8") as f:
        schema = json.load(f)
    _validator("fsm.schema.json").validate(minimal_fsm)
    assert validate_fsm_document(minimal_fsm, schema) == []
    assert validate_referential_integrity(minimal_fsm) == []


def test_fsm_schema_rejects_missing_initial_state(minimal_fsm: dict) -> None:
    del minimal_fsm["initial_state"]
    with pytest.raises(jsonschema.ValidationError):
        _validator("fsm.schema.json").validate(minimal_fsm)


def test_patch_schema_accepts_add_transition() -> None:
    patch = {
        "schema_version": "1.0.0",
        "patch_id": "p1",
        "target_fsm_id": "fsm_test_01",
        "operations": [
            {"op": "add_transition", "from": "s1", "event": "b", "to": "s0"}
        ],
        "inverse_operations": [
            {"op": "remove_transition", "from": "s1", "event": "b", "to": "s0"}
        ],
    }
    _validator("patch.schema.json").validate(patch)


def test_repair_case_schema_entry_bundle() -> None:
    case = {
        "schema_version": "2.0.0",
        "identity": {
            "case_id": "case_01",
            "system_id": "example_system",
            "campaign_id": "campaign_01",
        },
        "inputs": {
            "requirement_text": "Example requirement text.",
            "candidate_fsm": "candidate_fsm.json",
            "reference_fsm": "reference_fsm.json",
        },
        "baseline": {
            "initial_bpr": 0.0,
            "initial_component_metrics": {
                "suite_id": "suite_01",
                "total_count": 1,
                "passed_count": 0,
                "failed_count": 1,
                "checks": [{"check_id": "check_a", "passed": False}],
            },
        },
        "oracles": {
            "feedback_oracles": {"suite_id": "suite_fb"},
            "validation_oracles": {"suite_id": "suite_01"},
        },
        "diagnostics": {
            "missing_transitions": [],
            "extra_transitions": [],
            "failure_summary": "One check fails.",
        },
        "repair_history": {
            "iterations": [],
            "applied_patches": [],
            "intermediate_bpr": [0.0],
        },
        "final_outcome": {
            "final_bpr": None,
            "repair_status": "not_started",
            "regression_detected": False,
            "overfitting_detected": False,
        },
    }
    _validator("repair_case.schema.json").validate(case)


def _iteration_stub(index: int = 0) -> dict:
    return {
        "iteration_index": index,
        "input_candidate_path": "candidates/initial.json",
        "input_bpr_feedback": 0.25,
        "input_bpr_validation": 0.25,
        "feedback_summary_path": "feedback/iter_000.json",
        "generated_patch_path": "patches/iter_000.json",
        "patch_valid": True,
        "patch_applied": True,
        "output_candidate_path": "candidates/iter_000.json",
        "output_bpr_feedback": 0.5,
        "output_bpr_validation": 0.5,
        "regression_detected": False,
        "overfitting_detected": False,
        "error_type": "none",
        "error_message": "",
    }


def _repair_run_v2_stub(*, baseline: bool = False) -> dict:
    return {
        "schema_version": "2.0.0",
        "identity": {
            "run_id": "case_01__baseline_no_repair__r001"
            if baseline
            else "case_01__patch_binary_feedback__r001",
            "case_id": "case_01",
            "system_id": "example_system",
        },
        "execution": {
            "repair_condition": "baseline_no_repair"
            if baseline
            else "patch_binary_feedback",
            "model_name": None if baseline else "llama3:8b",
            "model_digest": None if baseline else "a" * 64,
            "execution_backend": "none" if baseline else "ollama",
            "started_at": "2026-06-03T12:00:00Z",
            "completed_at": "2026-06-03T12:05:00Z",
            "max_iterations": 0 if baseline else 5,
            "temperature": 0.2,
            "seed": None if baseline else 42,
        },
        "inputs": {
            "input_case_path": "case.json",
            "initial_candidate_path": "candidates/initial.json",
            "feedback_oracle_set_id": "suite_fb",
            "validation_oracle_set_id": "suite_val",
        },
        "iterations": [] if baseline else [_iteration_stub()],
        "outcome": {
            "final_candidate_path": "candidates/initial.json"
            if baseline
            else "candidates/iter_000.json",
            "final_bpr_feedback": 0.25 if baseline else 0.5,
            "final_bpr_validation": 0.25 if baseline else 0.5,
            "outcome_class": "no_improvement"
            if baseline
            else "effective_repair",
            "complete_repair": False,
            "effective_repair": False if baseline else True,
            "behavioural_degradation": False,
            "regression_detected": False,
            "overfitting_detected": False,
            "iterations_to_outcome": 0 if baseline else 0,
        },
        "cost": {
            "prompt_tokens_estimated": 0 if baseline else 100,
            "completion_tokens_estimated": 0 if baseline else 50,
            "wall_time_seconds": 1.0,
            "oracle_executions": 2,
            "patch_operations_total": 0 if baseline else 3,
        },
        "reproducibility": {
            "code_version": "deadbeef",
            "command": "python scripts/run_repair_condition.py",
            "environment_id": "test_env",
            "input_checksums": {"case.json": "a" * 64},
            "output_checksums": {"final.json": "b" * 64},
        },
    }


def test_repair_run_schema_v2_patch_condition() -> None:
    _validator("repair_run.schema.json").validate(_repair_run_v2_stub())


def test_repair_run_schema_v2_baseline_no_repair() -> None:
    _validator("repair_run.schema.json").validate(_repair_run_v2_stub(baseline=True))


def _diagnostic_base(level: int) -> dict:
    diag = {
        "schema_version": "1.0.0",
        "diagnostic_level": level,
        "identity": {
            "diagnostic_id": "case_01__run__iter00",
            "case_id": "case_01",
            "run_id": "case_01__patch_trace_feedback__r001",
            "iteration_index": 0,
        },
        "scoring_summary": {
            "total_tests": 2,
            "passed_tests": 1,
            "failed_tests": 1,
            "bpr": 0.5,
        },
        "failure_summary": {
            "failure_count": 1,
            "failure_categories": ["trace_mismatch"],
            "positive_path_failures": 1,
            "rejection_failures": 0,
        },
        "failed_tests": [
            {
                "test_id": "trace_ab",
                "oracle_type": "trace",
                "failure_type": "trace_mismatch",
                "expected_result": {"states": ["s0", "s1", "s0"]},
                "observed_result": {"states": ["s0", "s1", "s1"]},
                "expected_final_state": "s0",
                "observed_final_state": "s1",
                "trace": None if level == 1 else {"events": ["a", "b"], "states": ["s0", "s1", "s1"]},
            }
        ],
    }
    if level == 3:
        diag["localization"] = {
            "suspicious_states": ["s1"],
            "suspicious_transitions": [{"from": "s1", "event": "b", "to": "s1"}],
        }
    return diag


def test_diagnostic_schema_level1_binary() -> None:
    _validator("diagnostic.schema.json").validate(_diagnostic_base(1))


def test_diagnostic_schema_level2_trace() -> None:
    _validator("diagnostic.schema.json").validate(_diagnostic_base(2))


def test_diagnostic_schema_level3_localized() -> None:
    _validator("diagnostic.schema.json").validate(_diagnostic_base(3))


def test_repair_condition_schema() -> None:
    cond = {
        "schema_version": "1.0.0-placeholder",
        "condition_id": "baseline_no_repair",
        "role": "baseline",
        "prompt_ref": None,
        "uses_llm": False,
        "default_attempt_budget": 0,
    }
    _validator("repair_condition.schema.json").validate(cond)
