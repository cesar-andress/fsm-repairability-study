# Pilot repair campaign

Small-scale repairability study over multiple repair cases: one **condition**, one **Ollama model**, full pipeline per case. Implemented by [`scripts/run_pilot_campaign.py`](../scripts/run_pilot_campaign.py).

This runner is for **pilot studies** only. It does not compare models, produce plots, or run large-scale batch infrastructure.

## Pipeline (per case)

```text
candidate FSM
  → score (validation + feedback)
  → diagnostic (from feedback score)
  → prompt + Ollama
  → patch.json
  → apply patch + score
  → repair_run.json
```

Stages use existing scripts as libraries:

| Stage | Module |
|-------|--------|
| Score | [`score_repair.py`](../scripts/score_repair.py) |
| Diagnostic | [`build_diagnostic.py`](../scripts/build_diagnostic.py) |
| Ollama patch | [`generate_patch_ollama.py`](../scripts/generate_patch_ollama.py) |
| Apply + record | [`run_repair_condition.py`](../scripts/run_repair_condition.py) (dry-run with generated patch) |

## Case layout

`--cases-dir` may be:

- A **single case directory** containing `case.json`, FSMs, and oracle suite files (e.g. [`tests/fixtures/dry_run_case`](../tests/fixtures/dry_run_case)), or
- A **parent directory** whose immediate subdirectories each contain `case.json`.

Planned production layout: [`datasets/repair_cases/`](../datasets/repair_cases/).

## CLI

```bash
python scripts/run_pilot_campaign.py \
  --cases-dir tests/fixtures/dry_run_case \
  --condition patch_trace_feedback \
  --model llama3:8b \
  --max-cases 1 \
  --output-dir /tmp/pilot_campaign
```

| Flag | Role |
|------|------|
| `--cases-dir` | Root of repair case(s) |
| `--condition` | `patch_binary_feedback`, `patch_trace_feedback`, or `patch_localized_feedback` |
| `--model` | Single Ollama model tag (no multi-model comparison) |
| `--max-cases` | Cap on number of cases processed |
| `--output-dir` | Campaign root for summary, CSV, and per-case artefacts |
| `--ollama-url` | Default `http://127.0.0.1:11434` |
| `--temperature` | Default `0.0` |
| `--prompt-variant` | `default`, `operation-aware`, or `operation-inferred` (localized only); default is `default` |

Omitting `--prompt-variant` uses the original frozen prompts (backward compatible). For the second pilot campaign, pass `--prompt-variant operation-aware` or `operation-inferred` (see [`operation_aware_prompting.md`](operation_aware_prompting.md), [`operation_inferred_prompting.md`](operation_inferred_prompting.md)).

**Python 3.12+** and a running Ollama instance with the model pulled are required.

## Per-case output tree

```text
<output-dir>/<case_id>/
  prep/           # initial scores, diagnostic, requirement.txt
  ollama/         # prompt.txt, raw_response.txt, patch.json
  run/            # dry-run work tree (candidates, scores, diagnostics)
  repair_run.json
```

## Campaign outputs

| File | Content |
|------|---------|
| `campaign_summary.json` | Aggregate metrics and metadata |
| `campaign_results.csv` | One row per case |

### CSV columns

| Column | Meaning |
|--------|---------|
| `case_id` | Repair case identifier |
| `initial_bpr` | Validation BPR before repair |
| `final_bpr` | Validation BPR after repair (`repair_run` outcome) |
| `delta_bpr` | `final_bpr - initial_bpr` |
| `repaired` | `true` if effective or complete repair on validation |
| `complete_repair` | `true` if `final_bpr == 1` |
| `iterations` | Count of `repair_run.iterations` |
| `patch_operations` | Sum of applied patch operations |
| `status` | `ok` or `failed` |
| `error` | Error message when `status=failed` |

Top-level summary fields also include `condition`, `model`, `prompt_variant`, `cases_attempted`, and timestamps.

### Summary metrics (`campaign_summary.json` → `metrics`)

| Metric | Definition |
|--------|------------|
| `repair_rate` | Share of **succeeded** cases with `repaired=true` |
| `complete_repair_rate` | Share of succeeded cases with `complete_repair=true` |
| `mean_delta_bpr` | Mean validation ΔBPR over succeeded cases |
| `median_delta_bpr` | Median validation ΔBPR over succeeded cases |
| `regressions` | Succeeded cases with behavioural degradation / regression flags |
| `failures` | Cases that did not complete the pipeline |

Rates use **succeeded** cases as the denominator (not attempted cases with failures).

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | All cases succeeded |
| `1` | One or more case failures (summary and CSV still written) |
| `2` | Campaign setup error (invalid paths, no cases, bad flags) |

## Prerequisites

1. Repair cases with `inputs.requirement_text` and oracle bindings resolvable from the case directory.
2. Ollama healthy (`curl -s http://127.0.0.1:11434/api/tags`).
3. See [`ollama_backend.md`](ollama_backend.md) and [`repair_condition_runner.md`](repair_condition_runner.md).

## Limitations

- Single model per invocation (no model comparison).
- Single iteration per case (one Ollama call + one apply/score cycle).
- `repair_run` records `execution_backend: "none"` (patch provenance in `ollama/` folder).
- No plots or statistical tests.

## See also

- [`study_design.md`](study_design.md)
- [`experimental_setup.md`](experimental_setup.md)
