"""Tests for environment condition and model configuration."""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
CONDITION_IDS = {
    "baseline_no_repair",
    "baseline_full_regeneration",
    "patch_binary_feedback",
    "patch_trace_feedback",
    "patch_localized_feedback",
}


def test_conditions_yaml_defines_primary_iv() -> None:
    path = REPO_ROOT / "environment" / "conditions.yaml"
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    ids = {c["condition_id"] for c in cfg["conditions"]}
    assert ids == CONDITION_IDS


def test_baseline_no_repair_does_not_use_llm() -> None:
    cfg = yaml.safe_load(
        (REPO_ROOT / "environment" / "conditions.yaml").read_text(encoding="utf-8")
    )
    by_id = {c["condition_id"]: c for c in cfg["conditions"]}
    assert by_id["baseline_no_repair"]["uses_llm"] is False
    assert by_id["baseline_full_regeneration"]["uses_llm"] is True


def test_ollama_models_yaml_has_primary_and_sensitivity() -> None:
    cfg = yaml.safe_load(
        (REPO_ROOT / "environment" / "ollama_models.yaml").read_text(encoding="utf-8")
    )
    assert "primary_model" in cfg
    assert "sensitivity_models" in cfg
    assert cfg["ollama"]["base_url"].startswith("http")
