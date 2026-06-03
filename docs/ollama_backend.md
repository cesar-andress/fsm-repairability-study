# Ollama repair backend (pilot)

Minimal local patch generation for pilot studies: render a frozen repair prompt, call [Ollama](https://ollama.com/), extract JSON, validate against [`patch.schema.json`](../schemas/patch.schema.json), and write audit files. Implemented by [`scripts/generate_patch_ollama.py`](../scripts/generate_patch_ollama.py).

This backend does **not** apply patches, score FSMs, or modify [`run_repair_condition.py`](../scripts/run_repair_condition.py). Use it to produce `patch.json` for manual inspection or as input to the dry-run orchestrator via `--patch-source`.

## Prompt templates

| `condition` | Template |
|-------------|----------|
| `patch_binary_feedback` | [`prompts/repair_binary_feedback.md`](../prompts/repair_binary_feedback.md) |
| `patch_trace_feedback` | [`prompts/repair_trace_feedback.md`](../prompts/repair_trace_feedback.md) |
| `patch_localized_feedback` | [`prompts/repair_localized_feedback.md`](../prompts/repair_localized_feedback.md) |

Placeholders bound at run time:

- `{{requirement_text}}`
- `{{candidate_fsm_json}}`
- `{{diagnostic_json}}`
- `{{patch_schema_json}}`

Protocol: [`repair_prompt_protocol.md`](repair_prompt_protocol.md).

## Prerequisites

- **Python 3.12+**
- Ollama running locally (`curl -s http://127.0.0.1:11434/api/tags`)
- Model pulled (tag must match `--model`)
- Prior diagnostic from [`build_diagnostic.py`](../scripts/build_diagnostic.py) at the level matching the condition

## CLI

```bash
python scripts/generate_patch_ollama.py \
  --condition patch_trace_feedback \
  --requirement tests/fixtures/dry_run_case/requirement.txt \
  --candidate-fsm tests/fixtures/dry_run_case/candidate_fsm.json \
  --diagnostic /path/to/diagnostic.json \
  --patch-schema schemas/patch.schema.json \
  --model llama3:8b \
  --output-dir /tmp/pilot_patch_run
```

| Flag | Role |
|------|------|
| `--condition` | Selects prompt template (C/D/E patch conditions) |
| `--requirement` | `.txt`/`.md` text or JSON with `requirement_text` |
| `--candidate-fsm` | Candidate FSM JSON |
| `--diagnostic` | Projected diagnostic JSON |
| `--patch-schema` | Patch schema JSON (embedded in prompt) |
| `--model` | Ollama model tag |
| `--output-dir` | Writes `prompt.txt`, `raw_response.txt`, `patch.json` |
| `--ollama-url` | Default `http://127.0.0.1:11434` |
| `--temperature` | Default `0.0` |

## Outputs

| File | Content |
|------|---------|
| `prompt.txt` | Fully rendered prompt sent to Ollama |
| `raw_response.txt` | Unmodified model text |
| `patch.json` | Extracted object after JSON parse + schema validation |

## JSON extraction

The script accepts:

- Plain JSON object in the response
- JSON inside markdown `` ```json `` fences

It does not repair malformed JSON. Validation errors surface as non-zero exit code with a clear message.

## Pilot workflow

```text
score_repair → build_diagnostic → generate_patch_ollama → (optional) run_repair_condition --patch-source patch.json
```

1. Score the candidate and build a diagnostic at the correct level.
2. Run `generate_patch_ollama.py` and inspect `raw_response.txt` / `patch.json`.
3. Optionally feed `patch.json` into the dry-run runner to verify BPR change without calling Ollama again.

## HTTP client

Uses stdlib [`ollama_client.py`](../scripts/ollama_client.py) (`/api/generate`, non-streaming). See [`local_model_execution.md`](local_model_execution.md) for workstation setup.

## Limitations (pilot)

- Single-shot generation; no multi-iteration loop in this script.
- Abstention (`operations: []`) fails schema validation (`minItems: 1` on operations).
- No automatic retry on parse or validation failure.
- Model quality and format compliance are not benchmarked here.

## See also

- [`repair_condition_runner.md`](repair_condition_runner.md) — deterministic loop with external patch file
- [`diagnostic_generation.md`](diagnostic_generation.md)
- [`patch_language.md`](patch_language.md)
