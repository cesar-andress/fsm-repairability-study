"""Tests for patch failure taxonomy analysis."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PILOT_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "patch_failure_pilot"
PAPER_PILOT = REPO_ROOT.parent / "paper" / "experiments" / "frozen_pilot_001"
SCRIPTS = REPO_ROOT / "scripts"

sys.path.insert(0, str(SCRIPTS))
from analyze_patch_failure_taxonomy import (  # noqa: E402
    TAXONOMY_CLASSES,
    analyze_patch_failure_taxonomy,
    build_taxonomy,
    render_taxonomy_tex,
    select_examples,
    write_outputs,
)
from analyze_patch_failures import analyze_patch_failures  # noqa: E402


def test_build_taxonomy_counts_fixture() -> None:
    records, summary = analyze_patch_failures(PILOT_FIXTURE)
    body = build_taxonomy(records, summary["aggregates"])
    assert body["total_failures"] == 3
    assert body["classes"]["duplicate_transition"]["count"] == 1
    assert body["classes"]["missing_state"]["count"] == 1
    assert body["classes"]["transition_not_found"]["count"] == 1
    assert len(body["examples"]) >= 3


def test_select_examples_dedupes_same_message() -> None:
    records, _ = analyze_patch_failures(PILOT_FIXTURE)
    examples = select_examples(records, max_per_class=2)
    msgs = [e["error_message"] for e in examples]
    assert len(msgs) == len(set(msgs[:3]))


def test_render_tex_structure(tmp_path: Path) -> None:
    doc, tex = analyze_patch_failure_taxonomy(PILOT_FIXTURE)
    assert r"\begin{table}" in tex
    assert r"\label{tab:patch_failure_taxonomy}" in tex
    for cls in TAXONOMY_CLASSES:
        assert cls.replace("_", r"\_") in tex or cls in tex
    _latex_balanced(tex)


def _latex_balanced(tex: str) -> None:
    for env in ("table", "tabular", "itemize"):
        assert len(re.findall(rf"\\begin\{{{env}\}}", tex)) == len(
            re.findall(rf"\\end\{{{env}\}}", tex)
        )


def test_write_outputs(tmp_path: Path) -> None:
    doc, tex = analyze_patch_failure_taxonomy(PILOT_FIXTURE)
    json_path, tex_path = write_outputs(
        PILOT_FIXTURE, doc, tex, output_dir=tmp_path
    )
    loaded = json.loads(json_path.read_text(encoding="utf-8"))
    assert loaded["total_failures"] == 3
    assert set(loaded["classes"]) == set(TAXONOMY_CLASSES)
    assert tex_path.is_file()


@pytest.mark.skipif(not PAPER_PILOT.is_dir(), reason="paper pilot not present")
def test_frozen_pilot_duplicate_dominant() -> None:
    doc, _tex = analyze_patch_failure_taxonomy(PAPER_PILOT)
    dup = doc["classes"]["duplicate_transition"]
    assert dup["count"] == 47
    assert dup["share"] > 0.5
    assert doc["total_failures"] == 64
