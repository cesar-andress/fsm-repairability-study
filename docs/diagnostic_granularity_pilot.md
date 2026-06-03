# Diagnostic granularity pilot

Evaluate whether **repair effectiveness depends on diagnostic granularity** when the repair cases, local model, and iteration budget are held constant.

Implemented by [`scripts/run_diagnostic_granularity_pilot.py`](../scripts/run_diagnostic_granularity_pilot.py).

This is **not** a model benchmark and **not** a multi-model comparison study.

## Experimental factors

| Label | `repair_condition` | Diagnostic level |
|-------|-------------------|------------------|
| **C** | `patch_binary_feedback` | `binary` |
| **D** | `patch_trace_feedback` | `trace` |
| **E** | `patch_localized_feedback` | `localized` |

**Held constant per run:**

- Repair case corpus (`--cases-dir`)
- Ollama model tag (`--model`)
- Iteration budget (`--iteration-budget`, default **1** — one generate/apply/score cycle per condition)
- Prompt template set (`--prompt-variant`, default **`default`**)

**Independent variable:** diagnostic granularity (via prompt template + projected diagnostic).

**Dependent variables:** validation BPR after repair (ΔBPR vs case entry), complete repair, regression.

## CLI

```bash
python scripts/run_diagnostic_granularity_pilot.py \
  --cases-dir datasets/pilot_repair_cases \
  --model llama3:8b \
  --max-cases 5 \
  --output-dir results/diagnostic_granularity_pilot
```

Requires Python 3.12+, Ollama, and populated repair cases (see [`repair_candidate_selection.md`](repair_candidate_selection.md)).

### Prompt variant

```bash
python scripts/run_diagnostic_granularity_pilot.py \
  --cases-dir datasets/pilot_repair_cases \
  --model llama3:8b \
  --max-cases 10 \
  --output-dir results/diagnostic_granularity_pilot_oa \
  --prompt-variant operation-aware
```

| `--prompt-variant` (requested) | Effective variant per label |
|--------------------------------|-----------------------------|
| `default` | C, D, E → `default` |
| `operation-aware` | C, D, E → `operation-aware` |
| `operation-inferred` | C, D → `default`; **E only** → `operation-inferred` |

Dispatch is implemented in [`resolve_prompt_variant_for_condition()`](../scripts/generate_patch_ollama.py) so conditions C and D never receive operation-inferred templates (which require localized diagnostic feedback and only exist for E).

`diagnostic_granularity_summary.json` records:

- `prompt_variant` — same as `prompt_variant_requested` (backward compatible)
- `prompt_variant_requested` — CLI value
- `prompt_variant_by_condition` — map `C` / `D` / `E` → effective variant

Example for `--prompt-variant operation-inferred`:

```json
{
  "prompt_variant_requested": "operation-inferred",
  "prompt_variant_by_condition": {
    "C": "default",
    "D": "default",
    "E": "operation-inferred"
  }
}
```

See [`operation_aware_prompting.md`](operation_aware_prompting.md), [`operation_inferred_prompting.md`](operation_inferred_prompting.md).

## Outputs

| File | Content |
|------|---------|
| `diagnostic_granularity_results.csv` | One row per **attempted** case (including failures) |
| `diagnostic_granularity_summary.json` | Aggregate metrics and failure counts per condition |
| `runs/<case_id>/<C\|D\|E>/` | Per-condition work directory (flat; no nested `<case_id>`) |
| `runs/<case_id>/<C\|D\|E>/error.txt` | Stable error text when that case–condition run failed |

## Output layout

Each case–condition run writes directly under `runs/<case_id>/<C|D|E>/`:

```text
runs/<case_id>/C/
  prep/                 # initial scores, diagnostic
  ollama/               # prompt, raw response, patch.json
  run/                  # apply/score iteration artefacts
  repair_run.json       # frozen repair record
  error.txt             # present only on failure
```

There is **no** second `runs/<case_id>/<condition>/<case_id>/` nesting. This matches manual inspection: one folder per condition label for that case.

## Attempted versus evaluated cases

For each condition label (C, D, E):

| Summary field | Meaning |
|---------------|---------|
| `cases_attempted` | Repair cases for which the pilot **started** that condition (one attempt per case in the CSV) |
| `cases_evaluated` | Case–condition runs that completed scoring with `status == ok` and a usable ΔBPR |
| `cases_failed` | Case–condition runs that failed before a successful evaluation |

**Every attempted case appears exactly once in the CSV**, even when one or more conditions failed. Use per-condition `status_*`, `error_*`, and `error.txt` to diagnose partial completion.

**Do not interpret `cases_evaluated == 0` as zero repairability.** It means no case–condition pair finished the pipeline successfully for that label (for example patch generation, diagnostic projection, or apply/score errors). Compare `cases_failed` and the failure category counters before drawing scientific conclusions about granularity.

## Failure categories (summary JSON)

Per condition, the summary also reports:

| Field | Typical cause |
|-------|----------------|
| `invalid_patch_count` | Model output or patch JSON failed schema/validation |
| `patch_application_failure_count` | Patch engine could not apply operations |
| `generation_failure_count` | Ollama or prompt/patch generation failed |
| `scoring_failure_count` | Scoring or diagnostic projection failed |
| `runner_failure_count` | Other runner/case/pipeline errors |

**Invalid patches** and **generation failures** are part of the empirical outcome, not missing data: they measure whether richer diagnostics change model compliance or operational failure rates, not only mean ΔBPR on successful repairs.

Failures are **scientifically meaningful**: they show whether richer diagnostics (D, E) increase operational cost (more generation surface) or expose schema/projection constraints, independent of mean ΔBPR on succeeded runs only.

The pilot **continues** after a failed case–condition pair: remaining conditions for the same case and remaining cases in the corpus still run.

## `diagnostic_granularity_results.csv`

| Column group | Meaning |
|--------------|---------|
| `case_id`, `initial_bpr` | Case identity and entry validation BPR |
| `status_C` / `_D` / `_E` | Terminal status (see below) |
| `error_C` / `_D` / `_E` | Error message when failed (empty when ok) |
| `patch_valid_*`, `patch_applied_*` | From `repair_run` iteration when available (`true` / `false` / empty) |
| `outcome_*` | `outcome_class` from `repair_run` when evaluated |
| `final_bpr_*`, `delta_*` | Post-repair metrics (empty when not evaluated) |
| `best_condition` | Label(s) with highest ΔBPR among **evaluated** conditions |

### `status_*` values

| Status | Meaning |
|--------|---------|
| `ok` | Pipeline completed; ΔBPR and outcome fields populated |
| `generation_error` | Ollama or patch generation failed |
| `invalid_patch` | Patch JSON failed schema/validation |
| `patch_application_error` | Patch engine could not apply operations |
| `scoring_error` | Scoring or diagnostic projection failed |
| `runner_error` | Other case/runner/pipeline error |
| `skipped` | Condition not run (e.g. unsupported iteration budget) |

When status is not `ok`, `error_*` and `runs/.../error.txt` carry the message; BPR/delta columns stay empty.

## Summary (`per_condition` in JSON)

For each of C, D, E:

| Metric | Definition |
|--------|------------|
| `cases_attempted` | Number of case rows in the CSV |
| `cases_evaluated` | Successful evaluations (denominator for rates below) |
| `cases_failed` | Failed case–condition runs |
| `invalid_patch_count` | Patch JSON failed validation |
| `patch_application_failure_count` | Patch engine apply errors |
| `generation_failure_count` | Ollama or patch generation errors |
| `scoring_failure_count` | Scoring or diagnostic projection errors |
| `runner_failure_count` | Other runner/pipeline errors |
| `mean_delta_bpr` | Mean validation ΔBPR over **evaluated** runs only |
| `complete_repair_rate` | Fraction with `final_bpr_validation == 1` (evaluated only) |
| `regression_rate` | Fraction with behavioural degradation flags (evaluated only) |

## Interpretation

- Compare **evaluated** rates (mean ΔBPR, complete repair) only when `cases_evaluated` is sufficient; always report attempted/failed counts alongside.
- If mean ΔBPR increases C → D → E on evaluated runs, richer diagnostics may help under this protocol.
- If **D** has `cases_evaluated == 0` while C/E succeed, investigate `error_D` and `scoring_failure_count` before comparing granularity — likely infrastructure or projection, not repairability.
- **Regression rate** applies to evaluated runs only; pair with failure categories for harm from invalid or non-applied patches.

Published claims require the frozen CSV, summary JSON, and run artefacts cited by case and condition.

## Pipeline (per case × condition)

Same as [`pilot_campaign.md`](pilot_campaign.md): score → diagnostic → Ollama patch → apply → score → `repair_run`.

## Limitations

- Single iteration per condition in this pilot wiring.
- Same oracle suite often used for feedback and validation in extracted pilot cases.
- Ollama stochasticity remains; use low temperature and document model digest in run artefacts for repeats.

## See also

- [`repair_prompt_protocol.md`](repair_prompt_protocol.md)
- [`diagnostic_model.md`](diagnostic_model.md)
- [`diagnostic_generation.md`](diagnostic_generation.md)
- [`study_design.md`](study_design.md)
