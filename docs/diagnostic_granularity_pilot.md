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

## Outputs

| File | Content |
|------|---------|
| `diagnostic_granularity_results.csv` | One row per case, columns C/D/E |
| `diagnostic_granularity_summary.json` | Aggregate metrics per condition |
| `runs/<case_id>/<C\|D\|E>/` | Per-condition pilot artefacts (prompt, patch, `repair_run.json`) |

### `diagnostic_granularity_results.csv`

| Column | Meaning |
|--------|---------|
| `case_id` | Repair case |
| `initial_bpr` | Validation BPR before repair (same candidate across C/D/E) |
| `final_bpr_C` / `_D` / `_E` | Validation BPR after repair under each condition |
| `delta_C` / `_D` / `_E` | Final − initial validation BPR |
| `best_condition` | Label(s) with highest ΔBPR (`C`, `D`, `E`, or tie e.g. `C+D`) |

### Summary (`per_condition` in JSON)

For each of C, D, E:

| Metric | Definition |
|--------|------------|
| `mean_delta_bpr` | Mean validation ΔBPR over succeeded case–condition runs |
| `complete_repair_rate` | Fraction with `final_bpr_validation == 1` |
| `regression_rate` | Fraction with behavioural degradation / regression flags |

Denominator: cases where that condition completed successfully.

## Interpretation

- If **mean ΔBPR** or **complete repair rate** increases monotonically C → D → E, richer diagnostics may improve repairability under the pilot protocol.
- Flat curves suggest granularity may not matter for the sampled cases/model within one iteration.
- **Regression rate** captures harm from incorrect patches; compare across conditions alongside success rates.

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
- [`study_design.md`](study_design.md)
