"""Tests for operation-aware repair prompt templates (second pilot)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PROMPTS = REPO_ROOT / "prompts"
CHECKLIST_SNIPPET = PROMPTS / "snippets" / "transition_decision_checklist.md"

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


@pytest.fixture(scope="module")
def checklist_snippet() -> str:
    assert CHECKLIST_SNIPPET.is_file()
    return CHECKLIST_SNIPPET.read_text(encoding="utf-8").strip()


def test_all_operation_aware_templates_exist() -> None:
    for path in OPERATION_AWARE_FILES.values():
        assert path.is_file(), path


def test_checklist_snippet_exists() -> None:
    assert CHECKLIST_SNIPPET.is_file()


def test_required_placeholders_in_all_templates(prompt_text: str) -> None:
    for placeholder in REQUIRED_PLACEHOLDERS:
        assert placeholder in prompt_text


def test_templates_embed_canonical_checklist(
    prompt_text: str, checklist_snippet: str
) -> None:
    assert checklist_snippet in prompt_text


def test_mandatory_checklist_heading(prompt_text: str) -> None:
    assert "## Transition Decision Checklist (MANDATORY)" in prompt_text


def test_duplicate_transition_rule_appears(prompt_text: str) -> None:
    lower = prompt_text.lower()
    assert "never use `add_transition`" in lower or "never use add_transition" in lower
    assert "duplicated transition" in lower


def test_state_and_event_membership_in_step5(prompt_text: str) -> None:
    section = _section_after(prompt_text, "## Transition Decision Checklist")
    assert section is not None
    assert "candidate_fsm_json.states" in section
    assert "candidate_fsm_json.alphabet" in section


def test_determinism_verification_in_step5(prompt_text: str) -> None:
    section = _section_after(prompt_text, "## Transition Decision Checklist")
    assert section is not None
    assert "determinism" in section.lower()


def test_old_to_new_to_rule_in_step3(prompt_text: str) -> None:
    section = _section_after(prompt_text, "## Transition Decision Checklist")
    assert section is not None
    assert "old_to" in section
    assert "new_to" in section
    assert "different" in section.lower()


def test_json_only_rule_appears(prompt_text: str) -> None:
    lower = prompt_text.lower()
    assert "json only" in lower
    assert "no markdown" in lower or "no markdown fences" in lower


def test_step6_abstain_example(prompt_text: str) -> None:
    section = _section_after(prompt_text, "## Transition Decision Checklist")
    assert section is not None
    assert "Unable to determine a safe repair" in section
    assert '"operations": []' in section


def test_scan_transitions_step1(prompt_text: str) -> None:
    section = _section_after(prompt_text, "## Transition Decision Checklist")
    assert section is not None
    assert "Step 1" in section
    assert "candidate_fsm_json.transitions" in section


def test_transition_operation_selection_references_checklist(prompt_text: str) -> None:
    section = _section_after(prompt_text, "## Transition operation selection")
    assert section is not None
    assert "Transition Decision Checklist" in section


def _section_after(text: str, heading_prefix: str) -> str | None:
    pattern = re.escape(heading_prefix) + r"[^\n]*\n(.*?)(?=\n## |\Z)"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    return match.group(1) if match else None
