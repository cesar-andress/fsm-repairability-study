"""Tests for generated Results section narrative."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
PAPER_ROOT = REPO_ROOT.parent / "paper"
PAPER_EXPERIMENTS = PAPER_ROOT / "experiments"

sys.path.insert(0, str(SCRIPTS))
from generate_results_section import (  # noqa: E402
    FORBIDDEN_PHRASES,
    GeneratorError,
    build_results_tex,
    generate_results_section,
    load_main_results_csv,
    validate_no_forbidden_phrases,
)

REQUIRED_REFS = (
    r"\ref{tab:main_results}",
    r"\ref{tab:repair_outcomes}",
    r"\ref{tab:failure_analysis}",
    r"\ref{fig:evaluated-cases}",
    r"\ref{fig:repair-success}",
    r"\ref{fig:patch-failure}",
)


def _minimal_csv(path: Path) -> None:
    lines = [
        "variant,condition,evaluated,failed,patch_failures,abstentions,mean_delta,regression",
    ]
    for variant in ("default", "operation-aware", "operation-inferred"):
        for cond, ev, fail in (("C", 5, 10), ("D", 6, 9), ("E", 12, 3)):
            lines.append(
                f"{variant},{cond},{ev},{fail},0,0,0.01,0.0"
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _outcome_json() -> dict:
    per = {
        label: {
            "cases_evaluated": 10,
            "improved_count": 2,
            "unchanged_count": 7,
            "degraded_count": 1,
            "complete_repair_count": 0,
            "effective_repair_count": 2,
            "mean_delta_bpr": 0.01,
        }
        for label in ("C", "D", "E")
    }
    return {"per_condition": per}


def _patch_json() -> dict:
    return {
        "aggregates": {
            "total_failures": 12,
            "by_failure_class": {
                "duplicate_transition": 9,
                "missing_state": 2,
                "transition_not_found": 1,
                "invalid_operation_semantics": 0,
            },
        }
    }


def _write_experiments(experiments: Path) -> None:
    for pilot in (
        "frozen_pilot_001",
        "diagnostic_granularity_pilot_diverse_operation_aware_001",
        "frozen_main_pilot_001",
    ):
        analysis = experiments / pilot / "analysis"
        analysis.mkdir(parents=True)
        (analysis / "repair_outcome_summary.json").write_text(
            json.dumps(_outcome_json()), encoding="utf-8"
        )
        (analysis / "patch_failure_summary.json").write_text(
            json.dumps(_patch_json()), encoding="utf-8"
        )


def test_generated_tex_contains_table_and_figure_refs(tmp_path: Path) -> None:
    csv_path = tmp_path / "results" / "main_results_table.csv"
    experiments = tmp_path / "experiments"
    _minimal_csv(csv_path)
    _write_experiments(experiments)
    out = tmp_path / "generated" / "results_generated.tex"
    generate_results_section(
        main_results_csv=csv_path,
        experiments_dir=experiments,
        output_path=out,
    )
    tex = out.read_text(encoding="utf-8")
    for ref in REQUIRED_REFS:
        assert ref in tex
    assert "inferential statistics" in tex
    assert "causal explanations" in tex


def test_forbidden_phrases_rejected() -> None:
    bad = "This suggests that the model caused by noise."
    with pytest.raises(GeneratorError, match="forbidden"):
        validate_no_forbidden_phrases(bad)


def test_deterministic_template_includes_evaluated_counts(tmp_path: Path) -> None:
    csv_path = tmp_path / "results" / "main_results_table.csv"
    experiments = tmp_path / "experiments"
    _minimal_csv(csv_path)
    _write_experiments(experiments)
    rows = load_main_results_csv(csv_path)
    outcomes = {
        v: {c: type("S", (), {
            "cases_evaluated": 10,
            "improved_count": 1,
            "unchanged_count": 8,
            "degraded_count": 1,
            "complete_repair_count": 0,
            "effective_repair_count": 1,
        })() for c in ("C", "D", "E")}
        for v in ("default", "operation-aware", "operation-inferred")
    }
    from generate_results_section import FailureStats, OutcomeStats

    outcomes_typed = {
        v: {
            c: OutcomeStats(
                cases_evaluated=10,
                improved_count=1,
                unchanged_count=8,
                degraded_count=1,
                complete_repair_count=0,
                effective_repair_count=1,
                mean_delta_bpr=0.0,
            )
            for c in ("C", "D", "E")
        }
        for v in ("default", "operation-aware", "operation-inferred")
    }
    failures = {
        v: FailureStats(total_failures=5, by_class={"duplicate_transition": 5})
        for v in ("default", "operation-aware", "operation-inferred")
    }
    tex = build_results_tex(rows, outcomes_typed, failures)
    assert "12 case--condition runs were evaluated" in tex
    assert "condition~E" in tex


def test_no_significance_wording_in_full_generation(tmp_path: Path) -> None:
    csv_path = tmp_path / "results" / "main_results_table.csv"
    experiments = tmp_path / "experiments"
    _minimal_csv(csv_path)
    _write_experiments(experiments)
    out = tmp_path / "generated" / "results_generated.tex"
    generate_results_section(
        main_results_csv=csv_path,
        experiments_dir=experiments,
        output_path=out,
    )
    lower = out.read_text(encoding="utf-8").lower()
    for phrase in FORBIDDEN_PHRASES:
        assert phrase not in lower
    assert "significant" not in re.findall(r"\bsignificant\w*\b", lower)


@pytest.mark.skipif(
    not (PAPER_ROOT / "results" / "main_results_table.csv").is_file(),
    reason="paper CSV not present",
)
def test_generate_from_paper_tree(tmp_path: Path) -> None:
    out = tmp_path / "results_generated.tex"
    generate_results_section(
        main_results_csv=PAPER_ROOT / "results" / "main_results_table.csv",
        experiments_dir=PAPER_EXPERIMENTS,
        output_path=out,
    )
    tex = out.read_text(encoding="utf-8")
    assert "9 case--condition runs were evaluated" in tex
    assert "23 case--condition runs were evaluated" in tex
    assert "0 complete repairs" in tex
