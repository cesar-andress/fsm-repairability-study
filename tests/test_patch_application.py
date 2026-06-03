"""Integration tests: patch engine with scoring."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from apply_patch import PatchEngineError, apply_patch  # noqa: E402
from score_repair import score_against_suite  # noqa: E402
from validate_fsm import validate_fsm_document, validate_referential_integrity  # noqa: E402


@pytest.fixture
def fsm() -> dict:
    return {
        "schema_version": "1.0.0",
        "id": "fsm_test_01",
        "states": ["s0", "s1"],
        "initial_state": "s0",
        "alphabet": ["a"],
        "transitions": [{"from": "s0", "event": "a", "to": "s1"}],
    }


def test_apply_add_transition(fsm: dict) -> None:
    patch = {
        "schema_version": "1.0.0",
        "patch_id": "p1",
        "target_fsm_id": "fsm_test_01",
        "operations": [
            {"op": "add_transition", "from": "s1", "event": "b", "to": "s0"}
        ],
    }
    repaired = apply_patch(fsm, patch)
    assert validate_fsm_document(repaired) == []
    assert validate_referential_integrity(repaired) == []
    assert {"from": "s1", "event": "b", "to": "s0"} in repaired["transitions"]


def test_score_trace_check_passes_after_repair(fsm: dict) -> None:
    patch = {
        "schema_version": "1.0.0",
        "patch_id": "p2",
        "target_fsm_id": "fsm_test_01",
        "operations": [
            {"op": "add_transition", "from": "s1", "event": "b", "to": "s0"}
        ],
    }
    repaired = apply_patch(fsm, patch)
    suite = {
        "suite_id": "suite_stub",
        "tests": [
            {
                "test_id": "c1",
                "type": "trace",
                "events": ["a", "b"],
                "expected_states": ["s0", "s1", "s0"],
            }
        ],
    }
    result = score_against_suite(repaired, suite)
    assert result["passed"] is True
    assert result["bpr"] == 1.0


def test_wrong_target_fsm_id_raises(fsm: dict) -> None:
    patch = {
        "schema_version": "1.0.0",
        "patch_id": "p3",
        "target_fsm_id": "other",
        "operations": [
            {"op": "add_transition", "from": "s1", "event": "b", "to": "s0"}
        ],
    }
    with pytest.raises(PatchEngineError, match="target_fsm_id"):
        apply_patch(fsm, patch)
