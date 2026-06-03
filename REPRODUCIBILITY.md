# Reproducibility

Two replication modes are supported. Both verify the same scientific object: **behavioural repairability under repair conditions**, not model rankings.

## Release v1.0.0 quick check

Infrastructure-only release **v1.0.0** — confirms schemas, scripts, and tests; does not require Ollama, GPU, or campaign data. Scope: [`ARTIFACT_SCOPE.md`](ARTIFACT_SCOPE.md).

### Test suite

```bash
python -m pytest
```

Requires Python 3.9+ and `pip install -r environment/requirements.txt`.

### Minimal deterministic pipeline (fixtures only)

```bash
mkdir -p tmp/v100_repro_check
python scripts/score_repair.py \
  --fsm tests/fixtures/scoring/fsm_fail_trace.json \
  --oracles tests/fixtures/scoring/oracle_suite.json \
  --output tmp/v100_repro_check/score.json
python scripts/build_diagnostic.py \
  --score-report tmp/v100_repro_check/score.json \
  --level trace \
  --case-id quick_check \
  --run-id v100 \
  --iteration-index 0 \
  --output tmp/v100_repro_check/diagnostic.json
python scripts/apply_patch.py \
  --fsm tests/fixtures/dry_run_case/candidate_fsm.json \
  --patch tests/fixtures/dry_run_case/repair_patch.json \
  -o tmp/v100_repro_check/repaired_fsm.json
```

Optional end-to-end dry-run (orchestrator, no model):

```bash
python scripts/run_repair_condition.py \
  --case-dir tests/fixtures/dry_run_case \
  --condition patch_trace_feedback \
  --patch-source tests/fixtures/dry_run_case/repair_patch.json \
  --work-dir tmp/v100_repro_check/dry_run_work \
  --output-run tmp/v100_repro_check/repair_run.json
```

See [`docs/repair_condition_runner.md`](docs/repair_condition_runner.md).

## Principles

1. **Frozen inputs** — Cases, oracles, prompts, and completed runs are versioned files.
2. **Local inference only** — Study execution uses Ollama on the researcher workstation; no cloud API keys in this repository.
3. **Condition-first analysis** — Scripts parameterize on `condition_id` (primary IV); `model` is an engine label for sensitivity.
4. **Deterministic audit path** — Scoring, validation, and patch application do not require Ollama or a GPU.
5. **Small artifact** — Raw campaign logs stay outside the repo; Zenodo carries frozen runs and aggregates.

## Mode A — Audit replication (no Ollama, no GPU)

For reviewers and machines without the original RTX 4090 setup.

### 1. Environment

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r environment/requirements.txt
pytest tests/ -q
```

### 2. Validate and re-score

```bash
python scripts/validate_fsm.py -i datasets/repair_cases/<case_id>/initial_fsm.json
python scripts/score_repair.py \
  --fsm datasets/repair_cases/<case_id>/initial_fsm.json \
  --oracle-suite datasets/oracle_suites/<suite_id>.json
```

### 3. Load frozen runs

```bash
python scripts/run_repair_condition.py \
  --case <case_id> \
  --condition patch_trace_feedback \
  --model <model_label> \
  --offline
```

Compare outputs under `results/frozen_runs/` and recomputed aggregates in `results/summary/` *(at release)*.

This mode is sufficient to verify **condition-level** claims reported in the paper if runs and summary tables are deposited.

## Mode B — Local re-execution (Ollama)

For researchers repeating experiments on a compatible workstation.

### 1. Configure

Edit `environment/ollama_models.yaml` (primary and sensitivity models) and confirm Ollama is running:

```bash
curl -s http://127.0.0.1:11434/api/tags
```

### 2. Run a condition

```bash
python scripts/run_repair_condition.py \
  --case <case_id> \
  --condition patch_localized_feedback \
  --model <ollama-model-from-config>
```

Use `--dry-run` to validate prompt assembly without inference.

### 3. Deterministic baseline (no LLM)

```bash
python scripts/run_repair_condition.py --case <case_id> --condition baseline_no_repair
```

### 4. Patch loop *(planned)*

Full patch–score–feedback loops will chain `apply_patch.py`, `score_repair.py`, and `run_repair_condition.py`. Until implemented, deposit completed runs under `results/frozen_runs/`.

## Repair conditions (primary IV)

| `condition_id` | Requires Ollama |
|------------------|-----------------|
| `baseline_no_repair` | No |
| `baseline_full_regeneration` | Yes |
| `patch_binary_feedback` | Yes |
| `patch_trace_feedback` | Yes |
| `patch_localized_feedback` | Yes |

Definitions: `environment/conditions.yaml`. Design: `docs/study_design.md`.

## Model sensitivity (secondary)

Repeat a **subset** of conditions across `sensitivity_models` in `ollama_models.yaml`. Report as robustness; do not frame as a leaderboard.

## Component status

| Component | Audit mode | Ollama mode |
|-----------|------------|-------------|
| `validate_fsm.py` | Yes | Yes |
| `score_repair.py` | Yes | Yes |
| `apply_patch.py` | Yes | Yes |
| `ollama_client.py` | N/A | Yes |
| `run_repair_condition.py` | `--offline`, `baseline_no_repair` | Partial (generate stub) |
| Datasets / frozen runs | At release | At release |

## Reporting issues

Cite artifact version (`CITATION.cff`), `case_id`, `condition_id`, optional `model_label`, command line, and file hashes from `results/MANIFEST.md` *(at release)*.
