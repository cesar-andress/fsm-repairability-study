# Operation-inferred repair prompting

Second-pilot variant for **localized feedback (condition E)** where the model describes behavioural corrections and the framework selects patch operations.

## Motivation

Operation-aware prompts still ask the model to choose `add_transition` vs `update_transition`, which can cause duplicate-transition patch-application failures. The operation-inferred variant separates concerns:

| Role | Actor |
|------|--------|
| Behavioural intent | LLM (`from`, `event`, `desired_target`) |
| Operation choice | [`infer_patch_from_corrections.py`](../scripts/infer_patch_from_corrections.py) |

## Prompt template

[`prompts/repair_localized_feedback_operation_inferred.md`](../prompts/repair_localized_feedback_operation_inferred.md)

Placeholders:

- `{{requirement_text}}`
- `{{candidate_fsm_json}}`
- `{{localized_feedback_json}}` (bound from the projected localized diagnostic)

The model must **not** emit patch operations.

## Model output schema

Validated against [`schemas/behavioral_correction.schema.json`](../schemas/behavioral_correction.schema.json):

```json
{
  "schema_version": "1.0.0",
  "corrections": [
    {
      "from": "s1",
      "event": "b",
      "desired_target": "s0",
      "confidence": "high"
    }
  ],
  "rationale": "Return to initial state after a then b"
}
```

Empty `corrections` with `rationale` records a **valid abstention**: the runner writes `corrections.json` and `abstention.json` (no `patch.json`), completes the case with `status = abstained`, `outcome_class = abstained`, `delta_bpr = 0`, and does **not** count the case as `invalid_patch`.

## Inference rules

For each correction, inspecting `candidate_fsm_json.transitions`:

| Candidate FSM | Inferred operation |
|---------------|-------------------|
| `(from, event)` exists, `to` ≠ `desired_target` | `update_transition` |
| No `(from, event)` | `add_transition` |
| `desired_target` ∉ `states` | Error |
| `from` == `desired_target` (new self-loop) | Error |

## CLI / campaign use

```bash
python scripts/generate_patch_ollama.py \
  --condition patch_localized_feedback \
  --prompt-variant operation-inferred \
  --requirement requirement.txt \
  --candidate-fsm candidate.json \
  --diagnostic diagnostic.json \
  --patch-schema schemas/patch.schema.json \
  --model llama3:8b \
  --output-dir work/ollama
```

## E-only strategy

Operation-inferred is a **localized-feedback repair strategy**: the prompt binds `{{localized_feedback_json}}` and the correction schema assumes localization evidence. Binary (C) and trace (D) diagnostics do not provide that surface, so operation-inferred templates are undefined for those conditions.

When `--prompt-variant operation-inferred` is passed to multi-condition runners:

| Runner | C | D | E |
|--------|---|---|---|
| [`run_diagnostic_granularity_pilot.py`](../scripts/run_diagnostic_granularity_pilot.py) | `default` | `default` | `operation-inferred` |
| [`run_pilot_campaign.py`](../scripts/run_pilot_campaign.py) | N/A (single condition) | N/A | `operation-inferred` only if `--condition patch_localized_feedback`; otherwise `default` |

Mapping logic: [`resolve_prompt_variant_for_condition()`](../scripts/generate_patch_ollama.py).

### Granularity pilot summary fields

`diagnostic_granularity_summary.json` includes `prompt_variant_requested` and `prompt_variant_by_condition` (see [`diagnostic_granularity_pilot.md`](diagnostic_granularity_pilot.md)).

## Artefacts

| File | Content |
|------|---------|
| `prompt.txt` | Rendered prompt |
| `raw_response.txt` | Model JSON (corrections) |
| `corrections.json` | Parsed correction document |
| `abstention.json` | Present when `corrections` is empty (abstention artifact) |
| `patch.json` | Inferred + schema-validated patch (omitted on abstention) |

## See also

- [`operation_aware_prompting.md`](operation_aware_prompting.md)
- [`patch_failure_analysis.md`](patch_failure_analysis.md)
- [`repair_prompt_protocol.md`](repair_prompt_protocol.md)
