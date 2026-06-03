# Behavioural Repairability of LLM-Generated Finite State Machines

Replication artifact for an empirical software engineering study of **behavioural repairability**: given a structurally valid but behaviourally incorrect finite state machine (FSM) produced by a large language model (LLM), can it be repaired using feedback from behavioural oracles, and under which conditions?

This repository is **not** a general LLM benchmark or model leaderboard. The **primary independent variable** is the repair condition (baselines vs patch repair with different oracle feedback). Local Ollama models on the study workstation (e.g. RTX 4090) are **experimental engines** for sensitivity analysis, not the main contribution.

## Repository layout

| Path | Purpose |
|------|---------|
| [`docs/`](docs/) | Study design, terminology, diagnostic model, and scope documentation |
| [`schemas/`](schemas/) | JSON schemas for FSMs, patches, repair cases, repair runs, and oracle diagnostics |
| [`datasets/`](datasets/) | Frozen repair cases and oracle suites (added at release) |
| [`prompts/`](prompts/) | Frozen prompts per repair condition (primary IV) |
| [`scripts/`](scripts/) | Validation, scoring, and local Ollama execution helpers |
| [`environment/`](environment/) | `conditions.yaml`, `ollama_models.yaml`, Python deps |
| [`results/`](results/) | Aggregated study outputs (added at release) |
| [`environment/`](environment/) | Python dependencies for replication |
| [`tests/`](tests/) | Smoke tests for schemas and core script behaviour |

## Requirements

**Python 3.12 or newer is required.** See [`pyproject.toml`](pyproject.toml) (`requires-python = ">=3.12"`).

## Quick start (skeleton)

```bash
python3.12 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r environment/requirements.txt
python -m pytest
python scripts/validate_fsm.py --help
python scripts/run_repair_condition.py --help
```

- **Audit replication (no GPU):** frozen runs + deterministic scripts — [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md)
- **Local re-execution:** Ollama on study workstation — [`docs/experimental_setup.md`](docs/experimental_setup.md)

## Citation and license

- Citation metadata: [`CITATION.cff`](CITATION.cff) (placeholder until publication)
- License: [MIT](LICENSE)
- Data scope: [`DATA_STATEMENT.md`](DATA_STATEMENT.md)

## Related workspace

Exploratory research, drafts, and non-public material belong in the private `paper/` workspace, not in this repository. See [`docs/repository_scope.md`](docs/repository_scope.md).

## Release v1.0.0 scope

**v1.0.0 — Core Experimental Infrastructure** is the first stable public release. It ships schemas, deterministic scoring and diagnostics, patch application, controlled prompt templates, dry-run orchestration, tests, and documentation. It does **not** include large-scale campaigns, local model outputs, private experiments, paper drafts, or unpublished empirical results.

Full boundary: [`ARTIFACT_SCOPE.md`](ARTIFACT_SCOPE.md). Release notes: [`RELEASE_NOTES_v1.0.0.md`](RELEASE_NOTES_v1.0.0.md).

## Status

**v1.0.0 (infrastructure).** Core deterministic pipeline and dry-run orchestration are implemented and tested. Large-scale repair campaigns and Ollama-backed patch generation are planned for later releases; see [`ARTIFACT_SCOPE.md`](ARTIFACT_SCOPE.md).
