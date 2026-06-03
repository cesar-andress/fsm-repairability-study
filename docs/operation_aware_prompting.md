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

## Mandatory operation-aware rules

1. Scan `candidate_fsm_json.transitions` before any `add_transition`.
2. Never use `add_transition` when the same `from` and `event` already exist.
3. Use `update_transition` when the target state is wrong.
4. Do not emit `update_transition` when `old_to` equals `new_to`.
5. Target states must appear in `candidate_fsm_json.states`.
6. Avoid new self-loops unless the candidate already has them and the diagnostic justifies them.
7. If repair would force a duplicate transition, return `"operations": []` with `metadata.rationale` and `abstain: true`.
8. Output JSON only (no markdown fences).

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

### Campaign runners

The flag is propagated end-to-end:

| Runner | CLI | Summary field |
|--------|-----|---------------|
| [`run_pilot_campaign.py`](../scripts/run_pilot_campaign.py) | `--prompt-variant` | `campaign_summary.json` → `prompt_variant` |
| [`run_diagnostic_granularity_pilot.py`](../scripts/run_diagnostic_granularity_pilot.py) | `--prompt-variant` | `diagnostic_granularity_summary.json` → `prompt_variant` |

Both pass `prompt_variant` into [`generate_patch_ollama.py`](../scripts/generate_patch_ollama.py). Omitting `--prompt-variant` keeps **`default`** behaviour unchanged from earlier pilots.

## Analysis

Pair operation-aware prompting with [`analyze_patch_failures.py`](../scripts/analyze_patch_failures.py) on granularity pilot outputs to compare `duplicate_transition` and related failure classes between campaigns.

## See also

- [`repair_prompt_protocol.md`](repair_prompt_protocol.md)
- [`patch_failure_analysis.md`](patch_failure_analysis.md)
- [`patch_language.md`](patch_language.md)
