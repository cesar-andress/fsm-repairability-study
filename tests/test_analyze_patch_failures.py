"""Tests for patch failure analysis utility (read-only pilot inspection)."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PILOT_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "patch_failure_pilot"
SCRIPTS = REPO_ROOT / "scripts"

sys.path.insert(0, str(SCRIPTS))
from analyze_patch_failures import (  # noqa: E402
    classify_failure_message,
    analyze_patch_failures,
    write_outputs,
)


def _fixture_snapshot() -> dict[str, str]:
    """SHA256-free snapshot: relative path -> content hash via size+text."""
    snap: dict[str, str] = {}
    for path in sorted(PILOT_FIXTURE.rglob("*")):
        if path.is_file() and path.name not in (
            "patch_failure_summary.csv",
            "patch_failure_summary.json",
        ):
            snap[str(path.relative_to(PILOT_FIXTURE))] = path.read_text(encoding="utf-8")
    return snap


def test_classify_failure_message_patterns() -> None:
    assert (
        classify_failure_message(
            "operation[0] add_transition: duplicate (from, event) ('s0', 'a')"
        )
        == "duplicate_transition"
    )
    assert (
        classify_failure_message("from state 'ghost' not in states ['s0']")
        == "missing_state"
    )
    assert (
        classify_failure_message("remove_transition: no transition 's9' --'z'--> 's0'")
        == "transition_not_found"
    )


def test_analyze_does_not_modify_pilot_fixture(tmp_path: Path) -> None:
    before = _fixture_snapshot()
    records, summary = analyze_patch_failures(PILOT_FIXTURE)
    write_outputs(PILOT_FIXTURE, records, summary, output_dir=tmp_path)
    after = _fixture_snapshot()
    assert before == after
    assert (PILOT_FIXTURE / "patch_failure_summary.csv").is_file() is False


def test_analyze_extracts_failures_and_aggregates(tmp_path: Path) -> None:
    records, summary = analyze_patch_failures(PILOT_FIXTURE)
    assert len(records) == 3

    classes = {r.failure_class for r in records}
    assert "duplicate_transition" in classes
    assert "missing_state" in classes
    assert "transition_not_found" in classes

    dup = next(r for r in records if r.failure_class == "duplicate_transition")
    assert dup.condition == "C"
    assert dup.operation_index == "0"
    assert dup.operation_type == "add_transition"
    assert dup.source_state == "s0"
    assert dup.event == "a"
    assert dup.patch_path.endswith("patch.json")

    agg = summary["aggregates"]
    assert agg["total_failures"] == 3
    assert agg["by_condition"]["C"] == 1
    assert agg["by_condition"]["D"] == 1
    assert agg["by_condition"]["E"] == 1
    assert agg["by_failure_class"]["duplicate_transition"] == 1
    assert agg["by_system_id"]["atm_sys"] == 2
    assert agg["by_system_id"]["queue_sys"] == 1
    assert agg["by_operation_type"]["add_transition"] == 2

    csv_path, json_path = write_outputs(
        PILOT_FIXTURE, records, summary, output_dir=tmp_path
    )
    with csv_path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 3
    assert set(rows[0].keys()) >= {
        "case_id",
        "condition",
        "status",
        "error_message",
        "failure_class",
        "operation_index",
    }

    doc = json.loads(json_path.read_text(encoding="utf-8"))
    assert doc["aggregates"]["total_failures"] == 3
    assert len(doc["failures"]) == 3
