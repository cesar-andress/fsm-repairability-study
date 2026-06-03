"""Tests for frozen repair prompt templates (conditions C, D, E)."""

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

PROMPT_FILES = {
    "C": PROMPTS / "repair_binary_feedback.md",
    "D": PROMPTS / "repair_trace_feedback.md",
    "E": PROMPTS / "repair_localized_feedback.md",
}


@pytest.fixture(params=["C", "D", "E"], ids=["binary", "trace", "localized"])
def prompt_path(request: pytest.FixtureRequest) -> Path:
    path = PROMPT_FILES[request.param]
    assert path.is_file(), f"missing prompt file: {path}"
    return path


@pytest.fixture(params=["C", "D", "E"], ids=["binary", "trace", "localized"])
def prompt_text(prompt_path: Path) -> str:
    return prompt_path.read_text(encoding="utf-8")


def test_all_three_prompt_files_exist() -> None:
    for path in PROMPT_FILES.values():
        assert path.is_file(), path


def test_required_placeholders_in_all_prompts(prompt_text: str) -> None:
    for placeholder in REQUIRED_PLACEHOLDERS:
        assert placeholder in prompt_text


def test_prompts_forbid_full_fsm_regeneration(prompt_text: str) -> None:
    lower = prompt_text.lower()
    assert "full fsm regeneration" in lower or "no full fsm regeneration" in lower
    assert "forbid" in lower or "do not" in lower


def test_prompts_require_json_only_output(prompt_text: str) -> None:
    lower = prompt_text.lower()
    assert "json only" in lower or "only" in lower and "json" in lower
    assert "no markdown" in lower or "no markdown fences" in lower


def test_binary_prompt_does_not_offer_trace_or_localization_evidence() -> None:
    text = PROMPT_FILES["C"].read_text(encoding="utf-8")
    allowed = _section_after(text, "## Allowed diagnostic information")
    assert allowed is not None
    allowed_lower = allowed.lower()
    assert "trace" not in _allowed_bullets_only(allowed_lower)
    assert "expected" not in _allowed_bullets_only(allowed_lower)
    assert "observed" not in _allowed_bullets_only(allowed_lower)
    assert "localization" not in _allowed_bullets_only(allowed_lower)
    assert "do not" in text.lower() and "trace" in text.lower()


def test_trace_prompt_includes_witnesses_not_localization() -> None:
    text = PROMPT_FILES["D"].read_text(encoding="utf-8")
    allowed = _section_after(text, "## Allowed diagnostic information")
    assert allowed is not None
    assert "input_trace" in allowed or "trace" in allowed.lower()
    assert "expected" in allowed.lower()
    assert "observed" in allowed.lower()
    assert "do not" in allowed.lower() and "localization" in allowed.lower()


def test_localized_prompt_mentions_localization() -> None:
    text = PROMPT_FILES["E"].read_text(encoding="utf-8")
    assert "localization" in text.lower()
    assert "suspicious_states" in text
    assert "missing_transition_candidates" in text
    assert "extra_transition_candidates" in text


def test_prompts_reference_patch_schema(prompt_text: str) -> None:
    assert "patch schema" in prompt_text.lower()
    assert "{{patch_schema_json}}" in prompt_text


def test_prompts_include_required_sections(prompt_text: str) -> None:
    for heading in (
        "## Role",
        "## Task",
        "## Inputs",
        "## Constraints",
        "## Output contract",
        "## Patch operation policy",
        "## Failure handling",
    ):
        assert heading in prompt_text


def test_failure_handling_abstention_rule(prompt_text: str) -> None:
    section = _section_after(prompt_text, "## Failure handling")
    assert section is not None
    assert "operations" in section and "[]" in section
    assert "rationale" in section.lower()


def _section_after(text: str, heading_prefix: str) -> str | None:
    pattern = re.escape(heading_prefix) + r"[^\n]*\n(.*?)(?=\n## |\Z)"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    return match.group(1) if match else None


def _allowed_bullets_only(allowed_section: str) -> str:
    """Text of bullet lines in allowed section (lines starting with -)."""
    lines = [
        line.lower()
        for line in allowed_section.splitlines()
        if line.strip().startswith("-")
    ]
    return "\n".join(lines)
