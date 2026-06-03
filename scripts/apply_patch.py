#!/usr/bin/env python3
"""Apply a structured patch to an FSM document (minimal stub)."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Import sibling module without package install
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from validate_fsm import validate_fsm_document, validate_referential_integrity  # noqa: E402


def apply_operation(fsm: dict, op: dict) -> None:
    """Apply one patch operation in place. Raises ValueError on unknown op."""
    kind = op.get("op")
    if kind == "add_state":
        state = op["state"]
        if state in fsm["states"]:
            raise ValueError(f"state already exists: {state}")
        fsm["states"].append(state)
    elif kind == "remove_state":
        state = op["state"]
        if state not in fsm["states"]:
            raise ValueError(f"unknown state: {state}")
        if fsm["initial_state"] == state:
            raise ValueError(f"cannot remove initial state: {state}")
        fsm["states"] = [s for s in fsm["states"] if s != state]
        fsm["transitions"] = [
            t for t in fsm["transitions"] if t["from"] != state and t["to"] != state
        ]
    elif kind == "set_initial_state":
        state = op["state"]
        if state not in fsm["states"]:
            raise ValueError(f"unknown state: {state}")
        fsm["initial_state"] = state
    elif kind == "add_transition":
        t = {"from": op["from"], "event": op["event"], "to": op["to"]}
        if t["event"] not in fsm["alphabet"]:
            fsm["alphabet"].append(t["event"])
        for existing in fsm["transitions"]:
            if (
                existing["from"] == t["from"]
                and existing["event"] == t["event"]
            ):
                raise ValueError(
                    f"duplicate transition: {t['from']} --{t['event']}--> (exists)"
                )
        fsm["transitions"].append(t)
    elif kind == "remove_transition":
        fsm["transitions"] = [
            t
            for t in fsm["transitions"]
            if not (t["from"] == op["from"] and t["event"] == op["event"])
        ]
    elif kind == "relabel_event":
        old, new = op["from"], op["to"]
        if new not in fsm["alphabet"]:
            fsm["alphabet"].append(new)
        for t in fsm["transitions"]:
            if t["event"] == old:
                t["event"] = new
        if old in fsm["alphabet"] and old != new:
            still_used = any(t["event"] == old for t in fsm["transitions"])
            if not still_used:
                fsm["alphabet"] = [e for e in fsm["alphabet"] if e != old]
    else:
        raise ValueError(f"unsupported operation: {kind}")


def apply_patch(fsm: dict, patch: dict) -> dict:
    """Return a new FSM dict after applying all patch operations."""
    if patch.get("target_fsm_id") != fsm.get("id"):
        raise ValueError(
            f"patch target_fsm_id {patch.get('target_fsm_id')!r} "
            f"does not match fsm id {fsm.get('id')!r}"
        )
    result = copy.deepcopy(fsm)
    for op in patch.get("operations", []):
        apply_operation(result, op)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fsm", required=True, type=Path, help="Input FSM JSON")
    parser.add_argument("--patch", required=True, type=Path, help="Patch JSON")
    parser.add_argument("--output", "-o", required=True, type=Path, help="Output FSM JSON")
    args = parser.parse_args(argv)

    with args.fsm.open(encoding="utf-8") as f:
        fsm = json.load(f)
    with args.patch.open(encoding="utf-8") as f:
        patch = json.load(f)

    try:
        repaired = apply_patch(fsm, patch)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1

    errors = validate_fsm_document(repaired) + validate_referential_integrity(repaired)
    if errors:
        for msg in errors:
            print(msg, file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        json.dump(repaired, f, indent=2)
        f.write("\n")

    print(f"Wrote: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
