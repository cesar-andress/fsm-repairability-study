#!/usr/bin/env python3
"""
Classify patch application failures from diagnostic granularity pilot outputs.

Read-only analysis of --pilot-dir (does not modify pilot artefacts).
See docs/patch_failure_analysis.md.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
CONDITION_LABELS = ("C", "D", "E")
PATCH_APPLICATION_STATUSES = frozenset({"patch_application_error"})
PATCH_ERROR_MARKERS = (
    "patch application failed",
    "patch application",
    "apply_patch",
    "patchengine",
)

RESULTS_CSV = "diagnostic_granularity_results.csv"
SUMMARY_CSV = "patch_failure_summary.csv"
SUMMARY_JSON = "patch_failure_summary.json"

ROW_FIELDS = [
    "case_id",
    "condition",
    "status",
    "error_message",
    "patch_path",
    "operation_index",
    "operation_type",
    "source_state",
    "event",
    "target_state",
    "failure_class",
]

FAILURE_CLASSES = (
    "duplicate_transition",
    "missing_state",
    "unknown_event",
    "transition_not_found",
    "invalid_operation_semantics",
    "other",
)

OP_INDEX_RE = re.compile(r"operation\[(\d+)\]", re.IGNORECASE)


class AnalysisError(Exception):
    """Raised when pilot directory layout is invalid."""


@dataclass
class FailureRecord:
    case_id: str
    condition: str
    status: str
    error_message: str
    patch_path: str = ""
    operation_index: str = ""
    operation_type: str = ""
    source_state: str = ""
    event: str = ""
    target_state: str = ""
    failure_class: str = "other"
    system_id: str = ""

    def to_csv_row(self) -> dict[str, str]:
        return {
            "case_id": self.case_id,
            "condition": self.condition,
            "status": self.status,
            "error_message": self.error_message,
            "patch_path": self.patch_path,
            "operation_index": self.operation_index,
            "operation_type": self.operation_type,
            "source_state": self.source_state,
            "event": self.event,
            "target_state": self.target_state,
            "failure_class": self.failure_class,
        }


@dataclass
class PilotIndex:
    """Per case_id × condition status and error from granularity results CSV."""

    by_case: dict[str, dict[str, dict[str, str]]] = field(default_factory=dict)


def system_id_from_case_id(case_id: str) -> str:
    parts = case_id.split("__")
    if len(parts) >= 4 and parts[0] == "repair":
        return parts[2]
    if len(parts) >= 2:
        return parts[0]
    return "unknown"


def classify_failure_message(message: str) -> str:
    msg = message.lower()
    if "duplicate (from, event)" in msg or "duplicate transition" in msg:
        return "duplicate_transition"
    if "not in states" in msg or "missing state" in msg:
        return "missing_state"
    if "unknown event" in msg or "event not in alphabet" in msg:
        return "unknown_event"
    if (
        "no transition" in msg
        or "no (from, event) match" in msg
        or "transition_not_found" in msg
    ):
        return "transition_not_found"
    if (
        "self-loop" in msg
        or "must differ" in msg
        or "state operations are not supported" in msg
        or "unknown op" in msg
        or "post-patch fsm validation" in msg
        or "patch schema validation" in msg
        or "missing required field" in msg
        or "target_fsm_id" in msg
        or "must be a json object" in msg
    ):
        return "invalid_operation_semantics"
    return "other"


def _parse_operation_index(message: str) -> int | None:
    match = OP_INDEX_RE.search(message)
    if match:
        return int(match.group(1))
    return None


def _operation_fields(op: dict[str, Any] | None) -> tuple[str, str, str, str]:
    if not op:
        return "", "", "", ""
    op_type = str(op.get("op", ""))
    source = str(op.get("from", ""))
    ev = str(op.get("event", ""))
    if op_type == "update_transition":
        target = str(op.get("new_to", op.get("old_to", "")))
    else:
        target = str(op.get("to", ""))
    return op_type, source, ev, target


def _find_patch_path(cond_dir: Path) -> Path | None:
    candidates = [
        cond_dir / "ollama" / "patch.json",
        cond_dir / "prep" / "patches" / "iter_000_source.json",
        cond_dir / "run" / "patches" / "iter_000_source.json",
    ]
    for path in candidates:
        if path.is_file():
            return path
    return None


def _find_candidate_path(cond_dir: Path) -> Path | None:
    for path in (
        cond_dir / "prep" / "candidate.json",
        cond_dir / "run" / "candidates" / "iter_000.json",
    ):
        if path.is_file():
            return path
    return None


def _load_patch_ops(patch_path: Path | None) -> list[dict[str, Any]]:
    if patch_path is None:
        return []
    try:
        with patch_path.open(encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []
    ops = doc.get("operations")
    if isinstance(ops, list):
        return [o for o in ops if isinstance(o, dict)]
    return []


def _read_error_message(cond_dir: Path, csv_error: str) -> str:
    err_file = cond_dir / "error.txt"
    if err_file.is_file():
        return err_file.read_text(encoding="utf-8").strip()
    return csv_error.strip()


def _is_patch_application_failure(status: str, error: str) -> bool:
    if status in PATCH_APPLICATION_STATUSES:
        return True
    msg = error.lower()
    return any(marker in msg for marker in PATCH_ERROR_MARKERS)


def load_pilot_index(pilot_dir: Path) -> PilotIndex:
    index = PilotIndex()
    csv_path = pilot_dir / RESULTS_CSV
    if not csv_path.is_file():
        return index
    with csv_path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            case_id = row.get("case_id", "").strip()
            if not case_id:
                continue
            index.by_case.setdefault(case_id, {})
            for label in CONDITION_LABELS:
                status = row.get(f"status_{label}", "").strip()
                error = row.get(f"error_{label}", "").strip()
                index.by_case[case_id][label] = {"status": status, "error": error}
    return index


def discover_failure_targets(
    pilot_dir: Path, index: PilotIndex
) -> list[tuple[str, str, str, str]]:
    """Return (case_id, condition, status, csv_error) for patch application failures."""
    targets: list[tuple[str, str, str, str]] = []
    seen: set[tuple[str, str]] = set()

    runs_dir = pilot_dir / "runs"
    if runs_dir.is_dir():
        for case_dir in sorted(runs_dir.iterdir()):
            if not case_dir.is_dir():
                continue
            case_id = case_dir.name
            for label in CONDITION_LABELS:
                cond_dir = case_dir / label
                if not cond_dir.is_dir():
                    continue
                meta = index.by_case.get(case_id, {}).get(label, {})
                status = meta.get("status", "")
                csv_error = meta.get("error", "")
                error_preview = _read_error_message(cond_dir, csv_error)
                if not _is_patch_application_failure(status, error_preview):
                    if not (cond_dir / "error.txt").is_file():
                        continue
                    if not _is_patch_application_failure("", error_preview):
                        continue
                    status = status or "patch_application_error"
                key = (case_id, label)
                if key in seen:
                    continue
                seen.add(key)
                targets.append((case_id, label, status, csv_error))

    for case_id, conditions in sorted(index.by_case.items()):
        for label, meta in conditions.items():
            status = meta.get("status", "")
            error = meta.get("error", "")
            if not _is_patch_application_failure(status, error):
                continue
            key = (case_id, label)
            if key in seen:
                continue
            seen.add(key)
            targets.append((case_id, label, status, error))

    return targets


def build_failure_record(
    pilot_dir: Path,
    case_id: str,
    condition: str,
    status: str,
    csv_error: str,
) -> FailureRecord:
    cond_dir = pilot_dir / "runs" / case_id / condition
    error_message = _read_error_message(cond_dir, csv_error) if cond_dir.is_dir() else csv_error
    patch_path = _find_patch_path(cond_dir) if cond_dir.is_dir() else None
    ops = _load_patch_ops(patch_path)
    op_index = _parse_operation_index(error_message)
    op: dict[str, Any] | None = None
    if op_index is not None and 0 <= op_index < len(ops):
        op = ops[op_index]
    op_type, source, ev, target = _operation_fields(op)

    record = FailureRecord(
        case_id=case_id,
        condition=condition,
        status=status or "patch_application_error",
        error_message=error_message,
        patch_path=str(patch_path.resolve()) if patch_path else "",
        operation_index="" if op_index is None else str(op_index),
        operation_type=op_type,
        source_state=source,
        event=ev,
        target_state=target,
        failure_class=classify_failure_message(error_message),
        system_id=system_id_from_case_id(case_id),
    )
    return record


def compute_aggregates(records: list[FailureRecord]) -> dict[str, Any]:
    by_condition: Counter[str] = Counter()
    by_failure_class: Counter[str] = Counter()
    by_system_id: Counter[str] = Counter()
    by_operation_type: Counter[str] = Counter()

    for rec in records:
        by_condition[rec.condition] += 1
        by_failure_class[rec.failure_class] += 1
        by_system_id[rec.system_id] += 1
        op_key = rec.operation_type or "(unknown)"
        by_operation_type[op_key] += 1

    return {
        "total_failures": len(records),
        "by_condition": dict(sorted(by_condition.items())),
        "by_failure_class": dict(sorted(by_failure_class.items())),
        "by_system_id": dict(sorted(by_system_id.items())),
        "by_operation_type": dict(sorted(by_operation_type.items())),
    }


def analyze_patch_failures(pilot_dir: Path) -> tuple[list[FailureRecord], dict[str, Any]]:
    pilot_dir = pilot_dir.resolve()
    if not pilot_dir.is_dir():
        raise AnalysisError(f"pilot directory not found: {pilot_dir}")

    index = load_pilot_index(pilot_dir)
    targets = discover_failure_targets(pilot_dir, index)
    records = [
        build_failure_record(pilot_dir, case_id, cond, status, err)
        for case_id, cond, status, err in targets
    ]
    aggregates = compute_aggregates(records)
    summary = {
        "schema_version": "1.0.0",
        "pilot_dir": str(pilot_dir),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_results_csv": str((pilot_dir / RESULTS_CSV).resolve())
        if (pilot_dir / RESULTS_CSV).is_file()
        else None,
        "aggregates": aggregates,
        "failures": [rec.to_csv_row() for rec in records],
    }
    return records, summary


def write_outputs(
    pilot_dir: Path,
    records: list[FailureRecord],
    summary: dict[str, Any],
    *,
    output_dir: Path | None = None,
) -> tuple[Path, Path]:
    out = (output_dir or pilot_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    csv_path = out / SUMMARY_CSV
    json_path = out / SUMMARY_JSON

    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=ROW_FIELDS)
        writer.writeheader()
        for rec in records:
            writer.writerow(rec.to_csv_row())

    json_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return csv_path, json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pilot-dir",
        required=True,
        type=Path,
        help="Diagnostic granularity pilot output root (read-only)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Write summaries here (default: same as --pilot-dir)",
    )
    args = parser.parse_args(argv)

    try:
        records, summary = analyze_patch_failures(args.pilot_dir)
        csv_path, json_path = write_outputs(
            args.pilot_dir,
            records,
            summary,
            output_dir=args.output_dir,
        )
    except AnalysisError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(summary["aggregates"], indent=2))
    print(f"wrote {csv_path}")
    print(f"wrote {json_path}")
    print(f"classified {len(records)} patch application failure(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
