#!/usr/bin/env python3
"""Score an FSM against a behavioural oracle suite (minimal stub)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from validate_fsm import validate_referential_integrity  # noqa: E402


def simulate_step(fsm: dict, state: str, event: str) -> str | None:
    """Return next state or None if no transition is defined."""
    for t in fsm.get("transitions", []):
        if t["from"] == state and t["event"] == event:
            return t["to"]
    return None


def run_trace(fsm: dict, events: list[str]) -> tuple[bool, list[str]]:
    """Execute a sequence from the initial state; return (ok, state_trace)."""
    state = fsm["initial_state"]
    trace = [state]
    for event in events:
        nxt = simulate_step(fsm, state, event)
        if nxt is None:
            return False, trace
        state = nxt
        trace.append(state)
    return True, trace


def score_against_suite(fsm: dict, suite: dict) -> dict:
    """
    Score FSM against a minimal oracle suite format (stub).

    Expected suite shape (placeholder):
      { "suite_id": "...", "checks": [ { "check_id": "...", "type": "trace",
        "events": ["a","b"], "expected_states": ["s0","s1","s2"] } ] }
    """
    integrity = validate_referential_integrity(fsm)
    if integrity:
        return {
            "suite_id": suite.get("suite_id"),
            "passed": False,
            "checks": [],
            "error": "fsm_integrity_failed",
            "details": integrity,
        }

    check_results = []
    all_passed = True
    for check in suite.get("checks", []):
        cid = check.get("check_id", "unknown")
        ctype = check.get("type", "trace")
        if ctype == "trace":
            events = check.get("events", [])
            expected = check.get("expected_states", [])
            ok, observed = run_trace(fsm, events)
            passed = ok and observed == expected
        else:
            passed = False
            observed = []
        check_results.append(
            {
                "check_id": cid,
                "passed": passed,
                "observed_states": observed if ctype == "trace" else None,
            }
        )
        all_passed = all_passed and passed

    return {
        "suite_id": suite.get("suite_id"),
        "passed": all_passed,
        "checks": check_results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fsm", required=True, type=Path, help="FSM JSON to score")
    parser.add_argument(
        "--oracle-suite",
        required=True,
        type=Path,
        help="Oracle suite JSON (placeholder format)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Optional path to write score JSON",
    )
    args = parser.parse_args(argv)

    with args.fsm.open(encoding="utf-8") as f:
        fsm = json.load(f)
    with args.oracle_suite.open(encoding="utf-8") as f:
        suite = json.load(f)

    if not suite.get("checks"):
        print(
            "Warning: oracle suite has no checks (placeholder). "
            "Score may not reflect study oracles.",
            file=sys.stderr,
        )

    result = score_against_suite(fsm, suite)
    text = json.dumps(result, indent=2)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)

    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
