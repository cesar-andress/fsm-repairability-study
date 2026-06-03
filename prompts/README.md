# Frozen prompts

Prompt templates for each **repair condition** (primary independent variable). Wording is frozen at artifact release.

## Conditions and prompts

| `condition_id` | Prompt file | Notes |
|----------------|-------------|--------|
| `baseline_no_repair` | *(none)* | No LLM; oracle scoring only |
| `baseline_full_regeneration` | [`baseline_full_regeneration.md`](baseline_full_regeneration.md) | Full FSM from task spec |
| `patch_binary_feedback` | [`repair_binary_feedback.md`](repair_binary_feedback.md) | Pass/fail feedback |
| `patch_binary_feedback` (operation-aware) | [`repair_binary_feedback_operation_aware.md`](repair_binary_feedback_operation_aware.md) | Second pilot: Transition Decision Checklist |
| `patch_trace_feedback` | [`repair_trace_feedback.md`](repair_trace_feedback.md) | Failing trace feedback |
| `patch_trace_feedback` (operation-aware) | [`repair_trace_feedback_operation_aware.md`](repair_trace_feedback_operation_aware.md) | Second pilot: Transition Decision Checklist |
| `patch_localized_feedback` | [`repair_localized_feedback.md`](repair_localized_feedback.md) | Localized diagnostic feedback |
| `patch_localized_feedback` (operation-aware) | [`repair_localized_feedback_operation_aware.md`](repair_localized_feedback_operation_aware.md) | Second pilot: Transition Decision Checklist |
| `patch_localized_feedback` (operation-inferred) | [`repair_localized_feedback_operation_inferred.md`](repair_localized_feedback_operation_inferred.md) | Second pilot: corrections → inferred ops |

Canonical metadata: `environment/conditions.yaml`.

## Models vs conditions

Prompts do **not** encode model choice. The Ollama model is passed at run time (`scripts/run_repair_condition.py --model ...`) and recorded in run metadata. Model comparisons are sensitivity analyses only.

## Replication without Ollama

Published claims should be auditable from `results/frozen_runs/` using deterministic scoring scripts. Re-invoking these prompts via Ollama is optional (see `docs/experimental_setup.md`).

Placeholders use `{{variable}}` syntax; bindings are assembled in `scripts/run_repair_condition.py`.

Controlled repair protocol (conditions C–E): [`docs/repair_prompt_protocol.md`](../docs/repair_prompt_protocol.md).

## Shared snippets

| Snippet | Used in |
|---------|---------|
| [`snippets/transition_decision_checklist.md`](snippets/transition_decision_checklist.md) | All `*_operation_aware.md` templates (C, D, E) |

Edit the snippet first, then sync into the three operation-aware templates before freeze.
