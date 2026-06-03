#!/usr/bin/env python3
"""
Deterministic scoring: evaluate one FSM against one oracle suite.

See docs/scoring_interface.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from validate_fsm import validate_referential_integrity  # noqa: E402

SCORE_SCHEMA_VERSION = "1.0.0"
TEST_TYPES = ("trace", "final_state", "rejected_event")


def _transition_enabled(transition: dict[str, Any]) -> bool:
    """
    Transitions match on (from, event). Guards are ignored unless boolean literals.
    Non-boolean guards disable the transition for matching (documented limitation).
    """
    if "guard" not in transition:
        return True
    guard = transition["guard"]
    if isinstance(guard, bool):
        return guard
    return False


def _resolve_transition(fsm: dict[str, Any], state: str, event: str) -> str | None:
    """Return target state or None if no enabled transition matches."""
    for t in fsm.get("transitions", []):
        if t.get("from") != state or t.get("event") != event:
            continue
        if not _transition_enabled(t):
            continue
        return t.get("to")
    return None


def run_trace(fsm: dict[str, Any], events: list[str]) -> tuple[bool, list[str]]:
    """Execute events from initial_state; stop early if transition undefined."""
    state = fsm["initial_state"]
    trace = [state]
    for event in events:
        nxt = _resolve_transition(fsm, state, event)
        if nxt is None:
            return False, trace
        state = nxt
        trace.append(state)
    return True, trace


def _check_final_states(fsm: dict[str, Any], state: str) -> bool:
    finals = fsm.get("final_states")
    if not finals:
        return True
    return state in finals


def _evaluate_test(fsm: dict[str, Any], test: dict[str, Any]) -> dict[str, Any]:
    test_id = test["test_id"]
    test_type = test["type"]
    events = test.get("events", [])

    if test_type == "trace":
        expected = test.get("expected_states", [])
        ok, observed = run_trace(fsm, events)
        passed = ok and observed == expected
        if passed:
            return {"test_id": test_id, "passed": True, "type": test_type}
        failure_type = "trace_mismatch" if ok else "undefined_transition"
        return {
            "test_id": test_id,
            "passed": False,
            "type": test_type,
            "failure": {
                "test_id": test_id,
                "failure_type": failure_type,
                "expected": {"states": expected},
                "observed": {"states": observed},
                "trace": {"events": events},
                "diagnostic_hint": test.get("diagnostic_hint", ""),
            },
        }

    if test_type == "final_state":
        expected_final = test["expected_final_state"]
        ok, observed = run_trace(fsm, events)
        final_state = observed[-1] if observed else None
        in_finals = _check_final_states(fsm, final_state) if final_state else False
        passed = ok and final_state == expected_final and in_finals
        if passed:
            return {"test_id": test_id, "passed": True, "type": test_type}
        return {
            "test_id": test_id,
            "passed": False,
            "type": test_type,
            "failure": {
                "test_id": test_id,
                "failure_type": "final_state_mismatch"
                if ok
                else "undefined_transition",
                "expected": {"final_state": expected_final, "states": observed},
                "observed": {"final_state": final_state, "states": observed},
                "trace": {"events": events},
                "diagnostic_hint": test.get("diagnostic_hint", ""),
            },
        }

    if test_type == "rejected_event":
        from_state = test.get("from_state", fsm["initial_state"])
        if len(events) != 1:
            return {
                "test_id": test_id,
                "passed": False,
                "type": test_type,
                "failure": {
                    "test_id": test_id,
                    "failure_type": "invalid_test_spec",
                    "expected": {"single_event": True},
                    "observed": {"events": events},
                    "trace": {"events": events},
                    "diagnostic_hint": "rejected_event requires exactly one event",
                },
            }
        event = events[0]
        nxt = _resolve_transition(fsm, from_state, event)
        passed = nxt is None
        if passed:
            return {"test_id": test_id, "passed": True, "type": test_type}
        return {
            "test_id": test_id,
            "passed": False,
            "type": test_type,
            "failure": {
                "test_id": test_id,
                "failure_type": "unexpected_transition",
                "expected": {"from": from_state, "event": event, "no_transition": True},
                "observed": {"to": nxt},
                "trace": {"events": events, "from_state": from_state},
                "diagnostic_hint": test.get("diagnostic_hint", ""),
            },
        }

    return {
        "test_id": test_id,
        "passed": False,
        "type": test_type,
        "failure": {
            "test_id": test_id,
            "failure_type": "unsupported_test_type",
            "expected": {},
            "observed": {},
            "trace": {},
            "diagnostic_hint": f"unsupported type: {test_type}",
        },
    }


def _type_agreement(results: list[dict[str, Any]], test_type: str) -> float | None:
    typed = [r for r in results if r.get("type") == test_type]
    if not typed:
        return None
    passed = sum(1 for r in typed if r["passed"])
    return passed / len(typed)


def score_fsm(
    fsm: dict[str, Any],
    suite: dict[str, Any],
    *,
    fsm_path: str | None = None,
    oracle_suite_path: str | None = None,
) -> dict[str, Any]:
    """
    Score one FSM against one oracle suite. Deterministic for fixed inputs.
    """
    integrity_errors = validate_referential_integrity(fsm)
    tests = suite.get("tests", suite.get("checks", []))

    if integrity_errors:
        return {
            "score_schema_version": SCORE_SCHEMA_VERSION,
            "fsm_path": fsm_path,
            "oracle_suite_path": oracle_suite_path,
            "suite_id": suite.get("suite_id"),
            "total_tests": len(tests),
            "passed_tests": 0,
            "failed_tests": len(tests) if tests else 0,
            "bpr": 0.0 if tests else 1.0,
            "component_metrics": {
                "final_state_agreement": None,
                "trace_agreement": None,
                "rejected_event_agreement": None,
            },
            "failures": [
                {
                    "test_id": "_fsm_integrity",
                    "failure_type": "fsm_integrity_error",
                    "expected": {"valid_fsm": True},
                    "observed": {"errors": integrity_errors},
                    "trace": {},
                    "diagnostic_hint": "FSM failed referential integrity before scoring",
                }
            ],
            "error": "fsm_integrity_failed",
        }

    results = [_evaluate_test(fsm, t) for t in tests]
    passed_tests = sum(1 for r in results if r["passed"])
    total = len(results)
    failed_tests = total - passed_tests
    bpr = (passed_tests / total) if total else 1.0

    failures = [r["failure"] for r in results if not r["passed"] and "failure" in r]

    return {
        "score_schema_version": SCORE_SCHEMA_VERSION,
        "fsm_path": fsm_path,
        "oracle_suite_path": oracle_suite_path,
        "suite_id": suite.get("suite_id"),
        "total_tests": total,
        "passed_tests": passed_tests,
        "failed_tests": failed_tests,
        "bpr": bpr,
        "component_metrics": {
            "final_state_agreement": _type_agreement(results, "final_state"),
            "trace_agreement": _type_agreement(results, "trace"),
            "rejected_event_agreement": _type_agreement(results, "rejected_event"),
        },
        "failures": failures,
    }


def score_against_suite(fsm: dict[str, Any], suite: dict[str, Any]) -> dict[str, Any]:
    """Legacy adapter: map new report shape to {passed, checks, bpr} for older callers."""
    report = score_fsm(fsm, suite)
    failed_ids = {f["test_id"] for f in report.get("failures", [])}
    checks = []
    for test in suite.get("tests", suite.get("checks", [])):
        tid = test.get("test_id", test.get("check_id", "unknown"))
        passed = tid not in failed_ids
        entry: dict[str, Any] = {"check_id": tid, "passed": passed}
        if not passed:
            failure = next(f for f in report["failures"] if f["test_id"] == tid)
            entry["observed_states"] = failure.get("observed", {}).get("states")
        checks.append(entry)
    return {
        "suite_id": report.get("suite_id"),
        "passed": report["bpr"] == 1.0,
        "checks": checks,
        "bpr": report["bpr"],
        "passed_tests": report["passed_tests"],
        "total_tests": report["total_tests"],
    }


def write_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = {
        "score_schema_version": report["score_schema_version"],
        "fsm_path": report.get("fsm_path"),
        "oracle_suite_path": report.get("oracle_suite_path"),
        "suite_id": report.get("suite_id"),
        "total_tests": report["total_tests"],
        "passed_tests": report["passed_tests"],
        "failed_tests": report["failed_tests"],
        "bpr": report["bpr"],
        "component_metrics": report["component_metrics"],
        "failures": report["failures"],
    }
    if "error" in report:
        ordered["error"] = report["error"]
    path.write_text(json.dumps(ordered, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fsm", required=True, type=Path, help="FSM JSON path")
    parser.add_argument(
        "--oracles",
        required=True,
        type=Path,
        help="Oracle suite JSON path",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Output score report JSON path",
    )
    args = parser.parse_args(argv)

    with args.fsm.open(encoding="utf-8") as f:
        fsm = json.load(f)
    with args.oracles.open(encoding="utf-8") as f:
        suite = json.load(f)

    report = score_fsm(
        fsm,
        suite,
        fsm_path=str(args.fsm),
        oracle_suite_path=str(args.oracles),
    )
    write_report(report, args.output)
    print(json.dumps(report, indent=2))

    return 0 if report["bpr"] == 1.0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
