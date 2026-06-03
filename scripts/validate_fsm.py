#!/usr/bin/env python3
"""Validate an FSM JSON document against schemas/fsm.schema.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import jsonschema
    from jsonschema import Draft202012Validator
except ImportError:  # pragma: no cover
    jsonschema = None  # type: ignore
    Draft202012Validator = None  # type: ignore

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schemas" / "fsm.schema.json"


def load_schema() -> dict:
    with SCHEMA_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def validate_fsm_document(doc: dict, schema: dict | None = None) -> list[str]:
    """Return a list of validation error messages (empty if valid)."""
    if jsonschema is None:
        raise RuntimeError(
            "jsonschema is required. Install with: pip install -r environment/requirements.txt"
        )
    schema = schema or load_schema()
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    return [e.message for e in errors]


def validate_referential_integrity(doc: dict) -> list[str]:
    """Lightweight checks beyond JSON Schema (placeholder for study rules)."""
    issues: list[str] = []
    states = set(doc.get("states", []))
    initial = doc.get("initial_state")
    if initial and initial not in states:
        issues.append(f"initial_state '{initial}' is not in states")
    alphabet = set(doc.get("alphabet", []))
    for i, t in enumerate(doc.get("transitions", [])):
        for field in ("from", "event", "to"):
            if field not in t:
                issues.append(f"transition[{i}] missing '{field}'")
        if t.get("from") not in states:
            issues.append(f"transition[{i}] from state '{t.get('from')}' not in states")
        if t.get("to") not in states:
            issues.append(f"transition[{i}] to state '{t.get('to')}' not in states")
        if t.get("event") not in alphabet:
            issues.append(
                f"transition[{i}] event '{t.get('event')}' not in alphabet"
            )
    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        "-i",
        required=True,
        type=Path,
        help="Path to FSM JSON file",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only print errors; no success message",
    )
    args = parser.parse_args(argv)

    with args.input.open(encoding="utf-8") as f:
        doc = json.load(f)

    schema_errors = validate_fsm_document(doc)
    integrity_errors = validate_referential_integrity(doc)
    all_errors = schema_errors + integrity_errors

    if all_errors:
        for msg in all_errors:
            print(msg, file=sys.stderr)
        return 1

    if not args.quiet:
        print(f"Valid: {args.input}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
