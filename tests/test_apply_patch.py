"""Unit tests for patch engine v1 (transition operations)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = REPO_ROOT / "examples"
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from apply_patch import (  # noqa: E402
    PatchEngineError,
    apply_patch,
    canonicalize_fsm,
    load_fsm,
    load_patch,
    write_fsm,
)


@pytest.fixture
def base_fsm() -> dict:
    return {
        "schema_version": "1.0.0",
        "id": "fsm_test_01",
        "states": ["s0", "s1"],
        "initial_state": "s0",
        "alphabet": ["a"],
        "transitions": [{"from": "s0", "event": "a", "to": "s1"}],
    }


def test_add_transition_extends_machine(base_fsm: dict) -> None:
    patch = {
        "schema_version": "1.0.0",
        "patch_id": "add_b",
        "target_fsm_id": "fsm_test_01",
        "operations": [
            {"op": "add_transition", "from": "s1", "event": "b", "to": "s0"}
        ],
    }
    result = apply_patch(base_fsm, patch)
    assert {"from": "s1", "event": "b", "to": "s0"} in result["transitions"]
    assert result["alphabet"] == ["a", "b"]


def test_remove_transition(base_fsm: dict) -> None:
    patch = {
        "schema_version": "1.0.0",
        "patch_id": "remove_a",
        "target_fsm_id": "fsm_test_01",
        "operations": [
            {"op": "remove_transition", "from": "s0", "event": "a", "to": "s1"}
        ],
    }
    result = apply_patch(base_fsm, patch)
    assert result["transitions"] == []
    assert result["alphabet"] == []


def test_update_transition(base_fsm: dict) -> None:
    extended = apply_patch(
        base_fsm,
        {
            "schema_version": "1.0.0",
            "patch_id": "add_loop",
            "target_fsm_id": "fsm_test_01",
            "operations": [
                {"op": "add_transition", "from": "s1", "event": "b", "to": "s0"}
            ],
        },
    )
    patch = {
        "schema_version": "1.0.0",
        "patch_id": "retarget_b",
        "target_fsm_id": "fsm_test_01",
        "operations": [
            {
                "op": "update_transition",
                "from": "s1",
                "event": "b",
                "old_to": "s0",
                "new_to": "s1",
            }
        ],
    }
    result = apply_patch(extended, patch)
    assert {"from": "s1", "event": "b", "to": "s1"} in result["transitions"]


def test_duplicate_add_reports_operation_index(base_fsm: dict) -> None:
    patch = {
        "schema_version": "1.0.0",
        "patch_id": "dup",
        "target_fsm_id": "fsm_test_01",
        "operations": [
            {"op": "add_transition", "from": "s0", "event": "a", "to": "s1"}
        ],
    }
    with pytest.raises(PatchEngineError) as exc_info:
        apply_patch(base_fsm, patch)
    err = exc_info.value
    assert err.operation_index == 0
    assert "operation[0]" in str(err)
    assert "duplicate" in str(err).lower()
    assert err.format_detailed()


def test_remove_missing_transition_lists_available(base_fsm: dict) -> None:
    patch = {
        "schema_version": "1.0.0",
        "patch_id": "missing",
        "target_fsm_id": "fsm_test_01",
        "operations": [
            {"op": "remove_transition", "from": "s0", "event": "z", "to": "s1"}
        ],
    }
    with pytest.raises(PatchEngineError) as exc_info:
        apply_patch(base_fsm, patch)
    assert "available:" in str(exc_info.value).lower()


def test_update_wrong_old_to_hints_targets(base_fsm: dict) -> None:
    patch = {
        "schema_version": "1.0.0",
        "patch_id": "bad_update",
        "target_fsm_id": "fsm_test_01",
        "operations": [
            {
                "op": "update_transition",
                "from": "s0",
                "event": "a",
                "old_to": "s0",
                "new_to": "s1",
            }
        ],
    }
    with pytest.raises(PatchEngineError) as exc_info:
        apply_patch(base_fsm, patch)
    assert "targets:" in str(exc_info.value)


def test_unsupported_state_operation_rejected(base_fsm: dict) -> None:
    patch = {
        "schema_version": "1.0.0",
        "patch_id": "state_op",
        "target_fsm_id": "fsm_test_01",
        "operations": [{"op": "add_state", "state": "s2"}],
    }
    with pytest.raises(PatchEngineError) as exc_info:
        apply_patch(base_fsm, patch)
    assert "not supported in patch engine v1" in str(exc_info.value)


def test_target_fsm_id_mismatch(base_fsm: dict) -> None:
    patch = {
        "schema_version": "1.0.0",
        "patch_id": "wrong",
        "target_fsm_id": "other",
        "operations": [
            {"op": "add_transition", "from": "s1", "event": "b", "to": "s0"}
        ],
    }
    with pytest.raises(PatchEngineError, match="target_fsm_id"):
        apply_patch(base_fsm, patch)


def test_input_fsm_not_mutated_on_failure(base_fsm: dict) -> None:
    original = json.loads(json.dumps(base_fsm))
    patch = {
        "schema_version": "1.0.0",
        "patch_id": "fail",
        "target_fsm_id": "fsm_test_01",
        "operations": [
            {"op": "add_transition", "from": "s1", "event": "b", "to": "s0"},
            {"op": "add_transition", "from": "s0", "event": "a", "to": "s1"},
        ],
    }
    with pytest.raises(PatchEngineError):
        apply_patch(base_fsm, patch)
    assert base_fsm == original


def test_canonicalize_deterministic_ordering(base_fsm: dict) -> None:
    shuffled = {
        **base_fsm,
        "states": ["s1", "s0"],
        "transitions": [{"from": "s0", "event": "a", "to": "s1"}],
        "alphabet": ["a"],
    }
    c1 = canonicalize_fsm(shuffled)
    c2 = canonicalize_fsm(
        {
            **base_fsm,
            "states": ["s0", "s1"],
            "transitions": [{"from": "s0", "event": "a", "to": "s1"}],
        }
    )
    assert c1["states"] == ["s0", "s1"]
    assert c1 == c2


def test_examples_traffic_light_patch(tmp_path: Path) -> None:
    fsm_path = EXAMPLES / "traffic_light" / "candidate_fsm.json"
    patch_path = EXAMPLES / "traffic_light" / "patch_fix_yellow.json"
    expected_path = EXAMPLES / "traffic_light" / "expected_fsm.json"

    fsm = load_fsm(fsm_path)
    patch = load_patch(patch_path)
    result = apply_patch(fsm, patch)
    expected = load_fsm(expected_path)
    assert result == canonicalize_fsm(expected)


def test_write_fsm_roundtrip(tmp_path: Path, base_fsm: dict) -> None:
    out = tmp_path / "out.json"
    write_fsm(canonicalize_fsm(base_fsm), out)
    loaded = load_fsm(out)
    assert loaded["states"] == ["s0", "s1"]
    assert loaded["transitions"] == base_fsm["transitions"]
