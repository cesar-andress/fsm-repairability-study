#!/usr/bin/env python3
"""
Extract repair cases from prior benchmark outputs for pilot repair studies.

Selects structurally valid FSMs with BPR < 1.0 and at least one failed behavioural check,
then writes datasets/pilot_repair_cases/<case_id>/ bundles.

See docs/repair_candidate_selection.md.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "datasets" / "pilot_repair_cases"
MANIFEST_NAME = "manifest.json"
REPAIR_CASE_SCHEMA_VERSION = "2.0.0"
SLUG_RE = re.compile(r"^[a-z][a-z0-9_]*$")

sys.path.insert(0, str(REPO_ROOT / "scripts"))

from score_repair import score_fsm  # noqa: E402
from validate_fsm import (  # noqa: E402
    validate_fsm_document,
    validate_referential_integrity,
)

REPORT_FIELDS = [
    "case_id",
    "system_id",
    "initial_bpr",
    "failed_tests",
    "candidate_size",
    "reference_size",
]


class ExtractionError(Exception):
    """Raised when benchmark layout or configuration is invalid."""


@dataclass
class BenchmarkEntry:
    case_id: str
    system_id: str
    requirement_text: str
    candidate_fsm_path: str
    reference_fsm_path: str
    oracle_suite_path: str


@dataclass
class SelectionRow:
    case_id: str
    system_id: str
    initial_bpr: float
    failed_tests: int
    candidate_size: int
    reference_size: int


@dataclass
class EvaluatedEntry:
    entry: BenchmarkEntry
    selected: bool
    reason: str = ""
    row: SelectionRow | None = None


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _json_byte_size(doc: dict[str, Any]) -> int:
    return len(json.dumps(doc, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def _validate_slug(value: str, field: str) -> None:
    if not SLUG_RE.match(value):
        raise ExtractionError(f"{field} must match slug pattern: {value!r}")


def load_benchmark_manifest(benchmark_dir: Path) -> tuple[str, list[BenchmarkEntry]]:
    benchmark_dir = benchmark_dir.resolve()
    manifest_path = benchmark_dir / MANIFEST_NAME
    if not manifest_path.is_file():
        raise ExtractionError(f"benchmark manifest not found: {manifest_path}")

    data = load_json(manifest_path)
    if not isinstance(data, dict):
        raise ExtractionError("manifest must be a JSON object")

    campaign_id = data.get("campaign_id", "benchmark_import")
    if not isinstance(campaign_id, str) or not SLUG_RE.match(campaign_id):
        raise ExtractionError(f"invalid campaign_id in manifest: {campaign_id!r}")

    entries_raw = data.get("entries")
    if not isinstance(entries_raw, list) or not entries_raw:
        raise ExtractionError("manifest.entries must be a non-empty array")

    entries: list[BenchmarkEntry] = []
    for i, raw in enumerate(entries_raw):
        if not isinstance(raw, dict):
            raise ExtractionError(f"entries[{i}] must be an object")
        for key in (
            "case_id",
            "system_id",
            "requirement_text",
            "candidate_fsm_path",
            "reference_fsm_path",
            "oracle_suite_path",
        ):
            if key not in raw or not isinstance(raw[key], str) or not raw[key].strip():
                raise ExtractionError(f"entries[{i}] missing or invalid {key}")

        _validate_slug(raw["case_id"], "case_id")
        _validate_slug(raw["system_id"], "system_id")

        entries.append(
            BenchmarkEntry(
                case_id=raw["case_id"],
                system_id=raw["system_id"],
                requirement_text=raw["requirement_text"].strip(),
                candidate_fsm_path=raw["candidate_fsm_path"],
                reference_fsm_path=raw["reference_fsm_path"],
                oracle_suite_path=raw["oracle_suite_path"],
            )
        )

    return campaign_id, entries


def resolve_benchmark_path(benchmark_dir: Path, rel: str) -> Path:
    path = (benchmark_dir / rel).resolve()
    if not path.is_file():
        raise ExtractionError(f"benchmark file not found: {rel}")
    try:
        path.relative_to(benchmark_dir.resolve())
    except ValueError as exc:
        raise ExtractionError(f"path escapes benchmark root: {rel}") from exc
    return path


def structurally_valid_fsm(fsm: dict[str, Any]) -> tuple[bool, str]:
    schema_errors = validate_fsm_document(fsm)
    integrity_errors = validate_referential_integrity(fsm)
    if schema_errors or integrity_errors:
        detail = "; ".join((schema_errors + integrity_errors)[:3])
        return False, detail
    return True, ""


def score_candidate(
    candidate: dict[str, Any],
    oracle_suite: dict[str, Any],
) -> dict[str, Any]:
    return score_fsm(
        candidate,
        oracle_suite,
        fsm_path="candidate_fsm.json",
        oracle_suite_path="oracle_suite.json",
    )


def _build_checks(report: dict[str, Any], suite: dict[str, Any]) -> list[dict[str, Any]]:
    failed_ids = {f["test_id"] for f in report.get("failures", [])}
    checks = []
    for test in suite.get("tests", []):
        tid = test.get("test_id", "unknown")
        passed = tid not in failed_ids
        entry: dict[str, Any] = {"check_id": tid, "passed": passed}
        if test.get("type"):
            entry["check_type"] = test["type"]
        checks.append(entry)
    return checks


def _failure_summary(report: dict[str, Any]) -> str:
    failures = report.get("failures", [])
    if not failures:
        return "No behavioural failures recorded."
    ids = [f.get("test_id", "?") for f in failures[:8]]
    suffix = "..." if len(failures) > 8 else ""
    return f"Failed checks at extraction: {', '.join(ids)}{suffix}"


def evaluate_entry(
    benchmark_dir: Path,
    entry: BenchmarkEntry,
    *,
    campaign_id: str,
) -> EvaluatedEntry:
    try:
        cand_path = resolve_benchmark_path(benchmark_dir, entry.candidate_fsm_path)
        ref_path = resolve_benchmark_path(benchmark_dir, entry.reference_fsm_path)
        suite_path = resolve_benchmark_path(benchmark_dir, entry.oracle_suite_path)

        candidate = load_json(cand_path)
        reference = load_json(ref_path)
        oracle_suite = load_json(suite_path)

        if not isinstance(candidate, dict) or not isinstance(reference, dict):
            return EvaluatedEntry(entry, False, "FSM documents must be JSON objects")
        if not isinstance(oracle_suite, dict):
            return EvaluatedEntry(entry, False, "oracle suite must be a JSON object")

        ok_c, reason_c = structurally_valid_fsm(candidate)
        if not ok_c:
            return EvaluatedEntry(entry, False, f"candidate structurally invalid: {reason_c}")

        ok_r, reason_r = structurally_valid_fsm(reference)
        if not ok_r:
            return EvaluatedEntry(entry, False, f"reference structurally invalid: {reason_r}")

        report = score_candidate(candidate, oracle_suite)
        bpr = float(report["bpr"])
        failed_tests = int(report["failed_tests"])

        if bpr >= 1.0:
            return EvaluatedEntry(
                entry,
                False,
                f"BPR {bpr} is not below 1.0",
            )
        if failed_tests < 1:
            return EvaluatedEntry(
                entry,
                False,
                "no failed behavioural checks",
            )

        row = SelectionRow(
            case_id=entry.case_id,
            system_id=entry.system_id,
            initial_bpr=bpr,
            failed_tests=failed_tests,
            candidate_size=_json_byte_size(candidate),
            reference_size=_json_byte_size(reference),
        )
        return EvaluatedEntry(entry, True, "", row)

    except (ExtractionError, OSError, ValueError, RuntimeError) as exc:
        return EvaluatedEntry(entry, False, str(exc))


def build_case_json(
    entry: BenchmarkEntry,
    *,
    campaign_id: str,
    report: dict[str, Any],
    oracle_suite: dict[str, Any],
) -> dict[str, Any]:
    suite_id = oracle_suite.get("suite_id", "validation_suite")
    if not isinstance(suite_id, str) or not SLUG_RE.match(suite_id):
        suite_id = "validation_suite"

    checks = _build_checks(report, oracle_suite)
    return {
        "schema_version": REPAIR_CASE_SCHEMA_VERSION,
        "identity": {
            "case_id": entry.case_id,
            "system_id": entry.system_id,
            "campaign_id": campaign_id,
        },
        "inputs": {
            "requirement_text": entry.requirement_text,
            "candidate_fsm": "candidate_fsm.json",
            "reference_fsm": "reference_fsm.json",
        },
        "baseline": {
            "initial_bpr": report["bpr"],
            "initial_component_metrics": {
                "suite_id": suite_id,
                "total_count": report["total_tests"],
                "passed_count": report["passed_tests"],
                "failed_count": report["failed_tests"],
                "checks": checks,
            },
        },
        "oracles": {
            "feedback_oracles": {
                "suite_id": suite_id,
                "suite_path": "oracle_suite.json",
            },
            "validation_oracles": {
                "suite_id": suite_id,
                "suite_path": "oracle_suite.json",
            },
        },
        "diagnostics": {
            "missing_transitions": [],
            "extra_transitions": [],
            "failure_summary": _failure_summary(report),
        },
        "repair_history": {
            "iterations": [],
            "applied_patches": [],
            "intermediate_bpr": [report["bpr"]],
        },
        "final_outcome": {
            "final_bpr": None,
            "repair_status": "not_started",
            "regression_detected": False,
            "overfitting_detected": False,
        },
        "admission": {
            "structurally_valid": True,
            "eligible_for_repair_study": True,
            "initial_bpr_below_one": True,
        },
    }


def write_case_bundle(
    output_dir: Path,
    entry: BenchmarkEntry,
    *,
    campaign_id: str,
    benchmark_dir: Path,
) -> SelectionRow:
    case_dir = output_dir / entry.case_id
    case_dir.mkdir(parents=True, exist_ok=True)

    cand_path = resolve_benchmark_path(benchmark_dir, entry.candidate_fsm_path)
    ref_path = resolve_benchmark_path(benchmark_dir, entry.reference_fsm_path)
    suite_path = resolve_benchmark_path(benchmark_dir, entry.oracle_suite_path)

    candidate = load_json(cand_path)
    reference = load_json(ref_path)
    oracle_suite = load_json(suite_path)
    report = score_candidate(candidate, oracle_suite)

    case_doc = build_case_json(
        entry, campaign_id=campaign_id, report=report, oracle_suite=oracle_suite
    )

    (case_dir / "case.json").write_text(
        json.dumps(case_doc, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (case_dir / "candidate_fsm.json").write_text(
        json.dumps(candidate, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (case_dir / "reference_fsm.json").write_text(
        json.dumps(reference, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (case_dir / "oracle_suite.json").write_text(
        json.dumps(oracle_suite, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return SelectionRow(
        case_id=entry.case_id,
        system_id=entry.system_id,
        initial_bpr=float(report["bpr"]),
        failed_tests=int(report["failed_tests"]),
        candidate_size=_json_byte_size(candidate),
        reference_size=_json_byte_size(reference),
    )


def write_selection_report(path: Path, rows: list[SelectionRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=REPORT_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "case_id": row.case_id,
                    "system_id": row.system_id,
                    "initial_bpr": row.initial_bpr,
                    "failed_tests": row.failed_tests,
                    "candidate_size": row.candidate_size,
                    "reference_size": row.reference_size,
                }
            )


def extract_repair_candidates(
    *,
    benchmark_dir: Path,
    output_dir: Path,
    max_candidates: int | None = None,
) -> tuple[list[SelectionRow], list[EvaluatedEntry]]:
    campaign_id, entries = load_benchmark_manifest(benchmark_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    evaluated: list[EvaluatedEntry] = []
    selected_rows: list[SelectionRow] = []

    for entry in entries:
        result = evaluate_entry(benchmark_dir, entry, campaign_id=campaign_id)
        evaluated.append(result)
        if not result.selected:
            continue
        if max_candidates is not None and len(selected_rows) >= max_candidates:
            continue
        row = write_case_bundle(
            output_dir,
            entry,
            campaign_id=campaign_id,
            benchmark_dir=benchmark_dir,
        )
        selected_rows.append(row)

    report_path = output_dir / "candidate_selection_report.csv"
    write_selection_report(report_path, selected_rows)
    return selected_rows, evaluated


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--benchmark-dir",
        required=True,
        type=Path,
        help=f"Benchmark export root containing {MANIFEST_NAME}",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output root for pilot cases (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--max-candidates",
        type=int,
        default=None,
        help="Optional cap on number of cases written",
    )
    args = parser.parse_args(argv)

    try:
        selected, evaluated = extract_repair_candidates(
            benchmark_dir=args.benchmark_dir,
            output_dir=args.output_dir,
            max_candidates=args.max_candidates,
        )
    except ExtractionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    n_sel = len(selected)
    n_eval = len(evaluated)
    print(f"evaluated {n_eval} benchmark entries, selected {n_sel}")
    print(f"wrote {args.output_dir / 'candidate_selection_report.csv'}")
    for row in selected:
        print(f"  {row.case_id}  bpr={row.initial_bpr}  failed_tests={row.failed_tests}")

    return 0 if n_sel > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
