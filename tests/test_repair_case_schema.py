"""Contract tests for repair_case.schema.json v2.0.0."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = REPO_ROOT / "schemas"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "repair_cases"

VALID_FIXTURES = (
    "not_started.json",
    "complete_repair.json",
    "overfitting_detected.json",
)

INVALID_FIXTURES = (
    "invalid_missing_case_id.json",
    "invalid_bpr_out_of_range.json",
    "invalid_outcome_history_mismatch.json",
)


def _schema_registry() -> Registry:
    registry: Registry = Registry()
    for path in sorted(SCHEMAS.glob("*.json")):
        with path.open(encoding="utf-8") as f:
            contents = json.load(f)
        registry = registry.with_resource(path.name, Resource.from_contents(contents))
    return registry


def _repair_case_validator() -> Draft202012Validator:
    with (SCHEMAS / "repair_case.schema.json").open(encoding="utf-8") as f:
        schema = json.load(f)
    return Draft202012Validator(schema, registry=_schema_registry())


def _load_fixture(name: str) -> dict:
    with (FIXTURES / name).open(encoding="utf-8") as f:
        return json.load(f)


def assert_repair_case_history_consistent(case: dict) -> None:
    """Cross-field rules beyond JSON Schema (v2.0.0 study invariants)."""
    history = case["repair_history"]
    outcome = case["final_outcome"]
    baseline_bpr = case["baseline"]["initial_bpr"]
    bpr_trace = history["intermediate_bpr"]

    assert len(bpr_trace) >= 1, "intermediate_bpr must include index 0 (initial)"
    assert bpr_trace[0] == baseline_bpr, "intermediate_bpr[0] must equal baseline.initial_bpr"

    n_iter = len(history["iterations"])
    assert len(bpr_trace) == n_iter + 1, (
        "intermediate_bpr length must be iterations + 1 "
        f"(got {len(bpr_trace)} bpr values for {n_iter} iterations)"
    )

    for i, record in enumerate(history["iterations"]):
        assert record["iteration_index"] == i
        if record.get("bpr_before") is not None:
            assert record["bpr_before"] == bpr_trace[i]
        assert record["bpr_after"] == bpr_trace[i + 1]

    status = outcome["repair_status"]
    if status == "not_started":
        assert n_iter == 0
        assert len(history["applied_patches"]) == 0
        assert outcome["final_bpr"] is None
    elif status == "success":
        assert outcome["final_bpr"] == bpr_trace[-1]
        assert history["iterations"][-1]["validation_passed_all"] is True

    if outcome["overfitting_detected"] and n_iter > 0:
        assert outcome["final_bpr"] == bpr_trace[-1]


@pytest.mark.parametrize("fixture_name", VALID_FIXTURES)
def test_valid_repair_case_fixtures_pass_schema(fixture_name: str) -> None:
    case = _load_fixture(fixture_name)
    _repair_case_validator().validate(case)
    assert_repair_case_history_consistent(case)


@pytest.mark.parametrize("fixture_name", INVALID_FIXTURES)
def test_invalid_repair_case_fixtures_reject_schema(fixture_name: str) -> None:
    case = _load_fixture(fixture_name)
    with pytest.raises(jsonschema.ValidationError):
        _repair_case_validator().validate(case)


def test_complete_repair_fixture_declares_success() -> None:
    case = _load_fixture("complete_repair.json")
    assert case["final_outcome"]["repair_status"] == "success"
    assert case["final_outcome"]["final_bpr"] == 1.0


def test_overfitting_fixture_flags_overfitting() -> None:
    case = _load_fixture("overfitting_detected.json")
    assert case["final_outcome"]["overfitting_detected"] is True
    assert case["final_outcome"]["final_bpr"] == case["baseline"]["initial_bpr"]


def test_semantic_rejects_success_with_final_bpr_mismatch() -> None:
    case = _load_fixture("complete_repair.json")
    case["final_outcome"]["final_bpr"] = 0.25
    _repair_case_validator().validate(case)
    with pytest.raises(AssertionError):
        assert_repair_case_history_consistent(case)
