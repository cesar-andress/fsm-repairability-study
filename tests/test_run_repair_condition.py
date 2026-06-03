"""Tests for dry-run repair condition orchestrator."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
CASE_DIR = REPO_ROOT / "tests" / "fixtures" / "dry_run_case"
PATCH_SOURCE = CASE_DIR / "repair_patch.json"
SCRIPTS = REPO_ROOT / "scripts"
SCHEMAS = REPO_ROOT / "schemas"

sys.path.insert(0, str(SCRIPTS))
from run_repair_condition import (  # noqa: E402
    RunnerError,
    run_dry_repair_condition,
    validate_repair_run,
    write_repair_run,
)

PLACEHOLDER_CHECKSUM = "a" * 64


@pytest.fixture
def work_dir(tmp_path: Path) -> Path:
    return tmp_path / "work"


def _case_snapshot() -> str:
    return (CASE_DIR / "case.json").read_text(encoding="utf-8")


def test_baseline_no_repair_emits_valid_repair_run(work_dir: Path, tmp_path: Path) -> None:
    out = tmp_path / "baseline_run.json"
    run = run_dry_repair_condition(
        case_dir=CASE_DIR,
        condition="baseline_no_repair",
        work_dir=work_dir,
        started_at="2026-06-03T12:00:00Z",
        completed_at="2026-06-03T12:05:00Z",
    )
    write_repair_run(run, out)
    validate_repair_run(run)

    assert run["execution"]["repair_condition"] == "baseline_no_repair"
    _assert_output_checksums_sane(run)
    assert run["execution"]["max_iterations"] == 0
    assert run["execution"]["execution_backend"] == "none"
    assert run["iterations"] == []
    assert run["outcome"]["final_bpr_validation"] == pytest.approx(2 / 3)


def _assert_output_checksums_sane(run: dict) -> None:
    outputs = run["reproducibility"]["output_checksums"]
    assert "repair_run.json" not in outputs
    assert PLACEHOLDER_CHECKSUM not in outputs.values()
    for digest in outputs.values():
        assert len(digest) == 64
        assert digest != PLACEHOLDER_CHECKSUM


def test_patch_trace_feedback_improves_bpr(work_dir: Path) -> None:
    run = run_dry_repair_condition(
        case_dir=CASE_DIR,
        condition="patch_trace_feedback",
        work_dir=work_dir,
        patch_source=PATCH_SOURCE,
        started_at="2026-06-03T12:00:00Z",
        completed_at="2026-06-03T12:05:00Z",
    )
    assert run["execution"]["execution_backend"] == "none"
    assert run["execution"]["model_name"] is None
    _assert_output_checksums_sane(run)
    assert len(run["iterations"]) == 1
    it = run["iterations"][0]
    assert it["patch_applied"] is True
    assert it["input_bpr_validation"] == pytest.approx(2 / 3)
    assert it["output_bpr_validation"] == 1.0
    assert run["outcome"]["effective_repair"] is True
    assert run["outcome"]["complete_repair"] is True


def test_case_dir_inputs_not_mutated(work_dir: Path) -> None:
    before = _case_snapshot()
    run_dry_repair_condition(
        case_dir=CASE_DIR,
        condition="patch_trace_feedback",
        work_dir=work_dir,
        patch_source=PATCH_SOURCE,
    )
    assert (CASE_DIR / "case.json").read_text(encoding="utf-8") == before


def test_intermediate_diagnostics_written(work_dir: Path) -> None:
    run_dry_repair_condition(
        case_dir=CASE_DIR,
        condition="patch_trace_feedback",
        work_dir=work_dir,
        patch_source=PATCH_SOURCE,
    )
    diag = work_dir / "diagnostics" / "iter_000_feedback.json"
    assert diag.is_file()
    data = json.loads(diag.read_text(encoding="utf-8"))
    assert data["identity"]["diagnostic_level"] == "trace"
    assert (work_dir / "scores" / "iter_000_input_feedback.json").is_file()
    assert (work_dir / "candidates" / "iter_001.json").is_file()


def test_invalid_condition_fails_clearly(work_dir: Path) -> None:
    with pytest.raises(RunnerError, match="unsupported condition"):
        run_dry_repair_condition(
            case_dir=CASE_DIR,
            condition="unknown_condition",
            work_dir=work_dir,
            patch_source=PATCH_SOURCE,
        )


def test_output_validates_against_repair_run_schema(work_dir: Path, tmp_path: Path) -> None:
    run = run_dry_repair_condition(
        case_dir=CASE_DIR,
        condition="patch_binary_feedback",
        work_dir=work_dir,
        patch_source=PATCH_SOURCE,
    )
    out = tmp_path / "run.json"
    write_repair_run(run, out)
    _assert_output_checksums_sane(run)
    assert run["execution"]["repair_condition"] == "patch_binary_feedback"
    diag = json.loads(
        (work_dir / "diagnostics" / "iter_000_feedback.json").read_text(encoding="utf-8")
    )
    assert diag["identity"]["diagnostic_level"] == "binary"


def test_patch_with_ollama_metadata(work_dir: Path) -> None:
    run = run_dry_repair_condition(
        case_dir=CASE_DIR,
        condition="patch_trace_feedback",
        work_dir=work_dir,
        patch_source=PATCH_SOURCE,
        execution_backend="ollama",
        model_name="llama3:8b",
        model_digest=None,
        temperature=0.0,
        seed=None,
    )
    validate_repair_run(run)
    assert run["execution"]["execution_backend"] == "ollama"
    assert run["execution"]["model_name"] == "llama3:8b"
    assert run["execution"]["model_digest"] is None
    assert run["execution"]["temperature"] == 0.0


def test_baseline_ignores_ollama_metadata(work_dir: Path) -> None:
    run = run_dry_repair_condition(
        case_dir=CASE_DIR,
        condition="baseline_no_repair",
        work_dir=work_dir,
        execution_backend="ollama",
        model_name="should-not-appear",
    )
    assert run["execution"]["execution_backend"] == "none"
    assert run["execution"]["model_name"] is None


def test_cli_end_to_end(work_dir: Path, tmp_path: Path) -> None:
    out_run = tmp_path / "cli_run.json"
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "run_repair_condition.py"),
            "--case-dir",
            str(CASE_DIR),
            "--condition",
            "patch_trace_feedback",
            "--patch-source",
            str(PATCH_SOURCE),
            "--output-run",
            str(out_run),
            "--work-dir",
            str(work_dir),
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert proc.returncode == 0, proc.stderr
    run = json.loads(out_run.read_text(encoding="utf-8"))
    validate_repair_run(run)
    _assert_output_checksums_sane(run)
