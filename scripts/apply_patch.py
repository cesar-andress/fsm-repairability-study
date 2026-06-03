#!/usr/bin/env python3
"""
Apply constrained FSM patches (v1: transition operations only).

See docs/patch_language.md. State operations are not supported in this version.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMAS_DIR = REPO_ROOT / "schemas"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from validate_fsm import validate_fsm_document, validate_referential_integrity  # noqa: E402

try:
    import jsonschema
    from jsonschema import Draft202012Validator
except ImportError:  # pragma: no cover
    jsonschema = None  # type: ignore
    Draft202012Validator = None  # type: ignore

SUPPORTED_OPERATIONS = frozenset(
    {"add_transition", "remove_transition", "update_transition"}
)
UNSUPPORTED_IN_V1 = frozenset(
    {"add_state", "remove_state", "rename_state", "change_initial_state"}
)


class PatchEngineError(Exception):
    """Raised when patch loading or application fails."""

    def __init__(
        self,
        message: str,
        *,
        operation_index: int | None = None,
        operation: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.operation_index = operation_index
        self.operation = operation

    def format_detailed(self) -> str:
        lines = [str(self)]
        if self.operation_index is not None:
            lines.append(f"  at operation index: {self.operation_index}")
        if self.operation is not None:
            lines.append(f"  operation: {json.dumps(self.operation, sort_keys=True)}")
        return "\n".join(lines)


def _patch_schema_registry():
    if jsonschema is None:
        return None
    from referencing import Registry, Resource

    registry: Registry = Registry()
    for path in sorted(SCHEMAS_DIR.glob("*.json")):
        with path.open(encoding="utf-8") as f:
            contents = json.load(f)
        registry = registry.with_resource(path.name, Resource.from_contents(contents))
    return registry


def load_json(path: Path) -> Any:
    if not path.is_file():
        raise PatchEngineError(f"file not found: {path}")
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        raise PatchEngineError(f"invalid JSON in {path}: {exc}") from exc


def load_fsm(path: Path) -> dict[str, Any]:
    doc = load_json(path)
    if not isinstance(doc, dict):
        raise PatchEngineError(f"FSM document must be a JSON object: {path}")
    return doc


def load_patch(path: Path, *, validate_schema: bool = True) -> dict[str, Any]:
    doc = load_json(path)
    if not isinstance(doc, dict):
        raise PatchEngineError(f"patch document must be a JSON object: {path}")
    if validate_schema:
        validate_patch_document(doc)
    return doc


def validate_patch_document(patch: dict[str, Any]) -> None:
    if Draft202012Validator is None:
        return
    schema_path = SCHEMAS_DIR / "patch.schema.json"
    with schema_path.open(encoding="utf-8") as f:
        schema = json.load(f)
    registry = _patch_schema_registry()
    validator = Draft202012Validator(schema, registry=registry)
    errors = sorted(validator.iter_errors(patch), key=lambda e: list(e.path))
    if errors:
        detail = "; ".join(e.message for e in errors[:5])
        raise PatchEngineError(f"patch schema validation failed: {detail}")


def _transition_key(t: dict[str, str]) -> tuple[str, str, str]:
    return (t["from"], t["event"], t["to"])


def _find_by_from_event(
    transitions: list[dict[str, str]], fr: str, ev: str
) -> list[dict[str, str]]:
    return [t for t in transitions if t["from"] == fr and t["event"] == ev]


def _sync_alphabet(fsm: dict[str, Any]) -> None:
    used = {t["event"] for t in fsm.get("transitions", [])}
    fsm["alphabet"] = sorted(used)


def canonicalize_fsm(fsm: dict[str, Any]) -> dict[str, Any]:
    """Return a deep copy with deterministic ordering for stable output."""
    out = copy.deepcopy(fsm)
    out["states"] = sorted(out.get("states", []))
    transitions = out.get("transitions", [])
    out["transitions"] = sorted(
        transitions,
        key=lambda t: (t["from"], t["event"], t["to"]),
    )
    _sync_alphabet(out)
    return out


def _ensure_supported_op(op: dict[str, Any], index: int) -> str:
    kind = op.get("op")
    if kind in UNSUPPORTED_IN_V1:
        raise PatchEngineError(
            f"operation[{index}] {kind!r}: state operations are not supported "
            f"in patch engine v1 (supported: {sorted(SUPPORTED_OPERATIONS)})",
            operation_index=index,
            operation=op,
        )
    if kind not in SUPPORTED_OPERATIONS:
        raise PatchEngineError(
            f"operation[{index}] unknown op {kind!r}; "
            f"supported in v1: {sorted(SUPPORTED_OPERATIONS)}",
            operation_index=index,
            operation=op,
        )
    return kind


def apply_add_transition(
    fsm: dict[str, Any], op: dict[str, Any], index: int
) -> None:
    fr, ev, to = op["from"], op["event"], op["to"]
    states = fsm.get("states", [])
    if fr not in states:
        raise PatchEngineError(
            f"operation[{index}] add_transition: from state {fr!r} not in "
            f"states {sorted(states)}",
            operation_index=index,
            operation=op,
        )
    if to not in states:
        raise PatchEngineError(
            f"operation[{index}] add_transition: to state {to!r} not in "
            f"states {sorted(states)}",
            operation_index=index,
            operation=op,
        )
    if fr == to:
        raise PatchEngineError(
            f"operation[{index}] add_transition: self-loop {fr!r} --{ev}--> {to!r} "
            "is rejected",
            operation_index=index,
            operation=op,
        )
    conflicts = _find_by_from_event(fsm.get("transitions", []), fr, ev)
    if conflicts:
        existing = conflicts[0]
        raise PatchEngineError(
            f"operation[{index}] add_transition: duplicate (from, event) "
            f"({fr!r}, {ev!r}); existing target {existing['to']!r}",
            operation_index=index,
            operation=op,
        )
    fsm.setdefault("transitions", []).append({"from": fr, "event": ev, "to": to})
    _sync_alphabet(fsm)


def apply_remove_transition(
    fsm: dict[str, Any], op: dict[str, Any], index: int
) -> None:
    fr, ev, to = op["from"], op["event"], op["to"]
    transitions = fsm.get("transitions", [])
    key = (fr, ev, to)
    if key not in {_transition_key(t) for t in transitions}:
        available = [
            f"{t['from']} --{t['event']}--> {t['to']}" for t in transitions
        ]
        raise PatchEngineError(
            f"operation[{index}] remove_transition: no transition "
            f"{fr!r} --{ev}--> {to!r}; available: {available or '(none)'}",
            operation_index=index,
            operation=op,
        )
    fsm["transitions"] = [
        t for t in transitions if _transition_key(t) != key
    ]
    _sync_alphabet(fsm)


def apply_update_transition(
    fsm: dict[str, Any], op: dict[str, Any], index: int
) -> None:
    fr, ev = op["from"], op["event"]
    old_to, new_to = op["old_to"], op["new_to"]
    if old_to == new_to:
        raise PatchEngineError(
            f"operation[{index}] update_transition: old_to and new_to must differ "
            f"(both {old_to!r})",
            operation_index=index,
            operation=op,
        )
    states = fsm.get("states", [])
    if new_to not in states:
        raise PatchEngineError(
            f"operation[{index}] update_transition: new_to state {new_to!r} not in "
            f"states {sorted(states)}",
            operation_index=index,
            operation=op,
        )
    transitions = fsm.get("transitions", [])
    target = None
    for t in transitions:
        if t["from"] == fr and t["event"] == ev and t["to"] == old_to:
            target = t
            break
    if target is None:
        by_fe = _find_by_from_event(transitions, fr, ev)
        hint = (
            f"targets: {[t['to'] for t in by_fe]}" if by_fe else "no (from, event) match"
        )
        raise PatchEngineError(
            f"operation[{index}] update_transition: no transition "
            f"{fr!r} --{ev}--> {old_to!r}; {hint}",
            operation_index=index,
            operation=op,
        )
    target["to"] = new_to
    others = [
        t
        for t in transitions
        if t is not target and t["from"] == fr and t["event"] == ev
    ]
    if others:
        raise PatchEngineError(
            f"operation[{index}] update_transition: duplicate (from, event) "
            f"({fr!r}, {ev!r}) after update",
            operation_index=index,
            operation=op,
        )
    _sync_alphabet(fsm)


def apply_operation(fsm: dict[str, Any], op: dict[str, Any], index: int) -> None:
    kind = _ensure_supported_op(op, index)
    if kind == "add_transition":
        apply_add_transition(fsm, op, index)
    elif kind == "remove_transition":
        apply_remove_transition(fsm, op, index)
    elif kind == "update_transition":
        apply_update_transition(fsm, op, index)


def apply_patch(fsm: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """
    Apply all patch operations and return a canonicalized FSM.

    The input FSM is not mutated. On failure, raises PatchEngineError and leaves
    the caller's FSM unchanged.
    """
    target = patch.get("target_fsm_id")
    fsm_id = fsm.get("id")
    if target != fsm_id:
        raise PatchEngineError(
            f"patch target_fsm_id {target!r} does not match fsm id {fsm_id!r}"
        )

    operations = patch.get("operations")
    if not isinstance(operations, list) or len(operations) == 0:
        raise PatchEngineError("patch operations must be a non-empty array")

    working = copy.deepcopy(fsm)
    for index, op in enumerate(operations):
        if not isinstance(op, dict):
            raise PatchEngineError(
                f"operation[{index}] must be a JSON object, got {type(op).__name__}",
                operation_index=index,
            )
        try:
            apply_operation(working, op, index)
        except PatchEngineError:
            raise
        except KeyError as exc:
            raise PatchEngineError(
                f"operation[{index}] missing required field: {exc}",
                operation_index=index,
                operation=op,
            ) from exc

    result = canonicalize_fsm(working)
    schema_errors = validate_fsm_document(result)
    integrity_errors = validate_referential_integrity(result)
    all_errors = schema_errors + integrity_errors
    if all_errors:
        raise PatchEngineError(
            "post-patch FSM validation failed: " + "; ".join(all_errors)
        )
    return result


def write_fsm(fsm: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = {
        "schema_version": fsm.get("schema_version"),
        "id": fsm.get("id"),
        "states": fsm.get("states"),
        "initial_state": fsm.get("initial_state"),
        "alphabet": fsm.get("alphabet"),
        "transitions": fsm.get("transitions"),
    }
    if "outputs" in fsm:
        ordered["outputs"] = fsm["outputs"]
    if "metadata" in fsm:
        ordered["metadata"] = fsm["metadata"]
    with path.open("w", encoding="utf-8") as f:
        json.dump(ordered, f, indent=2)
        f.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fsm", required=True, type=Path, help="Input FSM JSON")
    parser.add_argument("--patch", required=True, type=Path, help="Patch JSON")
    parser.add_argument("--output", "-o", required=True, type=Path, help="Output FSM JSON")
    parser.add_argument(
        "--no-schema-check",
        action="store_true",
        help="Skip JSON Schema validation of the patch file",
    )
    args = parser.parse_args(argv)

    try:
        fsm = load_fsm(args.fsm)
        patch = load_patch(args.patch, validate_schema=not args.no_schema_check)
        result = apply_patch(fsm, patch)
        write_fsm(result, args.output)
    except PatchEngineError as exc:
        print(exc.format_detailed(), file=sys.stderr)
        return 1

    print(f"Wrote: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
