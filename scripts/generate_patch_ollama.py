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
from ollama_client import OllamaConfig, generate  # noqa: E402

CONDITION_TEMPLATE_STEMS = {
    "patch_binary_feedback": "repair_binary_feedback",
    "patch_trace_feedback": "repair_trace_feedback",
    "patch_localized_feedback": "repair_localized_feedback",
}

PROMPT_VARIANTS = frozenset({"default", "operation-aware"})


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
    suffix = "_operation_aware" if prompt_variant == "operation-aware" else ""
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


class PatchGenerationError(Exception):
    """Raised when prompt assembly, inference, extraction, or validation fails."""


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


def write_outputs(
    output_dir: Path,
    *,
    prompt: str,
    raw_response: str,
    patch: dict[str, Any],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
    (output_dir / "raw_response.txt").write_text(raw_response, encoding="utf-8")
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
    try:
        validate_patch_document(patch)
    except PatchEngineError as exc:
        raise PatchGenerationError(f"patch validation failed: {exc}") from exc

    write_outputs(output_dir, prompt=prompt, raw_response=raw_response, patch=patch)
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
        help="Prompt template set: default (original) or operation-aware (second pilot)",
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
