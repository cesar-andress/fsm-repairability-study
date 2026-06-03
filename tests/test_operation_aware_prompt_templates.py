"""Tests for operation-aware repair prompt templates (second pilot)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PROMPTS = REPO_ROOT / "prompts"

REQUIRED_PLACEHOLDERS = (
    "{{requirement_text}}",
    "{{candidate_fsm_json}}",
    "{{diagnostic_json}}",
    "{{patch_schema_json}}",
)

OPERATION_AWARE_FILES = {
    "C": PROMPTS / "repair_binary_feedback_operation_aware.md",
    "D": PROMPTS / "repair_trace_feedback_operation_aware.md",
    "E": PROMPTS / "repair_localized_feedback_operation_aware.md",
}


@pytest.fixture(params=["C", "D", "E"], ids=["binary", "trace", "localized"])
def prompt_path(request: pytest.FixtureRequest) -> Path:
    path = OPERATION_AWARE_FILES[request.param]
    assert path.is_file(), f"missing prompt file: {path}"
    return path


@pytest.fixture(params=["C", "D", "E"], ids=["binary", "trace", "localized"])
def prompt_text(prompt_path: Path) -> str:
    return prompt_path.read_text(encoding="utf-8")


def test_all_operation_aware_templates_exist() -> None:
    for path in OPERATION_AWARE_FILES.values():
        assert path.is_file(), path


def test_required_placeholders_in_all_templates(prompt_text: str) -> None:
    for placeholder in REQUIRED_PLACEHOLDERS:
        assert placeholder in prompt_text


def test_duplicate_transition_rule_appears(prompt_text: str) -> None:
    lower = prompt_text.lower()
    assert "duplicate" in lower
    assert "from" in lower and "event" in lower
    assert "never use `add_transition`" in lower or "never use add_transition" in lower


def test_state_membership_rule_appears(prompt_text: str) -> None:
    lower = prompt_text.lower()
    assert "candidate_fsm_json.states" in lower
    assert "state membership" in lower or "not listed" in lower


def test_old_to_new_to_rule_appears(prompt_text: str) -> None:
    lower = prompt_text.lower()
    assert "old_to" in lower
    assert "new_to" in lower
    assert "equals" in lower


def test_json_only_rule_appears(prompt_text: str) -> None:
    lower = prompt_text.lower()
    assert "output only json" in lower or "json only" in lower
    assert "no markdown" in lower or "no markdown fences" in lower


def test_scan_before_add_rule(prompt_text: str) -> None:
    section = _section_after(prompt_text, "## Operation-aware transition rules")
    assert section is not None
    assert "scan" in section.lower()
    assert "candidate_fsm_json.transitions" in section


def test_abstain_on_forced_duplicate(prompt_text: str) -> None:
    section = _section_after(prompt_text, "## Operation-aware transition rules")
    assert section is not None
    assert "operations" in section and "[]" in section
    assert "rationale" in section.lower()


def _section_after(text: str, heading_prefix: str) -> str | None:
    pattern = re.escape(heading_prefix) + r"[^\n]*\n(.*?)(?=\n## |\Z)"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    return match.group(1) if match else None
