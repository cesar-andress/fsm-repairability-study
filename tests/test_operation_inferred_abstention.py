"""Tests for operation-inferred empty-correction abstention handling."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from unittest import mock

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
CASE_DIR = REPO_ROOT / "tests" / "fixtures" / "dry_run_case"
OLLAMA_FIXTURES = REPO_ROOT / "tests" / "fixtures" / "ollama"
SCRIPTS = REPO_ROOT / "scripts"
RAW_PATCH = (OLLAMA_FIXTURES / "raw_patch_fenced.txt").read_text(encoding="utf-8")

sys.path.insert(0, str(SCRIPTS))
from generate_patch_ollama import (  # noqa: E402
    ABSTENTION_FILENAME,
    PatchAbstention,
    PatchGenerationError,
    generate_patch_ollama,
)
from infer_patch_from_corrections import (  # noqa: E402
    CorrectionInferenceError,
    corrections_indicate_abstention,
    infer_patch_from_corrections,
)
from run_diagnostic_granularity_pilot import (  # noqa: E402
    run_diagnostic_granularity_pilot,
)
from ollama_client import OllamaConfig  # noqa: E402
from run_pilot_campaign import CaseResult, run_case_pipeline  # noqa: E402

CANDIDATE = json.loads((CASE_DIR / "candidate_fsm.json").read_text(encoding="utf-8"))
CORRECTION_EMPTY = {
    "schema_version": "1.0.0",
    "corrections": [],
    "rationale": "Unable to determine a safe repair.",
}


def test_corrections_indicate_abstention() -> None:
    assert corrections_indicate_abstention(CORRECTION_EMPTY) is True


def test_infer_empty_corrections_raises() -> None:
    with pytest.raises(CorrectionInferenceError, match="abstention"):
        infer_patch_from_corrections(CANDIDATE, CORRECTION_EMPTY)


@mock.patch("generate_patch_ollama.generate")
def test_generate_operation_inferred_abstention_artifact(
    mock_generate, tmp_path: Path
) -> None:
    mock_generate.return_value = json.dumps(CORRECTION_EMPTY)
    req = tmp_path / "req.txt"
    req.write_text("requirement", encoding="utf-8")
    fsm = tmp_path / "fsm.json"
    fsm.write_text(json.dumps(CANDIDATE), encoding="utf-8")
    diag = tmp_path / "diag.json"
    diag.write_text("{}", encoding="utf-8")
    out = tmp_path / "out"
    with pytest.raises(PatchAbstention):
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
    assert (out / ABSTENTION_FILENAME).is_file()
    assert not (out / "patch.json").exists()


@mock.patch("generate_patch_ollama.generate", return_value=json.dumps(CORRECTION_EMPTY))
def test_pipeline_abstention_not_invalid_patch(mock_generate, tmp_path: Path) -> None:
    del mock_generate
    out = tmp_path / "case_run"
    result = run_case_pipeline(
        case_dir=CASE_DIR,
        condition="patch_localized_feedback",
        model="test-model",
        output_dir=out,
        work_dir=out,
        ollama_config=OllamaConfig(),
        temperature=0.0,
        prompt_variant="operation-inferred",
    )
    assert result.status == "abstained"
    assert result.patch_applied is False
    assert result.patch_valid is None
    assert result.outcome_class == "abstained"
    assert result.initial_bpr == pytest.approx(2 / 3)
    assert result.final_bpr == result.initial_bpr
    assert result.delta_bpr == 0.0
    assert "patch schema validation failed" not in (result.error or "").lower()


def _generate_abstention_only_for_inferred(model: str, prompt: str, **kwargs: object) -> str:
    if '"desired_target"' in prompt:
        return json.dumps(CORRECTION_EMPTY)
    return RAW_PATCH


@mock.patch("generate_patch_ollama.generate", side_effect=_generate_abstention_only_for_inferred)
def test_granularity_abstention_in_csv_and_summary(
    mock_generate, tmp_path: Path
) -> None:
    del mock_generate
    out = tmp_path / "granularity_abstain"
    summary, rows = run_diagnostic_granularity_pilot(
        cases_dir=CASE_DIR,
        model="test-model",
        max_cases=1,
        output_dir=out,
        prompt_variant="operation-inferred",
    )
    row = rows[0]
    assert row.status["E"] == "abstained"
    assert row.status["C"] == "ok"
    assert row.patch_valid["E"] == "n/a"
    assert row.patch_applied["E"] == "false"
    assert row.final_bpr["E"] == pytest.approx(2 / 3)
    assert row.delta["E"] == 0.0

    with (out / "diagnostic_granularity_results.csv").open(encoding="utf-8") as f:
        csv_row = next(csv.DictReader(f))
    assert csv_row["status_E"] == "abstained"
    assert csv_row["status_C"] == "ok"
    assert csv_row["patch_valid_E"] == "n/a"

    pc = summary["per_condition"]["E"]
    assert pc["abstention_count"] == 1
    assert pc["invalid_patch_count"] == 0
    assert pc["patch_application_failure_count"] == 0
    assert pc["cases_evaluated"] == 1
    assert pc["cases_failed"] == 0

    pc_c = summary["per_condition"]["C"]
    assert pc_c["abstention_count"] == 0


@mock.patch("generate_patch_ollama.generate", side_effect=_generate_abstention_only_for_inferred)
def test_granularity_only_e_uses_operation_inferred(mock_generate, tmp_path: Path) -> None:
    del mock_generate
    out = tmp_path / "granularity_oi_e"
    run_diagnostic_granularity_pilot(
        cases_dir=CASE_DIR,
        model="test-model",
        max_cases=1,
        output_dir=out,
        prompt_variant="operation-inferred",
    )
    assert (out / "runs" / "dry_run_case" / "E" / "ollama" / ABSTENTION_FILENAME).is_file()
    assert not (out / "runs" / "dry_run_case" / "E" / "ollama" / "patch.json").exists()
