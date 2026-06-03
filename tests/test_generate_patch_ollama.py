"""Tests for Ollama patch generation backend (no live Ollama required)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest import mock

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
CASE_DIR = REPO_ROOT / "tests" / "fixtures" / "dry_run_case"
OLLAMA_FIXTURES = REPO_ROOT / "tests" / "fixtures" / "ollama"
PATCH_SCHEMA = REPO_ROOT / "schemas" / "patch.schema.json"
SCRIPTS = REPO_ROOT / "scripts"

sys.path.insert(0, str(SCRIPTS))
from generate_patch_ollama import (  # noqa: E402
    PatchGenerationError,
    extract_patch_json,
    generate_patch_ollama,
    load_requirement_text,
    render_repair_prompt,
    resolve_condition,
)
from apply_patch import validate_patch_document  # noqa: E402

REQUIREMENT_SNIPPET = "On events a then b the machine must return to the initial state s0."


@pytest.fixture
def candidate_fsm() -> dict:
    return json.loads((CASE_DIR / "candidate_fsm.json").read_text(encoding="utf-8"))


@pytest.fixture
def diagnostic_trace() -> dict:
    return {
        "schema_version": "2.0.0",
        "identity": {
            "diagnostic_id": "diag_dry_run_test",
            "case_id": "dry_run_case",
            "run_id": "dry_run__patch_trace_feedback__test",
            "iteration_index": 0,
            "diagnostic_level": "trace",
        },
        "scoring_summary": {"bpr": 0.67, "failed_tests": 1},
        "failed_checks": [
            {
                "test_id": "trace_ab",
                "failure_type": "trace_mismatch",
                "expected": {"states": ["s0", "s1", "s0"]},
                "observed": {"states": ["s0", "s1", "s1"]},
            }
        ],
    }


@pytest.fixture
def patch_schema_doc() -> dict:
    return json.loads(PATCH_SCHEMA.read_text(encoding="utf-8"))


def test_resolve_condition_maps_templates() -> None:
    path = resolve_condition("patch_trace_feedback")
    assert path.name == "repair_trace_feedback.md"


def test_resolve_operation_aware_variant() -> None:
    path = resolve_condition("patch_binary_feedback", prompt_variant="operation-aware")
    assert path.name == "repair_binary_feedback_operation_aware.md"
    text = path.read_text(encoding="utf-8")
    assert "Transition Decision Checklist" in text


def test_resolve_default_variant_unchanged() -> None:
    assert (
        resolve_condition("patch_localized_feedback").name
        == "repair_localized_feedback.md"
    )


def test_render_prompt_replaces_placeholders(
    candidate_fsm: dict, diagnostic_trace: dict, patch_schema_doc: dict
) -> None:
    template = resolve_condition("patch_binary_feedback")
    prompt = render_repair_prompt(
        template,
        requirement_text=REQUIREMENT_SNIPPET,
        candidate_fsm=candidate_fsm,
        diagnostic=diagnostic_trace,
        patch_schema=patch_schema_doc,
    )
    assert "{{" not in prompt
    assert REQUIREMENT_SNIPPET in prompt
    assert candidate_fsm["id"] in prompt
    assert "diag_dry_run_test" in prompt
    assert '"FsmPatch"' in prompt or "patch_id" in prompt


def test_load_requirement_from_json_case_field(tmp_path: Path) -> None:
    req_path = tmp_path / "req.json"
    req_path.write_text(
        json.dumps({"requirement_text": REQUIREMENT_SNIPPET}),
        encoding="utf-8",
    )
    assert load_requirement_text(req_path) == REQUIREMENT_SNIPPET


def test_extract_json_from_markdown_fence() -> None:
    raw = (OLLAMA_FIXTURES / "raw_patch_fenced.txt").read_text(encoding="utf-8")
    patch = extract_patch_json(raw)
    assert patch["patch_id"] == "pilot_fix_b"
    assert patch["operations"][0]["op"] == "update_transition"


def test_extract_json_from_plain_response() -> None:
    raw = (OLLAMA_FIXTURES / "raw_patch_plain.json").read_text(encoding="utf-8")
    patch = extract_patch_json(raw)
    assert patch["patch_id"] == "pilot_plain"


def test_extract_json_fails_on_empty() -> None:
    with pytest.raises(PatchGenerationError, match="empty"):
        extract_patch_json("   ")


def test_extract_json_fails_without_object() -> None:
    with pytest.raises(PatchGenerationError, match="no JSON object"):
        extract_patch_json("no structured output here")


def test_validate_extracted_patches(
    candidate_fsm: dict,
) -> None:
    for name in ("raw_patch_fenced.txt", "raw_patch_plain.json"):
        raw = (OLLAMA_FIXTURES / name).read_text(encoding="utf-8")
        patch = extract_patch_json(raw)
        patch["target_fsm_id"] = candidate_fsm["id"]
        validate_patch_document(patch)


def test_generate_patch_ollama_writes_outputs(
    tmp_path: Path,
    candidate_fsm: dict,
    diagnostic_trace: dict,
    patch_schema_doc: dict,
) -> None:
    req_file = tmp_path / "requirement.txt"
    req_file.write_text(REQUIREMENT_SNIPPET, encoding="utf-8")
    fsm_path = tmp_path / "candidate.json"
    fsm_path.write_text(json.dumps(candidate_fsm), encoding="utf-8")
    diag_path = tmp_path / "diagnostic.json"
    diag_path.write_text(json.dumps(diagnostic_trace), encoding="utf-8")
    schema_path = tmp_path / "patch.schema.json"
    schema_path.write_text(json.dumps(patch_schema_doc), encoding="utf-8")

    raw = (OLLAMA_FIXTURES / "raw_patch_fenced.txt").read_text(encoding="utf-8")
    out_dir = tmp_path / "ollama_out"

    with mock.patch(
        "generate_patch_ollama.generate",
        return_value=raw,
    ):
        generate_patch_ollama(
            condition="patch_trace_feedback",
            requirement_path=req_file,
            candidate_fsm_path=fsm_path,
            diagnostic_path=diag_path,
            patch_schema_path=schema_path,
            model="test-model",
            output_dir=out_dir,
        )

    assert (out_dir / "prompt.txt").is_file()
    assert REQUIREMENT_SNIPPET in (out_dir / "prompt.txt").read_text(encoding="utf-8")
    assert (out_dir / "raw_response.txt").read_text(encoding="utf-8") == raw
    patch = json.loads((out_dir / "patch.json").read_text(encoding="utf-8"))
    assert patch["patch_id"] == "pilot_fix_b"
    validate_patch_document(patch)


def test_invalid_condition_raises() -> None:
    with pytest.raises(PatchGenerationError, match="unsupported condition"):
        resolve_condition("baseline_no_repair")


def test_invalid_prompt_variant_raises() -> None:
    with pytest.raises(PatchGenerationError, match="unsupported prompt_variant"):
        resolve_condition("patch_binary_feedback", prompt_variant="verbose")


def test_generate_operation_aware_uses_template(
    tmp_path: Path,
    candidate_fsm: dict,
    diagnostic_trace: dict,
    patch_schema_doc: dict,
) -> None:
    req_file = tmp_path / "requirement.txt"
    req_file.write_text(REQUIREMENT_SNIPPET, encoding="utf-8")
    fsm_path = tmp_path / "candidate.json"
    fsm_path.write_text(json.dumps(candidate_fsm), encoding="utf-8")
    diag_path = tmp_path / "diagnostic.json"
    diag_path.write_text(json.dumps(diagnostic_trace), encoding="utf-8")
    schema_path = tmp_path / "patch.schema.json"
    schema_path.write_text(json.dumps(patch_schema_doc), encoding="utf-8")
    out_dir = tmp_path / "ollama_oa"

    raw = (OLLAMA_FIXTURES / "raw_patch_fenced.txt").read_text(encoding="utf-8")
    with mock.patch("generate_patch_ollama.generate", return_value=raw):
        prompt, _raw, _patch = generate_patch_ollama(
            condition="patch_trace_feedback",
            requirement_path=req_file,
            candidate_fsm_path=fsm_path,
            diagnostic_path=diag_path,
            patch_schema_path=schema_path,
            model="test-model",
            output_dir=out_dir,
            prompt_variant="operation-aware",
        )
    assert "Transition Decision Checklist" in prompt
    assert "never use `add_transition`" in prompt.lower() or "never use add_transition" in prompt.lower()
