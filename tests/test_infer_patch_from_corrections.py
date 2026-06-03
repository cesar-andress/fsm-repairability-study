"""Tests for behavioural correction → patch inference."""

from __future__ import annotations

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
from infer_patch_from_corrections import (  # noqa: E402
    CorrectionInferenceError,
    infer_patch_from_corrections,
)
from generate_patch_ollama import (  # noqa: E402
    PatchGenerationError,
    generate_patch_ollama,
    resolve_condition,
)
from apply_patch import apply_patch, validate_patch_document  # noqa: E402

CANDIDATE = json.loads((CASE_DIR / "candidate_fsm.json").read_text(encoding="utf-8"))
CORRECTION_UPDATE = {
    "schema_version": "1.0.0",
    "corrections": [{"from": "s1", "event": "b", "desired_target": "s0"}],
    "rationale": "Return to s0 after b",
}
CORRECTION_EMPTY = {
    "schema_version": "1.0.0",
    "corrections": [],
    "rationale": "Cannot infer safe fix",
}


def test_infer_does_not_mutate_candidate() -> None:
    before = json.dumps(CANDIDATE)
    infer_patch_from_corrections(CANDIDATE, CORRECTION_UPDATE)
    assert json.dumps(CANDIDATE) == before


def test_infer_update_transition_for_existing_edge() -> None:
    candidate = json.loads(json.dumps(CANDIDATE))
    patch = infer_patch_from_corrections(candidate, CORRECTION_UPDATE)
    assert len(patch["operations"]) == 1
    op = patch["operations"][0]
    assert op["op"] == "update_transition"
    assert op["old_to"] == "s1"
    assert op["new_to"] == "s0"
    validate_patch_document(patch)
    repaired = apply_patch(candidate, patch)
    assert repaired["transitions"][1]["to"] == "s0"


def test_infer_add_transition_for_missing_edge() -> None:
    candidate = {
        "schema_version": "1.0.0",
        "id": "x",
        "states": ["s0", "s1"],
        "initial_state": "s0",
        "alphabet": ["a"],
        "transitions": [{"from": "s0", "event": "a", "to": "s1"}],
    }
    doc = {
        "schema_version": "1.0.0",
        "corrections": [{"from": "s1", "event": "b", "desired_target": "s0"}],
        "rationale": "Close loop",
    }
    patch = infer_patch_from_corrections(candidate, doc)
    assert patch["operations"][0]["op"] == "add_transition"


def test_empty_corrections_do_not_infer_patch() -> None:
    with pytest.raises(CorrectionInferenceError, match="abstention"):
        infer_patch_from_corrections(CANDIDATE, CORRECTION_EMPTY)


def test_missing_state_raises() -> None:
    doc = {
        "schema_version": "1.0.0",
        "corrections": [{"from": "s1", "event": "b", "desired_target": "ghost"}],
        "rationale": "bad",
    }
    with pytest.raises(CorrectionInferenceError, match="not in candidate states"):
        infer_patch_from_corrections(CANDIDATE, doc)


def test_resolve_operation_inferred_template() -> None:
    path = resolve_condition(
        "patch_localized_feedback", prompt_variant="operation-inferred"
    )
    assert path.name == "repair_localized_feedback_operation_inferred.md"


def test_operation_inferred_rejected_for_binary() -> None:
    with pytest.raises(PatchGenerationError, match="operation-inferred"):
        resolve_condition("patch_binary_feedback", prompt_variant="operation-inferred")


@mock.patch("generate_patch_ollama.generate")
def test_generate_operation_inferred_writes_corrections_and_patch(
    mock_generate, tmp_path: Path
) -> None:
    mock_generate.return_value = json.dumps(CORRECTION_UPDATE)
    req = tmp_path / "req.txt"
    req.write_text("requirement", encoding="utf-8")
    fsm = tmp_path / "fsm.json"
    fsm.write_text(json.dumps(CANDIDATE), encoding="utf-8")
    diag = tmp_path / "diag.json"
    diag.write_text("{}", encoding="utf-8")
    out = tmp_path / "out"
    generate_patch_ollama(
        condition="patch_localized_feedback",
        requirement_path=req,
        candidate_fsm_path=fsm,
        diagnostic_path=diag,
        patch_schema_path=REPO_ROOT / "schemas" / "patch.schema.json",
        model="test",
        output_dir=out,
        prompt_variant="operation-inferred",
    )
    assert (out / "corrections.json").is_file()
    patch = json.loads((out / "patch.json").read_text(encoding="utf-8"))
    assert patch["operations"][0]["op"] == "update_transition"
