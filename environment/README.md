# Environment

**Python 3.12 or newer is required.** Local **Ollama** is used on the study workstation for LLM-invoking conditions; audit replication does not require it.

## Setup

```bash
cd /path/to/fsm-repairability-study
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r environment/requirements.txt
python -m pytest
```

## Configuration

| File | Purpose |
|------|---------|
| [`requirements.txt`](requirements.txt) | Python packages (`jsonschema`, `PyYAML`, `pytest`) |
| [`conditions.yaml`](conditions.yaml) | Repair conditions — **primary IV** |
| [`ollama_models.yaml`](ollama_models.yaml) | Ollama URL, primary model, sensitivity models |

## Ollama (study workstation)

1. Install Ollama and pull models listed in `ollama_models.yaml`.
2. Confirm: `curl http://127.0.0.1:11434/api/tags`
3. Run conditions with `scripts/run_repair_condition.py`.

See [`docs/local_model_execution.md`](../docs/local_model_execution.md) for architecture, GPU usage, logging, and reproducibility.

Record exact model tags and Ollama version in `results/MANIFEST.md` at freeze.

## Without GPU / Ollama

Use `--offline` and frozen files under `results/frozen_runs/`. Deterministic scripts remain sufficient for artifact audit.
