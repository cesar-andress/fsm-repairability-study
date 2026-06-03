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
        "schema_version": "1.0.0-placeholder",
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
        "schema_version": "1.0.0-placeholder",
        "patch_id": "p1",
        "target_fsm_id": "fsm_test_01",
        "operations": [
            {"op": "add_transition", "from": "s1", "event": "b", "to": "s0"}
        ],
    }
    _validator("patch.schema.json").validate(patch)


def test_repair_case_schema_entry_bundle() -> None:
    case = {
        "schema_version": "1.0.0",
        "case_id": "case_01",
        "system_id": "example_system",
        "requirement_text": "Example requirement text.",
        "gold_fsm_path": "gold_fsm.json",
        "candidate_fsm_path": "candidate_fsm.json",
        "initial_bpr": 0.0,
        "oracle_suite_id": "suite_01",
        "failed_tests": [{"check_id": "check_a"}],
        "passed_tests": [],
        "missing_transitions": [],
        "extra_transitions": [],
        "repair_history": [],
        "final_bpr": None,
        "final_status": "not_started",
    }
    _validator("repair_case.schema.json").validate(case)


def test_repair_run_schema_placeholder() -> None:
    run = {
        "schema_version": "1.0.0-placeholder",
        "run_id": "run_01",
        "case_id": "case_01",
        "condition_id": "patch_binary_feedback",
        "model_label": "llama3:8b",
        "uses_llm": True,
        "attempt_budget": 3,
        "attempts": [{"attempt_index": 0, "oracle_passed": False}],
        "outcome": "budget_exhausted",
    }
    _validator("repair_run.schema.json").validate(run)


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
