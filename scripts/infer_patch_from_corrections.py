#!/usr/bin/env python3
"""
Convert behavioural correction JSON into a patch document (v1 transition ops).

The model describes intended (from, event, desired_target) fixes; this module
selects add_transition vs update_transition by inspecting the candidate FSM.

See docs/operation_inferred_prompting.md.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMAS_DIR = REPO_ROOT / "schemas"
CORRECTION_SCHEMA_VERSION = "1.0.0"
PATCH_SCHEMA_VERSION = "1.0.0"
SLUG_RE = re.compile(r"^[a-z][a-z0-9_]*$")


class CorrectionInferenceError(Exception):
    """Raised when correction JSON or inference fails."""


def _find_by_from_event(
    transitions: list[dict[str, str]], fr: str, ev: str
) -> list[dict[str, str]]:
    return [t for t in transitions if t.get("from") == fr and t.get("event") == ev]


def validate_correction_document(doc: dict[str, Any]) -> None:
    try:
        import jsonschema
        from jsonschema import Draft202012Validator
        from referencing import Registry, Resource
    except ImportError as exc:  # pragma: no cover
        raise CorrectionInferenceError(
            "jsonschema is required for correction validation"
        ) from exc

    registry: Registry = Registry()
    for path in sorted(SCHEMAS_DIR.glob("*.json")):
        with path.open(encoding="utf-8") as f:
            registry = registry.with_resource(
                path.name, Resource.from_contents(json.load(f))
            )
    with (SCHEMAS_DIR / "behavioral_correction.schema.json").open(
        encoding="utf-8"
    ) as f:
        schema = json.load(f)
    validator = Draft202012Validator(schema, registry=registry)
    errors = sorted(validator.iter_errors(doc), key=lambda e: e.path)
    if errors:
        raise CorrectionInferenceError(errors[0].message)


def extract_correction_json(raw_response: str) -> dict[str, Any]:
    text = raw_response.strip()
    if not text:
        raise CorrectionInferenceError("model response is empty")
    fence = re.search(r"```(?:json)?\s*\n(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()
    start = text.find("{")
    if start < 0:
        raise CorrectionInferenceError("no JSON object found in model response")
    try:
        doc, _end = json.JSONDecoder().raw_decode(text, start)
    except json.JSONDecodeError as exc:
        raise CorrectionInferenceError(f"failed to parse correction JSON: {exc}") from exc
    if not isinstance(doc, dict):
        raise CorrectionInferenceError("correction JSON must be a single object")
    return doc


def _slug(value: str, fallback: str = "repair") -> str:
    s = value.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    if not s or not SLUG_RE.match(s):
        s = fallback
    return s[:128]


def infer_patch_from_corrections(
    candidate_fsm: dict[str, Any],
    corrections_doc: dict[str, Any],
    *,
    patch_id: str | None = None,
) -> dict[str, Any]:
    """
    Map behavioural corrections to patch operations using candidate FSM structure.
    """
    validate_correction_document(corrections_doc)
    states = set(candidate_fsm.get("states") or [])
    transitions = [
        dict(t) for t in (candidate_fsm.get("transitions") or []) if isinstance(t, dict)
    ]
    target_fsm_id = str(candidate_fsm.get("id", "candidate"))
    operations: list[dict[str, Any]] = []
    metadata: dict[str, Any] = {
        "inference": "operation_inferred",
        "rationale": corrections_doc.get("rationale", ""),
    }

    for idx, corr in enumerate(corrections_doc.get("corrections") or []):
        if not isinstance(corr, dict):
            raise CorrectionInferenceError(f"corrections[{idx}] must be an object")
        fr = corr["from"]
        ev = corr["event"]
        desired = corr["desired_target"]
        if desired not in states:
            raise CorrectionInferenceError(
                f"corrections[{idx}] desired_target {desired!r} not in candidate states"
            )
        if fr == desired:
            raise CorrectionInferenceError(
                f"corrections[{idx}] self-loop {fr!r} --{ev}--> {desired!r} is not allowed"
            )

        existing = _find_by_from_event(transitions, fr, ev)
        if existing:
            current_to = existing[0]["to"]
            if current_to == desired:
                continue
            operations.append(
                {
                    "op": "update_transition",
                    "from": fr,
                    "event": ev,
                    "old_to": current_to,
                    "new_to": desired,
                }
            )
            for t in transitions:
                if t.get("from") == fr and t.get("event") == ev:
                    t["to"] = desired
                    break
            continue

        operations.append(
            {"op": "add_transition", "from": fr, "event": ev, "to": desired}
        )
        transitions.append({"from": fr, "event": ev, "to": desired})

    pid = patch_id or f"{_slug(target_fsm_id)}_inferred"
    if not corrections_doc.get("corrections"):
        metadata["abstain"] = True

    return {
        "schema_version": PATCH_SCHEMA_VERSION,
        "patch_id": pid,
        "target_fsm_id": target_fsm_id,
        "operations": operations,
        "metadata": metadata,
    }
