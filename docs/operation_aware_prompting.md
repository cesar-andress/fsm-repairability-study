# Operation-aware repair prompting

Second-pilot prompt variants that tighten transition-operation rules to reduce patch-engine rejections (duplicate `(from, event)` pairs, invalid targets, no-op updates).

## Templates

| Condition | Default template | Operation-aware template |
|-----------|------------------|---------------------------|
| C — `patch_binary_feedback` | [`repair_binary_feedback.md`](../prompts/repair_binary_feedback.md) | [`repair_binary_feedback_operation_aware.md`](../prompts/repair_binary_feedback_operation_aware.md) |
| D — `patch_trace_feedback` | [`repair_trace_feedback.md`](../prompts/repair_trace_feedback.md) | [`repair_trace_feedback_operation_aware.md`](../prompts/repair_trace_feedback_operation_aware.md) |
| E — `patch_localized_feedback` | [`repair_localized_feedback.md`](../prompts/repair_localized_feedback.md) | [`repair_localized_feedback_operation_aware.md`](../prompts/repair_localized_feedback_operation_aware.md) |

Placeholders are unchanged:

- `{{requirement_text}}`
- `{{candidate_fsm_json}}`
- `{{diagnostic_json}}`
- `{{patch_schema_json}}`

Diagnostic exposure (binary vs trace vs localized) matches the default templates; only transition-operation policy is strengthened.

## Transition Decision Checklist (MANDATORY)

Canonical text: [`prompts/snippets/transition_decision_checklist.md`](../prompts/snippets/transition_decision_checklist.md) (embedded in all operation-aware templates).

| Step | Rule |
|------|------|
| 1 | Scan all `candidate_fsm_json.transitions` |
| 2 | Detect existing `(from, event)` |
| 3 | If exists: **never** `add_transition`; **must** `update_transition` with correct `old_to` / `new_to` |
| 4 | If missing: `add_transition` |
| 5 | Verify no duplicate pairs in `operations`, states ∈ `states`, events ∈ `alphabet`, determinism preserved |
| 6 | On uncertainty: empty `operations` and `metadata.rationale` (prefer abstain over duplicate transitions) |

Output must still be JSON only (no markdown fences), as in each template’s constraints section.

## Selecting a variant

[`generate_patch_ollama.py`](../scripts/generate_patch_ollama.py) loads templates by repair condition and optional variant:

```bash
python scripts/generate_patch_ollama.py \
  --condition patch_trace_feedback \
  --prompt-variant operation-aware \
  --requirement requirement.txt \
  --candidate-fsm candidate.json \
  --diagnostic diagnostic.json \
  --patch-schema schemas/patch.schema.json \
  --model llama3:8b \
  --output-dir work/ollama
```

| `--prompt-variant` | Behaviour |
|--------------------|-----------|
| `default` | Original frozen templates (unchanged) |
| `operation-aware` | Operation-aware templates for the second pilot |
| `operation-inferred` | Localized only: behavioural corrections → inferred patch ops ([`operation_inferred_prompting.md`](operation_inferred_prompting.md)) |

### Campaign runners

The flag is propagated end-to-end:

| Runner | CLI | Summary field |
|--------|-----|---------------|
| [`run_pilot_campaign.py`](../scripts/run_pilot_campaign.py) | `--prompt-variant` | `campaign_summary.json` → `prompt_variant` |
| [`run_diagnostic_granularity_pilot.py`](../scripts/run_diagnostic_granularity_pilot.py) | `--prompt-variant` | `diagnostic_granularity_summary.json` → `prompt_variant` |

Both resolve the CLI value per condition via [`resolve_prompt_variant_for_condition()`](../scripts/generate_patch_ollama.py) before calling [`generate_patch_ollama.py`](../scripts/generate_patch_ollama.py). For `operation-aware`, all of C, D, and E use operation-aware templates. For `operation-inferred`, only E does; C and D fall back to `default` (see [`operation_inferred_prompting.md`](operation_inferred_prompting.md)). Omitting `--prompt-variant` keeps **`default`** behaviour unchanged from earlier pilots.

## Analysis

Pair operation-aware prompting with [`analyze_patch_failures.py`](../scripts/analyze_patch_failures.py) on granularity pilot outputs to compare `duplicate_transition` and related failure classes between campaigns.

## See also

- [`repair_prompt_protocol.md`](repair_prompt_protocol.md)
- [`patch_failure_analysis.md`](patch_failure_analysis.md)
- [`patch_language.md`](patch_language.md)
