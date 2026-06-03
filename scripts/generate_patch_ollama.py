#!/usr/bin/env python3
"""
Generate a repair patch JSON via local Ollama using frozen prompt templates.

Renders prompts/repair_*_feedback.md, calls Ollama, extracts JSON, validates against
patch.schema.json, and writes prompt.txt, raw_response.txt, and patch.json.

Does not apply patches or score FSMs. See docs/ollama_backend.md.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
PROMPTS_DIR = REPO_ROOT / "prompts"
SCHEMAS_DIR = REPO_ROOT / "schemas"

sys.path.insert(0, str(REPO_ROOT / "scripts"))

from apply_patch import PatchEngineError, validate_patch_document  # noqa: E402
from infer_patch_from_corrections import (  # noqa: E402
    CorrectionInferenceError,
    corrections_indicate_abstention,
    extract_correction_json,
    infer_patch_from_corrections,
)
from ollama_client import OllamaConfig, generate  # noqa: E402

CONDITION_TEMPLATE_STEMS = {
    "patch_binary_feedback": "repair_binary_feedback",
    "patch_trace_feedback": "repair_trace_feedback",
    "patch_localized_feedback": "repair_localized_feedback",
}

PROMPT_VARIANTS = frozenset({"default", "operation-aware", "operation-inferred"})

OPERATION_INFERRED_CONDITION = "patch_localized_feedback"


def resolve_prompt_variant_for_condition(
    global_prompt_variant: str,
    condition: str,
) -> str:
    """
    Map a CLI --prompt-variant to the effective variant for one repair condition.

    operation-inferred applies only to patch_localized_feedback (E); C and D use default.
    default and operation-aware pass through unchanged.
    """
    if global_prompt_variant not in PROMPT_VARIANTS:
        raise PatchGenerationError(
            f"unsupported prompt_variant {global_prompt_variant!r}; "
            f"expected one of: {', '.join(sorted(PROMPT_VARIANTS))}"
        )
    if condition not in CONDITION_TEMPLATE_STEMS:
        supported = ", ".join(sorted(CONDITION_TEMPLATE_STEMS))
        raise PatchGenerationError(
            f"unsupported condition {condition!r}; expected one of: {supported}"
        )
    if global_prompt_variant == "operation-inferred":
        if condition == OPERATION_INFERRED_CONDITION:
            return "operation-inferred"
        return "default"
    return global_prompt_variant


CORRECTION_PLACEHOLDERS = (
    "{{requirement_text}}",
    "{{candidate_fsm_json}}",
    "{{localized_feedback_json}}",
)


def template_path_for(condition: str, prompt_variant: str = "default") -> Path:
    if prompt_variant not in PROMPT_VARIANTS:
        raise PatchGenerationError(
            f"unsupported prompt_variant {prompt_variant!r}; "
            f"expected one of: {', '.join(sorted(PROMPT_VARIANTS))}"
        )
    stem = CONDITION_TEMPLATE_STEMS.get(condition)
    if stem is None:
        supported = ", ".join(sorted(CONDITION_TEMPLATE_STEMS))
        raise PatchGenerationError(
            f"unsupported condition {condition!r}; expected one of: {supported}"
        )
    if prompt_variant == "operation-aware":
        suffix = "_operation_aware"
    elif prompt_variant == "operation-inferred":
        if condition != OPERATION_INFERRED_CONDITION:
            raise PatchGenerationError(
                f"operation-inferred prompts apply only to {OPERATION_INFERRED_CONDITION!r}, "
                f"not {condition!r}"
            )
        suffix = "_operation_inferred"
    else:
        suffix = ""
    return PROMPTS_DIR / f"{stem}{suffix}.md"


# Backward-compatible map (default variant only).
CONDITION_TEMPLATES = {
    cond: template_path_for(cond, "default")
    for cond in CONDITION_TEMPLATE_STEMS
}

PLACEHOLDERS = (
    "{{requirement_text}}",
    "{{candidate_fsm_json}}",
    "{{diagnostic_json}}",
    "{{patch_schema_json}}",
)


ABSTENTION_FILENAME = "abstention.json"
ABSTENTION_KIND = "abstention"
ABSTENTION_SCHEMA_VERSION = "1.0.0"


class PatchGenerationError(Exception):
    """Raised when prompt assembly, inference, extraction, or validation fails."""


class PatchAbstention(Exception):
    """Raised when the model returns empty corrections (valid abstention, not a patch failure)."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir.resolve()
        super().__init__(f"repair abstention recorded under {self.output_dir}")


def resolve_condition(condition: str, *, prompt_variant: str = "default") -> Path:
    path = template_path_for(condition, prompt_variant)
    if not path.is_file():
        raise PatchGenerationError(f"prompt template not found: {path}")
    return path


def load_requirement_text(path: Path) -> str:
    if not path.is_file():
        raise PatchGenerationError(f"requirement file not found: {path}")
    raw = path.read_text(encoding="utf-8").strip()
    if path.suffix.lower() == ".json":
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise PatchGenerationError(f"invalid JSON requirement file: {exc}") from exc
        if isinstance(data, dict) and "requirement_text" in data:
            text = data["requirement_text"]
            if isinstance(text, str) and text.strip():
                return text.strip()
    if not raw:
        raise PatchGenerationError(f"requirement file is empty: {path}")
    return raw


def load_json_document(path: Path, *, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise PatchGenerationError(f"{label} not found: {path}")
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        raise PatchGenerationError(f"invalid JSON in {label} {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise PatchGenerationError(f"{label} must be a JSON object: {path}")
    return data


def format_json_for_prompt(doc: dict[str, Any]) -> str:
    return json.dumps(doc, indent=2, ensure_ascii=False)


def render_repair_prompt(
    template_path: Path,
    *,
    requirement_text: str,
    candidate_fsm: dict[str, Any],
    diagnostic: dict[str, Any],
    patch_schema: dict[str, Any],
) -> str:
    template = template_path.read_text(encoding="utf-8")
    for placeholder in PLACEHOLDERS:
        if placeholder not in template:
            raise PatchGenerationError(
                f"template missing placeholder {placeholder}: {template_path}"
            )
    rendered = template
    rendered = rendered.replace("{{requirement_text}}", requirement_text)
    rendered = rendered.replace(
        "{{candidate_fsm_json}}", format_json_for_prompt(candidate_fsm)
    )
    rendered = rendered.replace("{{diagnostic_json}}", format_json_for_prompt(diagnostic))
    rendered = rendered.replace(
        "{{patch_schema_json}}", format_json_for_prompt(patch_schema)
    )
    for placeholder in PLACEHOLDERS:
        if placeholder in rendered:
            raise PatchGenerationError(
                f"unreplaced placeholder {placeholder} after rendering"
            )
    return rendered


def render_operation_inferred_prompt(
    template_path: Path,
    *,
    requirement_text: str,
    candidate_fsm: dict[str, Any],
    diagnostic: dict[str, Any],
) -> str:
    template = template_path.read_text(encoding="utf-8")
    for placeholder in CORRECTION_PLACEHOLDERS:
        if placeholder not in template:
            raise PatchGenerationError(
                f"template missing placeholder {placeholder}: {template_path}"
            )
    rendered = template
    rendered = rendered.replace("{{requirement_text}}", requirement_text)
    rendered = rendered.replace(
        "{{candidate_fsm_json}}", format_json_for_prompt(candidate_fsm)
    )
    rendered = rendered.replace(
        "{{localized_feedback_json}}", format_json_for_prompt(diagnostic)
    )
    for placeholder in CORRECTION_PLACEHOLDERS:
        if placeholder in rendered:
            raise PatchGenerationError(
                f"unreplaced placeholder {placeholder} after rendering"
            )
    return rendered


def extract_patch_json(raw_response: str) -> dict[str, Any]:
    """Extract the first JSON object from model text (plain or markdown-fenced)."""
    text = raw_response.strip()
    if not text:
        raise PatchGenerationError("model response is empty")

    fence = re.search(r"```(?:json)?\s*\n(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()

    start = text.find("{")
    if start < 0:
        raise PatchGenerationError("no JSON object found in model response")

    try:
        doc, _end = json.JSONDecoder().raw_decode(text, start)
    except json.JSONDecodeError as exc:
        raise PatchGenerationError(f"failed to parse patch JSON: {exc}") from exc

    if not isinstance(doc, dict):
        raise PatchGenerationError("patch JSON must be a single object")
    return doc


def build_abstention_artifact(
    corrections_doc: dict[str, Any],
    *,
    target_fsm_id: str,
) -> dict[str, Any]:
    return {
        "schema_version": ABSTENTION_SCHEMA_VERSION,
        "kind": ABSTENTION_KIND,
        "target_fsm_id": target_fsm_id,
        "corrections": corrections_doc,
        "metadata": {
            "abstain": True,
            "rationale": corrections_doc.get("rationale", ""),
            "inference": "operation_inferred",
        },
    }


def write_abstention_outputs(
    output_dir: Path,
    *,
    prompt: str,
    raw_response: str,
    corrections_doc: dict[str, Any],
    abstention: dict[str, Any],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
    (output_dir / "raw_response.txt").write_text(raw_response, encoding="utf-8")
    (output_dir / "corrections.json").write_text(
        json.dumps(corrections_doc, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (output_dir / ABSTENTION_FILENAME).write_text(
        json.dumps(abstention, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    patch_path = output_dir / "patch.json"
    if patch_path.is_file():
        patch_path.unlink()


def emit_operation_inferred_abstention(
    output_dir: Path,
    *,
    prompt: str,
    raw_response: str,
    corrections_doc: dict[str, Any],
    candidate_fsm: dict[str, Any],
) -> None:
    """Persist abstention artefacts and remove any invalid empty patch.json."""
    target_id = str(candidate_fsm.get("id", "candidate"))
    abstention = build_abstention_artifact(corrections_doc, target_fsm_id=target_id)
    write_abstention_outputs(
        output_dir,
        prompt=prompt,
        raw_response=raw_response,
        corrections_doc=corrections_doc,
        abstention=abstention,
    )


def read_stored_corrections(ollama_dir: Path) -> dict[str, Any] | None:
    corrections_path = ollama_dir / "corrections.json"
    if corrections_path.is_file():
        try:
            with corrections_path.open(encoding="utf-8") as f:
                doc = json.load(f)
            return doc if isinstance(doc, dict) else None
        except json.JSONDecodeError:
            return None
    raw_path = ollama_dir / "raw_response.txt"
    if raw_path.is_file():
        try:
            return extract_correction_json(raw_path.read_text(encoding="utf-8"))
        except CorrectionInferenceError:
            return None
    return None


def is_empty_patch_validation_error(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return "[] should be non-empty" in msg or (
        "patch validation failed" in msg and "non-empty" in msg
    )


def recover_operation_inferred_abstention(
    ollama_dir: Path,
    prompt_variant: str,
    exc: BaseException,
    *,
    candidate_fsm: dict[str, Any] | None = None,
) -> bool:
    """
    True when a failed empty-patch validation should be treated as abstention.

    Handles legacy runs that wrote patch.json with operations: [] before abstention
    normalization, as long as corrections.json (or raw_response) shows corrections: [].
    """
    if prompt_variant != "operation-inferred":
        return False
    if not is_empty_patch_validation_error(exc):
        return False
    corrections = read_stored_corrections(ollama_dir)
    if corrections is None:
        return (ollama_dir / ABSTENTION_FILENAME).is_file()
    if not corrections_indicate_abstention(corrections):
        return False
    if not (ollama_dir / ABSTENTION_FILENAME).is_file() and candidate_fsm is not None:
        prompt = (ollama_dir / "prompt.txt").read_text(encoding="utf-8")
        raw = (ollama_dir / "raw_response.txt").read_text(encoding="utf-8")
        emit_operation_inferred_abstention(
            ollama_dir,
            prompt=prompt,
            raw_response=raw,
            corrections_doc=corrections,
            candidate_fsm=candidate_fsm,
        )
    return True


def infer_patch_for_operation_inferred(
    output_dir: Path,
    *,
    prompt: str,
    raw_response: str,
    candidate_fsm: dict[str, Any],
    corrections_doc: dict[str, Any],
) -> dict[str, Any]:
    """Return a validated patch or raise PatchAbstention when the model abstains."""
    if corrections_indicate_abstention(corrections_doc):
        emit_operation_inferred_abstention(
            output_dir,
            prompt=prompt,
            raw_response=raw_response,
            corrections_doc=corrections_doc,
            candidate_fsm=candidate_fsm,
        )
        raise PatchAbstention(output_dir)
    try:
        patch = infer_patch_from_corrections(candidate_fsm, corrections_doc)
    except CorrectionInferenceError as exc:
        if "abstention" in str(exc).lower():
            emit_operation_inferred_abstention(
                output_dir,
                prompt=prompt,
                raw_response=raw_response,
                corrections_doc=corrections_doc,
                candidate_fsm=candidate_fsm,
            )
            raise PatchAbstention(output_dir) from exc
        raise PatchGenerationError(f"correction inference failed: {exc}") from exc
    if not patch.get("operations"):
        emit_operation_inferred_abstention(
            output_dir,
            prompt=prompt,
            raw_response=raw_response,
            corrections_doc=corrections_doc,
            candidate_fsm=candidate_fsm,
        )
        raise PatchAbstention(output_dir)
    return patch


def write_outputs(
    output_dir: Path,
    *,
    prompt: str,
    raw_response: str,
    patch: dict[str, Any],
    corrections: dict[str, Any] | None = None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
    (output_dir / "raw_response.txt").write_text(raw_response, encoding="utf-8")
    if corrections is not None:
        (output_dir / "corrections.json").write_text(
            json.dumps(corrections, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    (output_dir / "patch.json").write_text(
        json.dumps(patch, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def generate_patch_ollama(
    *,
    condition: str,
    requirement_path: Path,
    candidate_fsm_path: Path,
    diagnostic_path: Path,
    patch_schema_path: Path,
    model: str,
    output_dir: Path,
    ollama_config: OllamaConfig | None = None,
    generate_options: dict[str, Any] | None = None,
    prompt_variant: str = "default",
) -> tuple[str, str, dict[str, Any]]:
    """
    Render prompt, call Ollama, extract and validate patch.

    Returns (prompt, raw_response, patch_dict).
    """
    template_path = resolve_condition(condition, prompt_variant=prompt_variant)
    requirement_text = load_requirement_text(requirement_path)
    candidate_fsm = load_json_document(candidate_fsm_path, label="candidate FSM")
    diagnostic = load_json_document(diagnostic_path, label="diagnostic")
    patch_schema = load_json_document(patch_schema_path, label="patch schema")

    if prompt_variant == "operation-inferred":
        prompt = render_operation_inferred_prompt(
            template_path,
            requirement_text=requirement_text,
            candidate_fsm=candidate_fsm,
            diagnostic=diagnostic,
        )
        raw_response = generate(
            model,
            prompt,
            config=ollama_config,
            options=generate_options,
        )
        corrections = extract_correction_json(raw_response)
        patch = infer_patch_for_operation_inferred(
            output_dir,
            prompt=prompt,
            raw_response=raw_response,
            candidate_fsm=candidate_fsm,
            corrections_doc=corrections,
        )
    else:
        prompt = render_repair_prompt(
            template_path,
            requirement_text=requirement_text,
            candidate_fsm=candidate_fsm,
            diagnostic=diagnostic,
            patch_schema=patch_schema,
        )
        raw_response = generate(
            model,
            prompt,
            config=ollama_config,
            options=generate_options,
        )
        patch = extract_patch_json(raw_response)
        corrections = None

    try:
        validate_patch_document(patch)
    except PatchEngineError as exc:
        raise PatchGenerationError(f"patch validation failed: {exc}") from exc

    write_outputs(
        output_dir,
        prompt=prompt,
        raw_response=raw_response,
        patch=patch,
        corrections=corrections if prompt_variant == "operation-inferred" else None,
    )
    return prompt, raw_response, patch


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--condition",
        required=True,
        choices=sorted(CONDITION_TEMPLATE_STEMS),
        help="Repair condition (selects prompt template)",
    )
    parser.add_argument(
        "--prompt-variant",
        choices=sorted(PROMPT_VARIANTS),
        default="default",
        help=(
            "Prompt template set: default, operation-aware, or operation-inferred "
            "(localized only; corrections inferred to patch ops)"
        ),
    )
    parser.add_argument(
        "--requirement",
        required=True,
        type=Path,
        help="Requirement text file (.txt/.md) or JSON with requirement_text",
    )
    parser.add_argument(
        "--candidate-fsm",
        required=True,
        type=Path,
        help="Candidate FSM JSON path",
    )
    parser.add_argument(
        "--diagnostic",
        required=True,
        type=Path,
        help="Diagnostic JSON path",
    )
    parser.add_argument(
        "--patch-schema",
        required=True,
        type=Path,
        help="Patch JSON Schema path (typically schemas/patch.schema.json)",
    )
    parser.add_argument(
        "--model",
        required=True,
        help="Ollama model tag (e.g. llama3:8b)",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Directory for prompt.txt, raw_response.txt, patch.json",
    )
    parser.add_argument(
        "--ollama-url",
        default="http://127.0.0.1:11434",
        help="Ollama base URL (default: http://127.0.0.1:11434)",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="Ollama decoding temperature (default: 0.0)",
    )
    args = parser.parse_args(argv)

    config = OllamaConfig(base_url=args.ollama_url)
    options = {"temperature": args.temperature}

    try:
        generate_patch_ollama(
            condition=args.condition,
            requirement_path=args.requirement,
            candidate_fsm_path=args.candidate_fsm,
            diagnostic_path=args.diagnostic,
            patch_schema_path=args.patch_schema,
            model=args.model,
            output_dir=args.output_dir,
            ollama_config=config,
            generate_options=options,
            prompt_variant=args.prompt_variant,
        )
    except (PatchGenerationError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"wrote {args.output_dir / 'prompt.txt'}")
    print(f"wrote {args.output_dir / 'raw_response.txt'}")
    print(f"wrote {args.output_dir / 'patch.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
