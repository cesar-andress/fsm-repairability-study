#!/usr/bin/env python3
"""
Run one repair case under one repair condition (primary IV).

Supports:
  - baseline_no_repair (deterministic, no Ollama)
  - LLM conditions via local Ollama (optional)
  - --dry-run (prompt assembly only)
  - --offline (read frozen run from results/frozen_runs/)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from ollama_client import OllamaConfig, generate, health_check  # noqa: E402
from score_repair import score_against_suite  # noqa: E402

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

CONDITION_IDS = (
    "baseline_no_repair",
    "baseline_full_regeneration",
    "patch_binary_feedback",
    "patch_trace_feedback",
    "patch_localized_feedback",
)


def load_yaml(path: Path) -> dict:
    if yaml is None:
        raise RuntimeError("PyYAML required: pip install -r environment/requirements.txt")
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_condition(config: dict, condition_id: str) -> dict:
    for cond in config.get("conditions", []):
        if cond.get("condition_id") == condition_id:
            return cond
    raise KeyError(f"unknown condition_id: {condition_id}")


def load_prompt_template(prompt_ref: str | None) -> str:
    if not prompt_ref:
        return ""
    path = REPO_ROOT / prompt_ref
    return path.read_text(encoding="utf-8")


def render_prompt(template: str, variables: dict[str, str]) -> str:
    out = template
    for key, value in variables.items():
        out = out.replace(f"{{{{{key}}}}}", value)
    return out


def load_case_bundle(case_id: str) -> dict[str, Any]:
    """Load case.json and initial_fsm.json from datasets/repair_cases/<case_id>/."""
    case_dir = REPO_ROOT / "datasets" / "repair_cases" / case_id
    case_path = case_dir / "case.json"
    fsm_path = case_dir / "initial_fsm.json"
    if not case_path.exists():
        raise FileNotFoundError(f"missing case bundle: {case_path}")
    with case_path.open(encoding="utf-8") as f:
        case = json.load(f)
    if fsm_path.exists():
        with fsm_path.open(encoding="utf-8") as f:
            case["_initial_fsm_doc"] = json.load(f)
    return case


def load_oracle_suite(suite_id: str) -> dict:
    path = REPO_ROOT / "datasets" / "oracle_suites" / f"{suite_id}.json"
    if not path.exists():
        return {"suite_id": suite_id, "checks": []}
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def frozen_run_path(case_id: str, condition_id: str, model_label: str | None) -> Path:
    suffix = f"__{model_label}" if model_label else ""
    return (
        REPO_ROOT
        / "results"
        / "frozen_runs"
        / f"{case_id}__{condition_id}{suffix}.json"
    )


def run_baseline_no_repair(case: dict, suite: dict) -> dict:
    fsm = case.get("_initial_fsm_doc")
    if not fsm:
        raise ValueError("baseline_no_repair requires initial_fsm.json in case bundle")
    score = score_against_suite(fsm, suite)
    return {
        "condition_id": "baseline_no_repair",
        "uses_llm": False,
        "attempt_budget": 0,
        "attempts": [],
        "outcome": "success" if score["passed"] else "budget_exhausted",
        "oracle_score": score,
    }


def run_with_ollama(
    *,
    condition: dict,
    case: dict,
    suite: dict,
    model: str,
    ollama_url: str,
    dry_run: bool,
) -> dict:
    prompt_ref = condition.get("prompt_ref")
    template = load_prompt_template(prompt_ref)
    fsm = case.get("_initial_fsm_doc") or {}
    variables = {
        "task_spec_ref": str(case.get("task_spec_ref", "")),
        "current_fsm_json": json.dumps(fsm, indent=2),
        "fsm_id": str(fsm.get("id", "")),
        "attempt_index": "1",
        "attempt_budget": str(condition.get("default_attempt_budget", 1)),
        "oracle_pass_fail": "fail",
        "failed_check_ids": "[]",
        "check_id": "stub",
        "input_sequence": "[]",
        "expected_trace": "[]",
        "observed_trace": "[]",
        "suspected_states": "[]",
        "suspected_transitions": "[]",
        "failure_summary": "stub",
        "task_spec_body": "",
        "structural_constraints": "",
    }
    prompt = render_prompt(template, variables)

    result: dict[str, Any] = {
        "condition_id": condition["condition_id"],
        "uses_llm": True,
        "model": model,
        "attempt_budget": condition.get("default_attempt_budget"),
        "prompt_ref": prompt_ref,
        "dry_run": dry_run,
    }

    if dry_run:
        result["prompt_chars"] = len(prompt)
        result["outcome"] = "aborted"
        return result

    if not health_check(OllamaConfig(base_url=ollama_url)):
        raise RuntimeError(
            f"Ollama not reachable at {ollama_url}. "
            "Use --dry-run or --offline for audit replication."
        )

    options = {}
    models_cfg = load_yaml(REPO_ROOT / "environment" / "ollama_models.yaml")
    if models_cfg.get("ollama", {}).get("options"):
        options = dict(models_cfg["ollama"]["options"])

    raw = generate(model, prompt, config=OllamaConfig(base_url=ollama_url), options=options)
    result["llm_response_chars"] = len(raw)
    result["outcome"] = "aborted"
    result["note"] = (
        "LLM response received; full parse/repair loop not implemented in skeleton. "
        "Freeze completed runs under results/frozen_runs/ for audit."
    )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True, help="Repair case id")
    parser.add_argument(
        "--condition",
        required=True,
        choices=CONDITION_IDS,
        help="Repair condition (primary independent variable)",
    )
    parser.add_argument(
        "--model",
        help="Ollama model name (experimental engine; required for LLM conditions)",
    )
    parser.add_argument(
        "--ollama-url",
        default="http://127.0.0.1:11434",
        help="Ollama base URL",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Load frozen run from results/frozen_runs/ instead of calling Ollama",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Assemble prompt and exit without Ollama call",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Write run summary JSON to this path",
    )
    args = parser.parse_args(argv)

    conditions_cfg = load_yaml(REPO_ROOT / "environment" / "conditions.yaml")
    condition = get_condition(conditions_cfg, args.condition)

    if args.offline:
        path = frozen_run_path(args.case, args.condition, args.model)
        if not path.exists():
            print(f"No frozen run: {path}", file=sys.stderr)
            return 1
        summary = json.loads(path.read_text(encoding="utf-8"))
        print(json.dumps(summary, indent=2))
        return 0

    case = load_case_bundle(args.case)
    suite_ids = case.get("oracle_suite_ids", [])
    suite = load_oracle_suite(suite_ids[0]) if suite_ids else {"suite_id": "none", "checks": []}

    if args.condition == "baseline_no_repair":
        summary = run_baseline_no_repair(case, suite)
    else:
        if not args.model and not args.dry_run:
            print("--model is required for LLM conditions", file=sys.stderr)
            return 1
        summary = run_with_ollama(
            condition=condition,
            case=case,
            suite=suite,
            model=args.model or "dry-run",
            ollama_url=args.ollama_url,
            dry_run=args.dry_run,
        )

    summary["case_id"] = args.case
    text = json.dumps(summary, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
