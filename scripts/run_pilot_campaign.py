#!/usr/bin/env python3
"""
Pilot repair campaign: run the full repair pipeline on multiple repair cases.

Pipeline per case:
  candidate FSM → score → diagnostic → prompt → Ollama → patch → apply → score → repair_run

Writes campaign_summary.json and campaign_results.csv under --output-dir.
See docs/pilot_campaign.md.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
PATCH_SCHEMA_PATH = REPO_ROOT / "schemas" / "patch.schema.json"

sys.path.insert(0, str(REPO_ROOT / "scripts"))

from apply_patch import write_fsm  # noqa: E402
from build_diagnostic import build_diagnostic, write_diagnostic  # noqa: E402
from generate_patch_ollama import (  # noqa: E402
    ABSTENTION_FILENAME,
    PROMPT_VARIANTS,
    PatchAbstention,
    PatchGenerationError,
    generate_patch_ollama,
    recover_operation_inferred_abstention,
    resolve_prompt_variant_for_condition,
)
from ollama_client import OllamaConfig  # noqa: E402
from run_repair_condition import (  # noqa: E402
    CONDITION_TO_DIAGNOSTIC_LEVEL,
    RunnerError,
    load_case_bundle,
    resolve_fsm,
    resolve_oracle_suite,
    run_dry_repair_condition,
    write_repair_run,
)
from score_repair import score_fsm, write_report  # noqa: E402

PILOT_CONDITIONS = frozenset(CONDITION_TO_DIAGNOSTIC_LEVEL.keys())
CAMPAIGN_SCHEMA_VERSION = "1.0.0"
CSV_FIELDS = [
    "case_id",
    "initial_bpr",
    "final_bpr",
    "delta_bpr",
    "repaired",
    "complete_repair",
    "iterations",
    "patch_operations",
    "status",
    "error",
]


class CampaignError(Exception):
    """Raised when campaign setup or aggregation fails."""


@dataclass
class CaseResult:
    case_id: str
    status: str = "ok"
    error: str = ""
    initial_bpr: float | None = None
    final_bpr: float | None = None
    delta_bpr: float | None = None
    repaired: bool = False
    complete_repair: bool = False
    iterations: int = 0
    patch_operations: int = 0
    regression: bool = False
    patch_valid: bool | None = None
    patch_applied: bool | None = None
    outcome_class: str = ""
    work_dir: Path | None = None


def discover_case_dirs(cases_dir: Path, max_cases: int) -> list[Path]:
    cases_dir = cases_dir.resolve()
    if not cases_dir.is_dir():
        raise CampaignError(f"cases directory not found: {cases_dir}")

    if (cases_dir / "case.json").is_file():
        roots = [cases_dir]
    else:
        roots = sorted(
            p for p in cases_dir.iterdir() if p.is_dir() and (p / "case.json").is_file()
        )

    if not roots:
        raise CampaignError(f"no repair cases found under {cases_dir}")

    if max_cases < 1:
        raise CampaignError("--max-cases must be at least 1")

    return roots[:max_cases]


def _write_requirement(case: dict[str, Any], path: Path) -> None:
    text = case.get("inputs", {}).get("requirement_text", "")
    if not isinstance(text, str) or not text.strip():
        raise CampaignError("case.inputs.requirement_text is missing or empty")
    path.write_text(text.strip() + "\n", encoding="utf-8")


def run_case_pipeline(
    *,
    case_dir: Path,
    condition: str,
    model: str,
    output_dir: Path,
    ollama_config: OllamaConfig,
    temperature: float,
    work_dir: Path | None = None,
    prompt_variant: str = "default",
) -> CaseResult:
    case_dir = case_dir.resolve()
    case = load_case_bundle(case_dir)
    case_id = case["identity"]["case_id"]
    work_dir = (work_dir or (output_dir / case_id)).resolve()
    prep_dir = work_dir / "prep"
    ollama_dir = work_dir / "ollama"
    run_dir = work_dir / "run"
    for d in (prep_dir, ollama_dir, run_dir):
        d.mkdir(parents=True, exist_ok=True)

    result = CaseResult(case_id=case_id, work_dir=work_dir)
    run_id = f"{case_id}__{condition}__pilot"
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        feedback_binding = case["oracles"]["feedback_oracles"]
        validation_binding = case["oracles"]["validation_oracles"]
        feedback_suite, feedback_suite_path = resolve_oracle_suite(case_dir, feedback_binding)
        validation_suite, validation_suite_path = resolve_oracle_suite(
            case_dir, validation_binding
        )

        candidate = resolve_fsm(case_dir, case["inputs"]["candidate_fsm"])
        candidate_path = prep_dir / "candidate.json"
        write_fsm(candidate, candidate_path)

        scores_dir = prep_dir / "scores"
        scores_dir.mkdir(exist_ok=True)
        score_val_path = scores_dir / "validation_initial.json"
        score_fb_path = scores_dir / "feedback_initial.json"

        report_val = score_fsm(
            candidate,
            validation_suite,
            fsm_path=str(candidate_path),
            oracle_suite_path=str(validation_suite_path),
        )
        write_report(report_val, score_val_path)
        result.initial_bpr = float(report_val["bpr"])

        report_fb = score_fsm(
            candidate,
            feedback_suite,
            fsm_path=str(candidate_path),
            oracle_suite_path=str(feedback_suite_path),
        )
        write_report(report_fb, score_fb_path)

        level = CONDITION_TO_DIAGNOSTIC_LEVEL[condition]
        diagnostic = build_diagnostic(
            report_fb,
            level,
            case_id=case_id,
            run_id=run_id,
            iteration_index=0,
            generated_at=started,
            score_report_path=score_fb_path,
            path_bases=[prep_dir, case_dir, REPO_ROOT],
        )
        diag_path = prep_dir / "diagnostics" / "iter_000.json"
        write_diagnostic(diagnostic, diag_path)

        req_path = prep_dir / "requirement.txt"
        _write_requirement(case, req_path)

        patch_source: Path | None = ollama_dir / "patch.json"
        abstention_source: Path | None = None
        try:
            generate_patch_ollama(
                condition=condition,
                requirement_path=req_path,
                candidate_fsm_path=candidate_path,
                diagnostic_path=diag_path,
                patch_schema_path=PATCH_SCHEMA_PATH,
                model=model,
                output_dir=ollama_dir,
                ollama_config=ollama_config,
                generate_options={"temperature": temperature},
                prompt_variant=prompt_variant,
            )
        except PatchAbstention:
            patch_source = None
            abstention_source = ollama_dir / ABSTENTION_FILENAME
        except PatchGenerationError as exc:
            if recover_operation_inferred_abstention(
                ollama_dir,
                prompt_variant,
                exc,
                candidate_fsm=candidate,
            ):
                patch_source = None
                abstention_source = ollama_dir / ABSTENTION_FILENAME
            else:
                raise

        repair_run = run_dry_repair_condition(
            case_dir=case_dir,
            condition=condition,
            work_dir=run_dir,
            patch_source=patch_source,
            abstention_source=abstention_source,
            run_id=run_id,
            started_at=started,
            completed_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            execution_backend="ollama",
            model_name=model,
            model_digest=None,
            temperature=temperature,
            seed=None,
        )
        repair_run_path = work_dir / "repair_run.json"
        write_repair_run(repair_run, repair_run_path)

        outcome = repair_run["outcome"]
        result.final_bpr = float(outcome["final_bpr_validation"])
        result.delta_bpr = result.final_bpr - (result.initial_bpr or 0.0)
        if outcome.get("outcome_class") == "abstained":
            result.status = "abstained"
            result.delta_bpr = 0.0
            result.final_bpr = result.initial_bpr
        result.repaired = bool(outcome.get("effective_repair")) or bool(
            outcome.get("complete_repair")
        )
        result.complete_repair = bool(outcome.get("complete_repair"))
        result.iterations = len(repair_run.get("iterations", []))
        result.patch_operations = int(repair_run["cost"].get("patch_operations_total", 0))
        result.regression = bool(outcome.get("behavioural_degradation")) or bool(
            outcome.get("regression_detected")
        )
        result.outcome_class = str(outcome.get("outcome_class", ""))
        iterations = repair_run.get("iterations") or []
        if iterations:
            if result.status == "abstained":
                result.patch_valid = None
            else:
                result.patch_valid = bool(iterations[0].get("patch_valid"))
            result.patch_applied = bool(iterations[0].get("patch_applied"))

    except (
        CampaignError,
        RunnerError,
        PatchGenerationError,
        RuntimeError,
        OSError,
        ValueError,
    ) as exc:
        result.status = "failed"
        result.error = str(exc)

    return result


def aggregate_campaign_summary(
    *,
    results: list[CaseResult],
    condition: str,
    model: str,
    cases_dir: Path,
    output_dir: Path,
    started_at: str,
    completed_at: str,
    prompt_variant_requested: str = "default",
    prompt_variant_effective: str | None = None,
) -> dict[str, Any]:
    ok = [r for r in results if r.status == "ok"]
    failed = [r for r in results if r.status != "ok"]
    deltas = [r.delta_bpr for r in ok if r.delta_bpr is not None]
    repaired = [r for r in ok if r.repaired]
    complete = [r for r in ok if r.complete_repair]
    regressions = [r for r in ok if r.regression]

    n_ok = len(ok)
    repair_rate = len(repaired) / n_ok if n_ok else 0.0
    complete_rate = len(complete) / n_ok if n_ok else 0.0

    return {
        "schema_version": CAMPAIGN_SCHEMA_VERSION,
        "campaign_id": f"pilot_{condition}_{started_at[:10]}",
        "condition": condition,
        "prompt_variant": prompt_variant_requested,
        "prompt_variant_requested": prompt_variant_requested,
        "prompt_variant_effective": prompt_variant_effective or prompt_variant_requested,
        "model": model,
        "cases_dir": str(cases_dir.resolve()),
        "output_dir": str(output_dir.resolve()),
        "started_at": started_at,
        "completed_at": completed_at,
        "cases_attempted": len(results),
        "cases_succeeded": n_ok,
        "cases_failed": len(failed),
        "metrics": {
            "repair_rate": repair_rate,
            "complete_repair_rate": complete_rate,
            "mean_delta_bpr": statistics.mean(deltas) if deltas else None,
            "median_delta_bpr": statistics.median(deltas) if deltas else None,
            "regressions": len(regressions),
            "failures": len(failed),
        },
    }


def write_campaign_results_csv(path: Path, results: list[CaseResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for r in results:
            writer.writerow(
                {
                    "case_id": r.case_id,
                    "initial_bpr": "" if r.initial_bpr is None else r.initial_bpr,
                    "final_bpr": "" if r.final_bpr is None else r.final_bpr,
                    "delta_bpr": "" if r.delta_bpr is None else r.delta_bpr,
                    "repaired": r.repaired if r.status == "ok" else "",
                    "complete_repair": r.complete_repair if r.status == "ok" else "",
                    "iterations": r.iterations if r.status == "ok" else "",
                    "patch_operations": r.patch_operations if r.status == "ok" else "",
                    "status": r.status,
                    "error": r.error,
                }
            )


def run_pilot_campaign(
    *,
    cases_dir: Path,
    condition: str,
    model: str,
    max_cases: int,
    output_dir: Path,
    ollama_config: OllamaConfig | None = None,
    temperature: float = 0.0,
    prompt_variant: str = "default",
) -> tuple[dict[str, Any], list[CaseResult]]:
    if prompt_variant not in PROMPT_VARIANTS:
        raise CampaignError(
            f"prompt_variant {prompt_variant!r} is not supported; "
            f"expected one of: {', '.join(sorted(PROMPT_VARIANTS))}"
        )
    if condition not in PILOT_CONDITIONS:
        raise CampaignError(
            f"condition {condition!r} is not supported for pilot campaigns; "
            f"expected one of: {', '.join(sorted(PILOT_CONDITIONS))}"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    case_dirs = discover_case_dirs(cases_dir, max_cases)
    started_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    config = ollama_config or OllamaConfig()

    effective_variant = resolve_prompt_variant_for_condition(prompt_variant, condition)
    results: list[CaseResult] = []
    for case_dir in case_dirs:
        results.append(
            run_case_pipeline(
                case_dir=case_dir,
                condition=condition,
                model=model,
                output_dir=output_dir,
                ollama_config=config,
                temperature=temperature,
                prompt_variant=effective_variant,
            )
        )

    completed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    summary = aggregate_campaign_summary(
        results=results,
        condition=condition,
        model=model,
        cases_dir=cases_dir,
        output_dir=output_dir,
        started_at=started_at,
        completed_at=completed_at,
        prompt_variant_requested=prompt_variant,
        prompt_variant_effective=effective_variant,
    )
    summary_path = output_dir / "campaign_summary.json"
    csv_path = output_dir / "campaign_results.csv"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    write_campaign_results_csv(csv_path, results)
    return summary, results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cases-dir",
        required=True,
        type=Path,
        help="Directory of repair case folders (or single case with case.json)",
    )
    parser.add_argument(
        "--condition",
        required=True,
        choices=sorted(PILOT_CONDITIONS),
        help="Repair condition (patch feedback level)",
    )
    parser.add_argument("--model", required=True, help="Ollama model tag")
    parser.add_argument(
        "--max-cases",
        type=int,
        default=1,
        help="Maximum number of cases to run (default: 1)",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Campaign output root (per-case subdirectories created)",
    )
    parser.add_argument(
        "--ollama-url",
        default="http://127.0.0.1:11434",
        help="Ollama base URL",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="Ollama decoding temperature (default: 0.0)",
    )
    parser.add_argument(
        "--prompt-variant",
        choices=sorted(PROMPT_VARIANTS),
        default="default",
        help=(
            "Requested prompt variant; operation-inferred applies only to "
            "patch_localized_feedback. See docs/operation_inferred_prompting.md."
        ),
    )
    args = parser.parse_args(argv)

    try:
        summary, results = run_pilot_campaign(
            cases_dir=args.cases_dir,
            condition=args.condition,
            model=args.model,
            max_cases=args.max_cases,
            output_dir=args.output_dir,
            ollama_config=OllamaConfig(base_url=args.ollama_url),
            temperature=args.temperature,
            prompt_variant=args.prompt_variant,
        )
    except CampaignError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    summary_path = args.output_dir / "campaign_summary.json"
    csv_path = args.output_dir / "campaign_results.csv"

    print(json.dumps(summary, indent=2))
    print(f"wrote {summary_path}")
    print(f"wrote {csv_path}")

    return 0 if summary["cases_failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
