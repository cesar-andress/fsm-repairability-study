#!/usr/bin/env python3
"""Apply a constrained FSM patch document (see docs/patch_language.md)."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from validate_fsm import validate_fsm_document, validate_referential_integrity  # noqa: E402


def _sync_alphabet(fsm: dict) -> None:
    used = {t["event"] for t in fsm.get("transitions", [])}
    fsm["alphabet"] = sorted(used)


def apply_operation(fsm: dict, op: dict) -> None:
    """Apply one patch operation in place. Raises ValueError on violation."""
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
        incident = op.get("incident_transitions", [])
        for t in incident:
            matches = [
                x
                for x in fsm["transitions"]
                if x["from"] == t["from"]
                and x["event"] == t["event"]
                and x["to"] == t["to"]
            ]
            if not matches:
                raise ValueError(f"incident transition not found: {t}")
        computed = [
            x
            for x in fsm["transitions"]
            if x["from"] == state or x["to"] == state
        ]
        if len(computed) != len(incident):
            raise ValueError(
                "incident_transitions must match all transitions incident on state"
            )
        fsm["states"] = [s for s in fsm["states"] if s != state]
        incident_set = {(t["from"], t["event"], t["to"]) for t in incident}
        fsm["transitions"] = [
            x
            for x in fsm["transitions"]
            if (x["from"], x["event"], x["to"]) not in incident_set
        ]
        _sync_alphabet(fsm)

    elif kind == "rename_state":
        old_name, new_name = op["old_name"], op["new_name"]
        if old_name not in fsm["states"]:
            raise ValueError(f"unknown state: {old_name}")
        if new_name in fsm["states"]:
            raise ValueError(f"state already exists: {new_name}")
        if old_name == new_name:
            raise ValueError("old_name and new_name must differ")
        fsm["states"] = [new_name if s == old_name else s for s in fsm["states"]]
        if fsm["initial_state"] == old_name:
            fsm["initial_state"] = new_name
        for t in fsm["transitions"]:
            if t["from"] == old_name:
                t["from"] = new_name
            if t["to"] == old_name:
                t["to"] = new_name

    elif kind == "change_initial_state":
        prev, new = op["previous_initial"], op["new_initial"]
        if fsm["initial_state"] != prev:
            raise ValueError(
                f"previous_initial {prev!r} != current initial {fsm['initial_state']!r}"
            )
        if new not in fsm["states"]:
            raise ValueError(f"unknown state: {new}")
        if prev == new:
            raise ValueError("previous_initial and new_initial must differ")
        fsm["initial_state"] = new

    elif kind == "add_transition":
        fr, ev, to = op["from"], op["event"], op["to"]
        if fr not in fsm["states"] or to not in fsm["states"]:
            raise ValueError("from/to state missing")
        if fr == to:
            raise ValueError("self-loops are rejected by default")
        for existing in fsm["transitions"]:
            if existing["from"] == fr and existing["event"] == ev:
                raise ValueError(f"duplicate (from, event): {fr}, {ev}")
        fsm["transitions"].append({"from": fr, "event": ev, "to": to})
        _sync_alphabet(fsm)

    elif kind == "remove_transition":
        fr, ev, to = op["from"], op["event"], op["to"]
        before = len(fsm["transitions"])
        fsm["transitions"] = [
            t
            for t in fsm["transitions"]
            if not (t["from"] == fr and t["event"] == ev and t["to"] == to)
        ]
        if len(fsm["transitions"]) == before:
            raise ValueError(f"transition not found: {fr} --{ev}--> {to}")
        _sync_alphabet(fsm)

    elif kind == "update_transition":
        fr, ev = op["from"], op["event"]
        old_to, new_to = op["old_to"], op["new_to"]
        if old_to == new_to:
            raise ValueError("old_to and new_to must differ")
        if new_to not in fsm["states"]:
            raise ValueError(f"unknown state: {new_to}")
        found = False
        for t in fsm["transitions"]:
            if t["from"] == fr and t["event"] == ev and t["to"] == old_to:
                t["to"] = new_to
                found = True
                break
        if not found:
            raise ValueError(f"transition not found for update: {fr} --{ev}--> {old_to}")
        for t in fsm["transitions"]:
            if t["from"] == fr and t["event"] == ev and t["to"] != new_to:
                raise ValueError(f"duplicate (from, event) after update: {fr}, {ev}")

    else:
        raise ValueError(f"unsupported operation: {kind}")


def apply_patch(fsm: dict, patch: dict) -> dict:
    """Return a new FSM dict after applying all patch operations atomically."""
    if patch.get("target_fsm_id") != fsm.get("id"):
        raise ValueError(
            f"patch target_fsm_id {patch.get('target_fsm_id')!r} "
            f"does not match fsm id {fsm.get('id')!r}"
        )
    result = copy.deepcopy(fsm)
    try:
        for op in patch.get("operations", []):
            apply_operation(result, op)
    except ValueError:
        raise
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
