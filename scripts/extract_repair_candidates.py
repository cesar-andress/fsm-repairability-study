#!/usr/bin/env python3
"""
Extract repair cases from prior benchmark outputs for pilot repair studies.

Modes:
  --benchmark-dir       Simple manifest.json layout (public fixtures).
  --emse-ingestion-manifest   EMSE behavioural campaign metrics + benchmark tree.

See docs/repair_candidate_selection.md.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "datasets" / "pilot_repair_cases"
MANIFEST_NAME = "manifest.json"
REPAIR_CASE_SCHEMA_VERSION = "2.0.0"
SLUG_RE = re.compile(r"^[a-z][a-z0-9_]*$")

BPR_COLUMNS = ("behavioral_pass_rate", "bpr", "BPR")
STRUCT_COLUMNS = ("g2_pass", "G2", "schema_valid", "structural_valid")
FAILED_COLUMNS = (
    "failed_tests",
    "failed_checks",
    "behavioral_failures",
    "oracle_failures",
)
SYSTEM_COLUMNS = ("system_id", "system", "requirement_system")
MODEL_COLUMNS = ("model", "model_id")
REPLICATE_COLUMNS = ("replicate", "run_id", "candidate_id")
CANDIDATE_PATH_COLUMNS = (
    "candidate_path",
    "candidate_fsm_path",
    "fsm_path",
    "output_path",
)

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

EMSE_REPORT_FIELDS = [
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
class EmseMetricsRow:
    campaign_id: str
    system_id: str
    model_id: str
    replicate: str
    case_id: str
    metrics_csv: Path
    run_dir: Path
    benchmark_root: Path
    candidate_path: Path
    reference_path: Path
    oracle_suite_path: Path
    system_spec_path: Path
    csv_bpr: float | None = None
    csv_structural_ok: bool | None = None
    csv_failed_tests: int | None = None


@dataclass
class SelectionRow:
    case_id: str
    system_id: str
    initial_bpr: float
    failed_tests: int
    candidate_size: int
    reference_size: int
    campaign_id: str = ""
    model_id: str = ""
    replicate: str = ""
    candidate_path: str = ""
    reference_path: str = ""
    oracle_suite_path: str = ""


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


def slugify_token(value: str) -> str:
    s = value.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "unknown"


def _first_column(row: dict[str, str], names: tuple[str, ...]) -> str | None:
    for name in names:
        if name in row and row[name].strip():
            return row[name].strip()
    return None


def _parse_bool(value: str | None) -> bool | None:
    if value is None or not str(value).strip():
        return None
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "t"}:
        return True
    if text in {"0", "false", "no", "n", "f"}:
        return False
    return None


def _parse_float(value: str | None) -> float | None:
    if value is None or not str(value).strip():
        return None
    try:
        return float(str(value).strip())
    except ValueError:
        return None


def _parse_int(value: str | None) -> int | None:
    if value is None or not str(value).strip():
        return None
    try:
        return int(float(str(value).strip()))
    except ValueError:
        return None


def _truthy_structural(row: dict[str, str]) -> bool | None:
    for col in STRUCT_COLUMNS:
        if col not in row:
            continue
        parsed = _parse_bool(row.get(col))
        if parsed is not None:
            return parsed
    return None


def _csv_row_passes_gates(row: dict[str, str]) -> tuple[bool, str]:
    bpr = None
    for col in BPR_COLUMNS:
        if col in row:
            bpr = _parse_float(row.get(col))
            break
    if bpr is None:
        return False, "behavioral_pass_rate is null"

    struct = _truthy_structural(row)
    if struct is not None and not struct:
        return False, "structural gate failed in metrics"

    if bpr >= 1.0:
        return False, f"BPR {bpr} is not below 1.0"

    failed: int | None = None
    for col in FAILED_COLUMNS:
        if col in row:
            failed = _parse_int(row.get(col))
            break
    if failed is not None and failed <= 0:
        return False, "no failed behavioural checks in metrics"

    return True, ""


def find_benchmark_root(metrics_csv: Path) -> Path:
    metrics_csv = metrics_csv.resolve()
    for parent in [metrics_csv.parent, *metrics_csv.parents]:
        if (parent / "benchmark" / "gold_fsms").is_dir():
            return parent
    raise ExtractionError(
        f"cannot locate benchmark root (expected benchmark/gold_fsms) near {metrics_csv}"
    )


def load_metrics_csv(path: Path) -> list[dict[str, str]]:
    path = path.resolve()
    if not path.is_file():
        raise ExtractionError(f"metrics.csv not found: {path}")
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ExtractionError(f"metrics.csv has no header: {path}")
        return [dict(row) for row in reader]


def _replicate_slug(value: str) -> str:
    text = str(value).strip()
    if text.lower().startswith("r") and len(text) <= 4:
        return slugify_token(text)
    num = re.sub(r"\D", "", text) or text
    try:
        return f"r{int(num):02d}"
    except ValueError:
        return slugify_token(f"r{text}")


def build_emse_case_id(
    campaign_id: str, system_id: str, model_id: str, replicate: str
) -> str:
    return (
        f"repair__{slugify_token(campaign_id)}__{slugify_token(system_id)}"
        f"__{slugify_token(model_id)}__{_replicate_slug(replicate)}"
    )


def _resolve_candidate_path(
    row: dict[str, str], run_dir: Path, run_id: str | None
) -> Path | None:
    rel = _first_column(row, CANDIDATE_PATH_COLUMNS)
    if rel:
        path = (run_dir / rel).resolve()
        return path if path.is_file() else None
    if run_id:
        direct = run_dir / "candidates" / f"{run_id}.json"
        if direct.is_file():
            return direct
        direct2 = run_dir / "candidates" / run_id
        if direct2.is_file():
            return direct2
    return None


def requirement_text_from_system_spec(spec: dict[str, Any]) -> str:
    if isinstance(spec.get("requirement_text"), str) and spec["requirement_text"].strip():
        return spec["requirement_text"].strip()
    reqs = spec.get("requirements")
    if isinstance(reqs, list) and reqs:
        return "\n".join(str(r).strip() for r in reqs if str(r).strip())
    if isinstance(spec.get("description"), str):
        return spec["description"].strip()
    name = spec.get("system_name", "system")
    return f"Behavioural requirements for {name}."


def normalize_emse_fsm_to_study(doc: dict[str, Any], system_id: str) -> dict[str, Any]:
    if isinstance(doc.get("transitions"), list) and doc["transitions"]:
        first = doc["transitions"][0]
        if "from" in first and "to" in first:
            if "schema_version" not in doc:
                doc = {**doc, "schema_version": "1.0.0"}
            if "id" not in doc:
                doc = {**doc, "id": slugify_token(system_id)}
            return doc
    states = list(doc.get("states", []))
    events = list(doc.get("events", doc.get("alphabet", [])))
    transitions: list[dict[str, str]] = []
    for t in doc.get("transitions", []):
        fr = t.get("from") or t.get("source")
        to = t.get("to") or t.get("target")
        ev = t.get("event")
        if fr and to and ev:
            transitions.append({"from": fr, "to": to, "event": ev})
    return {
        "schema_version": "1.0.0",
        "id": slugify_token(system_id),
        "states": states,
        "initial_state": doc.get("initial_state", states[0] if states else "s0"),
        "alphabet": events,
        "transitions": transitions,
    }


def normalize_emse_suite_to_study(doc: dict[str, Any], system_id: str) -> dict[str, Any]:
    if doc.get("schema_version") and doc.get("tests"):
        first = doc["tests"][0]
        if "type" in first:
            return doc
    tests_out: list[dict[str, Any]] = []
    initial = doc.get("initial_state")
    for t in doc.get("tests", []):
        tid = t.get("test_id", "unknown")
        events = list(t.get("events", []))
        kind = (t.get("kind") or t.get("type") or "oracle").lower()
        if kind == "negative" or t.get("expected_final_state") is None:
            from_state = events[0] if events else (initial or "s0")
            extra = events[1:] if len(events) > 1 else events
            tests_out.append(
                {
                    "test_id": tid,
                    "type": "rejected_event",
                    "from_state": from_state,
                    "events": extra or ["invalid"],
                }
            )
            continue
        trace = t.get("expected_trace") or t.get("expected_states")
        if trace:
            states = list(trace)
            if initial and (not states or states[0] != initial):
                states = [initial, *states]
            tests_out.append(
                {
                    "test_id": tid,
                    "type": "trace",
                    "events": events,
                    "expected_states": states,
                }
            )
            continue
        tests_out.append(
            {
                "test_id": tid,
                "type": "final_state",
                "events": events,
                "expected_final_state": t.get("expected_final_state"),
            }
        )
    return {
        "schema_version": "1.0.0",
        "suite_id": slugify_token(doc.get("suite_id", f"{system_id}_suite")),
        "tests": tests_out,
    }


def load_emse_ingestion_manifest(manifest_path: Path) -> list[EmseMetricsRow]:
    manifest_path = manifest_path.resolve()
    data = load_json(manifest_path)
    if not isinstance(data, dict):
        raise ExtractionError("ingestion manifest must be a JSON object")

    metrics_keys = [k for k in ("c1_metrics", "c2_metrics") if k in data]
    if not metrics_keys:
        raise ExtractionError("ingestion manifest must contain c1_metrics and/or c2_metrics")

    records: list[EmseMetricsRow] = []
    for key in metrics_keys:
        raw_path = data[key]
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ExtractionError(f"{key} must be a non-empty path string")
        metrics_csv = Path(raw_path)
        if not metrics_csv.is_absolute():
            metrics_csv = (manifest_path.parent / metrics_csv).resolve()
        run_dir = metrics_csv.parent
        benchmark_root = find_benchmark_root(metrics_csv)

        for row in load_metrics_csv(metrics_csv):
            ok, _reason = _csv_row_passes_gates(row)
            if not ok:
                continue

            system_raw = _first_column(row, SYSTEM_COLUMNS)
            if not system_raw:
                continue
            system_id = slugify_token(system_raw)
            campaign_id = row.get("campaign_id") or key.replace("_metrics", "")
            model_raw = _first_column(row, MODEL_COLUMNS) or "unknown_model"
            model_id = slugify_token(model_raw)
            replicate_raw = (
                _first_column(row, REPLICATE_COLUMNS)
                or row.get("run_index", "0")
                or "0"
            )
            run_id = row.get("run_id", "").strip() or None
            candidate_path = _resolve_candidate_path(row, run_dir, run_id)
            if candidate_path is None:
                warnings.warn(
                    f"skipping row (missing candidate file): campaign={campaign_id} "
                    f"system={system_raw} model={model_raw} replicate={replicate_raw}",
                    stacklevel=2,
                )
                continue

            benchmark = benchmark_root / "benchmark"
            reference_path = benchmark / "gold_fsms" / f"{system_raw}.json"
            oracle_path = benchmark / "test_suites" / f"{system_raw}.json"
            system_path = benchmark / "datasets" / "systems" / f"{system_raw}.json"
            if not reference_path.is_file():
                alt = benchmark / "gold_fsms" / f"{system_id.replace('-', '_')}.json"
                reference_path = alt if alt.is_file() else reference_path
            if not oracle_path.is_file():
                continue
            if not reference_path.is_file():
                warnings.warn(
                    f"skipping row (missing gold FSM): {reference_path}",
                    stacklevel=2,
                )
                continue

            case_id = build_emse_case_id(campaign_id, system_id, model_id, replicate_raw)
            bpr = None
            for col in BPR_COLUMNS:
                if col in row:
                    bpr = _parse_float(row.get(col))
                    break

            records.append(
                EmseMetricsRow(
                    campaign_id=slugify_token(campaign_id),
                    system_id=slugify_token(system_id),
                    model_id=model_id,
                    replicate=_replicate_slug(replicate_raw),
                    case_id=case_id,
                    metrics_csv=metrics_csv,
                    run_dir=run_dir,
                    benchmark_root=benchmark_root,
                    candidate_path=candidate_path,
                    reference_path=reference_path,
                    oracle_suite_path=oracle_path,
                    system_spec_path=system_path,
                    csv_bpr=bpr,
                    csv_structural_ok=_truthy_structural(row),
                    csv_failed_tests=next(
                        (
                            _parse_int(row.get(col))
                            for col in FAILED_COLUMNS
                            if col in row
                        ),
                        None,
                    ),
                )
            )
    if not records:
        raise ExtractionError("no EMSE metrics rows passed selection gates")
    return records


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


def build_case_json(
    *,
    case_id: str,
    system_id: str,
    campaign_id: str,
    requirement_text: str,
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
            "case_id": case_id,
            "system_id": system_id,
            "campaign_id": campaign_id,
        },
        "inputs": {
            "requirement_text": requirement_text,
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
            return EvaluatedEntry(entry, False, f"BPR {bpr} is not below 1.0")
        if failed_tests < 1:
            return EvaluatedEntry(entry, False, "no failed behavioural checks")

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


def write_case_bundle(
    output_dir: Path,
    *,
    case_id: str,
    system_id: str,
    campaign_id: str,
    requirement_text: str,
    candidate: dict[str, Any],
    reference: dict[str, Any],
    oracle_suite: dict[str, Any],
    system_spec: dict[str, Any] | None = None,
) -> SelectionRow:
    case_dir = output_dir / case_id
    case_dir.mkdir(parents=True, exist_ok=True)

    report = score_candidate(candidate, oracle_suite)
    case_doc = build_case_json(
        case_id=case_id,
        system_id=system_id,
        campaign_id=campaign_id,
        requirement_text=requirement_text,
        report=report,
        oracle_suite=oracle_suite,
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
    if system_spec is not None:
        (case_dir / "requirement.json").write_text(
            json.dumps(system_spec, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    return SelectionRow(
        case_id=case_id,
        system_id=system_id,
        initial_bpr=float(report["bpr"]),
        failed_tests=int(report["failed_tests"]),
        candidate_size=_json_byte_size(candidate),
        reference_size=_json_byte_size(reference),
        campaign_id=campaign_id,
    )


def write_case_bundle_benchmark(
    output_dir: Path,
    entry: BenchmarkEntry,
    *,
    campaign_id: str,
    benchmark_dir: Path,
) -> SelectionRow:
    cand_path = resolve_benchmark_path(benchmark_dir, entry.candidate_fsm_path)
    ref_path = resolve_benchmark_path(benchmark_dir, entry.reference_fsm_path)
    suite_path = resolve_benchmark_path(benchmark_dir, entry.oracle_suite_path)

    candidate = load_json(cand_path)
    reference = load_json(ref_path)
    oracle_suite = load_json(suite_path)

    row = write_case_bundle(
        output_dir,
        case_id=entry.case_id,
        system_id=entry.system_id,
        campaign_id=campaign_id,
        requirement_text=entry.requirement_text,
        candidate=candidate,
        reference=reference,
        oracle_suite=oracle_suite,
    )
    return row


def evaluate_emse_row(record: EmseMetricsRow) -> tuple[bool, str, SelectionRow | None]:
    try:
        if not record.candidate_path.is_file():
            return False, f"candidate file not found: {record.candidate_path}", None

        candidate_raw = load_json(record.candidate_path)
        reference_raw = load_json(record.reference_path)
        suite_raw = load_json(record.oracle_suite_path)

        if not isinstance(candidate_raw, dict):
            return False, "candidate must be a JSON object", None
        candidate = normalize_emse_fsm_to_study(candidate_raw, record.system_id)
        reference = normalize_emse_fsm_to_study(reference_raw, record.system_id)
        oracle_suite = normalize_emse_suite_to_study(suite_raw, record.system_id)

        if record.system_spec_path.is_file():
            system_spec = load_json(record.system_spec_path)
            requirement_text = requirement_text_from_system_spec(system_spec)
        else:
            system_spec = {"system_id": record.system_id}
            requirement_text = requirement_text_from_system_spec(system_spec)

        ok_c, reason_c = structurally_valid_fsm(candidate)
        if not ok_c:
            return False, f"candidate structurally invalid: {reason_c}", None

        ok_r, reason_r = structurally_valid_fsm(reference)
        if not ok_r:
            return False, f"reference structurally invalid: {reason_r}", None

        report = score_candidate(candidate, oracle_suite)
        bpr = float(report["bpr"])
        failed_tests = int(report["failed_tests"])

        if bpr >= 1.0:
            return False, f"re-scored BPR {bpr} is not below 1.0", None
        if failed_tests < 1:
            return False, "no failed behavioural checks after re-score", None

        row = SelectionRow(
            case_id=record.case_id,
            system_id=record.system_id,
            initial_bpr=bpr,
            failed_tests=failed_tests,
            candidate_size=_json_byte_size(candidate),
            reference_size=_json_byte_size(reference),
            campaign_id=record.campaign_id,
            model_id=record.model_id,
            replicate=record.replicate,
            candidate_path=str(record.candidate_path),
            reference_path=str(record.reference_path),
            oracle_suite_path=str(record.oracle_suite_path),
        )
        return True, "", row
    except (ExtractionError, OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        return False, str(exc), None


def write_emse_case_bundle(
    output_dir: Path, record: EmseMetricsRow
) -> SelectionRow:
    candidate_raw = load_json(record.candidate_path)
    reference_raw = load_json(record.reference_path)
    suite_raw = load_json(record.oracle_suite_path)
    system_spec = (
        load_json(record.system_spec_path)
        if record.system_spec_path.is_file()
        else {"system_id": record.system_id}
    )
    if not isinstance(system_spec, dict):
        system_spec = {"system_id": record.system_id}

    candidate = normalize_emse_fsm_to_study(candidate_raw, record.system_id)
    reference = normalize_emse_fsm_to_study(reference_raw, record.system_id)
    oracle_suite = normalize_emse_suite_to_study(suite_raw, record.system_id)
    requirement_text = requirement_text_from_system_spec(system_spec)

    row = write_case_bundle(
        output_dir,
        case_id=record.case_id,
        system_id=record.system_id,
        campaign_id=record.campaign_id,
        requirement_text=requirement_text,
        candidate=candidate,
        reference=reference,
        oracle_suite=oracle_suite,
        system_spec=system_spec,
    )
    row.model_id = record.model_id
    row.replicate = record.replicate
    row.candidate_path = str(record.candidate_path)
    row.reference_path = str(record.reference_path)
    row.oracle_suite_path = str(record.oracle_suite_path)
    row.campaign_id = record.campaign_id
    return row


def write_selection_report(
    path: Path, rows: list[SelectionRow], *, emse_mode: bool = False
) -> None:
    fields = EMSE_REPORT_FIELDS if emse_mode else REPORT_FIELDS
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            if emse_mode:
                writer.writerow(
                    {
                        "case_id": row.case_id,
                        "campaign_id": row.campaign_id,
                        "system_id": row.system_id,
                        "model_id": row.model_id,
                        "replicate": row.replicate,
                        "initial_bpr": row.initial_bpr,
                        "failed_tests": row.failed_tests,
                        "candidate_path": row.candidate_path,
                        "reference_path": row.reference_path,
                        "oracle_suite_path": row.oracle_suite_path,
                    }
                )
            else:
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
    benchmark_dir: Path | None = None,
    emse_manifest: Path | None = None,
    output_dir: Path,
    max_cases: int | None = None,
) -> tuple[list[SelectionRow], int]:
    output_dir.mkdir(parents=True, exist_ok=True)
    selected_rows: list[SelectionRow] = []
    evaluated_count = 0

    if emse_manifest is not None:
        records = load_emse_ingestion_manifest(emse_manifest)
        for record in records:
            evaluated_count += 1
            ok, reason, preview_row = evaluate_emse_row(record)
            if not ok:
                warnings.warn(
                    f"skipping {record.case_id}: {reason}",
                    stacklevel=2,
                )
                continue
            if max_cases is not None and len(selected_rows) >= max_cases:
                continue
            row = write_emse_case_bundle(output_dir, record)
            row.campaign_id = record.campaign_id
            row.model_id = record.model_id
            row.replicate = record.replicate
            row.candidate_path = str(record.candidate_path)
            row.reference_path = str(record.reference_path)
            row.oracle_suite_path = str(record.oracle_suite_path)
            selected_rows.append(row)
        write_selection_report(
            output_dir / "candidate_selection_report.csv",
            selected_rows,
            emse_mode=True,
        )
        return selected_rows, evaluated_count

    if benchmark_dir is None:
        raise ExtractionError("either --benchmark-dir or --emse-ingestion-manifest is required")

    campaign_id, entries = load_benchmark_manifest(benchmark_dir)
    evaluated: list[EvaluatedEntry] = []

    for entry in entries:
        result = evaluate_entry(benchmark_dir, entry, campaign_id=campaign_id)
        evaluated.append(result)
        evaluated_count += 1
        if not result.selected:
            continue
        if max_cases is not None and len(selected_rows) >= max_cases:
            continue
        row = write_case_bundle_benchmark(
            output_dir,
            entry,
            campaign_id=campaign_id,
            benchmark_dir=benchmark_dir,
        )
        selected_rows.append(row)

    write_selection_report(
        output_dir / "candidate_selection_report.csv",
        selected_rows,
        emse_mode=False,
    )
    return selected_rows, evaluated_count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--benchmark-dir",
        type=Path,
        help=f"Simple benchmark export root containing {MANIFEST_NAME}",
    )
    mode.add_argument(
        "--emse-ingestion-manifest",
        type=Path,
        help="EMSE campaign ingestion_manifest.json (c1_metrics, c2_metrics)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output root for pilot cases (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--max-cases",
        type=int,
        default=None,
        help="Maximum number of cases to write (default: unlimited)",
    )
    parser.add_argument(
        "--max-candidates",
        type=int,
        default=None,
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args(argv)
    max_cases = args.max_cases if args.max_cases is not None else args.max_candidates

    try:
        selected, evaluated = extract_repair_candidates(
            benchmark_dir=args.benchmark_dir,
            emse_manifest=args.emse_ingestion_manifest,
            output_dir=args.output_dir,
            max_cases=max_cases,
        )
    except ExtractionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    n_sel = len(selected)
    print(f"evaluated {evaluated} candidate rows, selected {n_sel}")
    print(f"wrote {args.output_dir / 'candidate_selection_report.csv'}")
    for row in selected:
        print(f"  {row.case_id}  bpr={row.initial_bpr}  failed_tests={row.failed_tests}")

    return 0 if n_sel > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
