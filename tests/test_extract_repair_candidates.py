"""Tests for repair candidate extraction from benchmark exports."""

from __future__ import annotations

import csv
import json
import sys
import warnings
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

REPO_ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_DIR = REPO_ROOT / "tests" / "fixtures" / "benchmark_export"
EMSE_DIR = REPO_ROOT / "tests" / "fixtures" / "emse_campaign"
SCHEMAS = REPO_ROOT / "schemas"
SCRIPTS = REPO_ROOT / "scripts"

sys.path.insert(0, str(SCRIPTS))
from extract_repair_candidates import (  # noqa: E402
    ExtractionError,
    build_emse_case_id,
    evaluate_entry,
    extract_repair_candidates,
    load_benchmark_manifest,
    load_emse_ingestion_manifest,
    structurally_valid_fsm,
)


def _repair_case_validator() -> Draft202012Validator:
    registry: Registry = Registry()
    for path in sorted(SCHEMAS.glob("*.json")):
        with path.open(encoding="utf-8") as f:
            registry = registry.with_resource(path.name, Resource.from_contents(json.load(f)))
    with (SCHEMAS / "repair_case.schema.json").open(encoding="utf-8") as f:
        schema = json.load(f)
    return Draft202012Validator(schema, registry=registry)


def test_load_benchmark_manifest() -> None:
    campaign_id, entries = load_benchmark_manifest(BENCHMARK_DIR)
    assert campaign_id == "fixture_benchmark_export"
    assert len(entries) == 3


def test_selection_criteria_on_fixtures() -> None:
    campaign_id, entries = load_benchmark_manifest(BENCHMARK_DIR)
    by_id = {e.case_id: e for e in entries}

    loop = evaluate_entry(BENCHMARK_DIR, by_id["pilot_loop"], campaign_id=campaign_id)
    assert loop.selected is True
    assert loop.row is not None
    assert loop.row.initial_bpr < 1.0
    assert loop.row.failed_tests >= 1

    passing = evaluate_entry(BENCHMARK_DIR, by_id["pilot_pass"], campaign_id=campaign_id)
    assert passing.selected is False
    assert "BPR" in passing.reason

    invalid = evaluate_entry(BENCHMARK_DIR, by_id["pilot_invalid"], campaign_id=campaign_id)
    assert invalid.selected is False
    assert "invalid" in invalid.reason.lower()


def test_extract_writes_pilot_case_bundle(tmp_path: Path) -> None:
    out = tmp_path / "pilot_cases"
    selected, evaluated = extract_repair_candidates(
        benchmark_dir=BENCHMARK_DIR,
        output_dir=out,
    )
    assert len(selected) == 1
    assert selected[0].case_id == "pilot_loop"
    assert evaluated == 3

    case_dir = out / "pilot_loop"
    for name in (
        "case.json",
        "candidate_fsm.json",
        "reference_fsm.json",
        "oracle_suite.json",
    ):
        assert (case_dir / name).is_file()

    report = out / "candidate_selection_report.csv"
    assert report.is_file()
    with report.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["case_id"] == "pilot_loop"
    assert float(rows[0]["initial_bpr"]) == pytest.approx(2 / 3)

    case = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    validator = _repair_case_validator()
    errors = sorted(validator.iter_errors(case), key=lambda e: list(e.path))
    assert not errors, [e.message for e in errors]
    assert case["final_outcome"]["repair_status"] == "not_started"


def test_structurally_valid_fsm_rejects_invalid() -> None:
    doc = json.loads(
        (BENCHMARK_DIR / "candidates" / "pilot_invalid.json").read_text(encoding="utf-8")
    )
    ok, _reason = structurally_valid_fsm(doc)
    assert ok is False


def test_missing_manifest_raises(tmp_path: Path) -> None:
    with pytest.raises(ExtractionError, match="manifest not found"):
        extract_repair_candidates(benchmark_dir=tmp_path / "empty", output_dir=tmp_path / "out")


def test_build_emse_case_id_deterministic() -> None:
    assert build_emse_case_id("C1_test", "loop_sys", "model_a", "01") == (
        "repair__c1_test__loop_sys__model_a__r01"
    )


def test_emse_load_selects_only_eligible_rows() -> None:
    records = load_emse_ingestion_manifest(EMSE_DIR / "ingestion_manifest.json")
    case_ids = {r.case_id for r in records}
    assert "repair__c1_test__loop_sys__model_a__r01" in case_ids
    assert len(case_ids) == 1


def test_emse_missing_candidate_warns() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        records = load_emse_ingestion_manifest(EMSE_DIR / "ingestion_manifest.json")
    messages = " ".join(str(w.message) for w in caught)
    assert "missing candidate" in messages.lower()
    assert any("99" in str(w.message) for w in caught if "missing candidate" in str(w.message))


def test_emse_extract_bundle_and_report(tmp_path: Path) -> None:
    out = tmp_path / "emse_out"
    selected, evaluated = extract_repair_candidates(
        emse_manifest=EMSE_DIR / "ingestion_manifest.json",
        output_dir=out,
    )
    assert evaluated == 1
    assert len(selected) == 1
    case_id = "repair__c1_test__loop_sys__model_a__r01"
    case_dir = out / case_id
    for name in (
        "case.json",
        "candidate_fsm.json",
        "reference_fsm.json",
        "oracle_suite.json",
        "requirement.json",
    ):
        assert (case_dir / name).is_file()

    with (out / "candidate_selection_report.csv").open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == [
            "case_id",
            "campaign_id",
            "system_id",
            "model_id",
            "replicate",
            "initial_bpr",
            "failed_tests",
            "candidate_path",
            "reference_path",
            "oracle_suite_path",
        ]
        row = next(reader)
        assert row["case_id"] == case_id
        assert row["campaign_id"] == "c1_test"
        assert row["system_id"] == "loop_sys"
        assert row["model_id"] == "model_a"
        assert float(row["initial_bpr"]) == pytest.approx(2 / 3)
        assert int(row["failed_tests"]) >= 1


def test_emse_max_cases(tmp_path: Path) -> None:
    out = tmp_path / "emse_cap"
    selected, _evaluated = extract_repair_candidates(
        emse_manifest=EMSE_DIR / "ingestion_manifest.json",
        output_dir=out,
        max_cases=1,
    )
    assert len(selected) == 1
