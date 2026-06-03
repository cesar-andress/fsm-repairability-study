"""Tests for operation-inferred localized repair prompt."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PROMPT = REPO_ROOT / "prompts" / "repair_localized_feedback_operation_inferred.md"

REQUIRED = (
    "{{requirement_text}}",
    "{{candidate_fsm_json}}",
    "{{localized_feedback_json}}",
)


def test_operation_inferred_template_exists() -> None:
    assert PROMPT.is_file()


def test_operation_inferred_placeholders() -> None:
    text = PROMPT.read_text(encoding="utf-8")
    for ph in REQUIRED:
        assert ph in text


def test_do_not_emit_patch_operations(text: str = PROMPT.read_text(encoding="utf-8")) -> None:
    lower = text.lower()
    assert "do not emit patch operations" in lower
    assert "do not emit add_transition" in lower
    assert "do not emit update_transition" in lower


def test_json_only_output(text: str = PROMPT.read_text(encoding="utf-8")) -> None:
    assert "return only valid json" in text.lower()


def test_corrections_schema_in_prompt(text: str = PROMPT.read_text(encoding="utf-8")) -> None:
    assert '"corrections"' in text
    assert '"desired_target"' in text
    assert '"rationale"' in text
