# Experimental setup

## Workstation (study execution)

Experiments are designed to run on a **local workstation** with:

- NVIDIA RTX 4090 (or equivalent) for accelerated local inference
- [Ollama](https://ollama.com/) serving one or more **local** models

This setup supports reproducible, large-scale campaigns **without cloud APIs**. Model weights and tags are recorded at artifact freeze.

## Independent variables and controls

| Factor | Role in study |
|--------|----------------|
| **Repair condition** | **Primary independent variable** — see `environment/conditions.yaml` |
| **LLM model (Ollama)** | **Experimental engine / sensitivity factor** — not the main contribution |
| Attempt budget | Protocol control per condition |
| Case id | Unit of analysis |

### Repair conditions (primary IV)

1. `baseline_no_repair` — oracle score only; no LLM
2. `baseline_full_regeneration` — full FSM regeneration from task spec; no patch loop
3. `patch_binary_feedback` — structured patch repair, binary oracle feedback
4. `patch_trace_feedback` — patch repair with failing trace feedback
5. `patch_localized_feedback` — patch repair with localized diagnostic feedback

Cross-condition contrasts support claims about **behavioural repairability under feedback**, not about which model scores highest.

### Model sensitivity (secondary)

- One **primary** Ollama model (`environment/ollama_models.yaml`) carries the main analysis.
- Additional **sensitivity** models repeat a subset of conditions to assess robustness of condition effects.
- Paper tables foreground **condition** contrasts; model-stratified tables are supplementary.

## Execution modes

### Mode A — Audit replication (no GPU, no Ollama)

For reviewers and Zenodo users without the original workstation:

1. Use frozen `results/frozen_runs/` and deposited FSMs/patches
2. Re-run deterministic scripts: `validate_fsm.py`, `apply_patch.py`, `score_repair.py`
3. Recompute aggregates with `scripts/aggregate_results.py` *(planned)*

No LLM invocation is required to verify reported condition-level statistics if runs are frozen.

### Mode B — Local re-execution (Ollama)

Researchers with Ollama installed may re-run conditions:

```bash
python scripts/run_repair_condition.py \
  --case case_01 \
  --condition patch_trace_feedback \
  --model <ollama-model> \
  --ollama-url http://127.0.0.1:11434
```

Outputs are written under a configurable run directory and should match frozen records within documented stochastic tolerance (temperature, seed policy to be fixed at freeze).

Use `--dry-run` to validate CLI and prompts without calling Ollama.

## Configuration files

| File | Purpose |
|------|---------|
| `environment/conditions.yaml` | Canonical condition definitions |
| `environment/ollama_models.yaml` | Ollama URL, primary and sensitivity models |
| `environment/requirements.txt` | Python deps (stdlib HTTP for Ollama; no cloud SDKs) |

## What this repository does not claim

- A leaderboard across many LLMs
- Generalization to cloud-hosted or API-only models
- Mandatory access to an RTX 4090 for **artifact audit**

See [`study_design.md`](study_design.md) and [`../REPRODUCIBILITY.md`](../REPRODUCIBILITY.md).
