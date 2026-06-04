# Artifact overview — fsm-repairability-study v2.0.0

## Repository purpose

**fsm-repairability-study** is the public software-and-data artifact for empirical studies of **behavioural repairability**: given a structurally valid but behaviourally incorrect finite state machine (FSM) produced by a large language model (LLM), how can repair be evaluated under oracle feedback, deterministic patch gates, and constrained patch languages?

Release **v2.0.0** extends the v1.x **core experimental infrastructure** with:

- **Frozen pilot campaigns** cited by the IST manuscript *A Reproducible Protocol for Evaluating Behavioural FSM Repair with Large Language Models*
- **Analysis and paper-generation scripts** (Tier A: no Ollama required)
- **Documentation** for IST artifact evaluation (see [`ARTIFACT_EVALUATION.md`](ARTIFACT_EVALUATION.md))

The artifact is **not** a model leaderboard or proof of diagnostic superiority. It provides a **reproducible evaluation protocol**, measurement definitions (repair executability vs repair effectiveness), and pilot-scale descriptive evidence.

## Author

| Field | Value |
|-------|--------|
| Name | César Andrés |
| ORCID | [0009-0001-8968-3404](https://orcid.org/0009-0001-8968-3404) |
| Email | cesar.andress@ucjc.edu |

Citation metadata: [`CITATION.cff`](CITATION.cff). License: [MIT](LICENSE).

## Frozen experiments (manuscript evidence base)

Three **separately frozen pilot arms** (30 repair cases × conditions C/D/E = 90 slots per arm). Shared case corpus: `pilot_repair_cases_diverse/` (30 cases).

| Manuscript label | Directory | Prompt variant |
|------------------|-----------|----------------|
| `default` | `freezes/frozen_pilot_001/` | Default patch authoring |
| `operation-aware` | `freezes/diagnostic_granularity_pilot_diverse_operation_aware_001/` | Operation checklist prompts |
| `operation-inferred` | `freezes/frozen_main_pilot_001/` | Inferred corrections on condition E only |

Each pilot root contains:

| File / path | Role |
|-------------|------|
| `diagnostic_granularity_summary.json` | Arm-level executability aggregates (written at campaign completion) |
| `diagnostic_granularity_results.csv` | Per case–condition row log |
| `runs/<case_id>/{C,D,E}/` | Slot artefacts (`repair_run.json`, diagnostics, Ollama outputs where applicable) |
| `analysis/repair_outcome_summary.json` | Behavioural outcome classes on evaluated slots (regeneratable) |
| `analysis/patch_failure_summary.json` | Patch-application failure taxonomy (regeneratable) |

**Paper workspace mirror:** the companion manuscript under `../paper/experiments/` uses the same directory names when Tier A is run from the paper tree.

**Diagnostic conditions:** C = binary feedback, D = trace feedback, E = localized feedback.

## Reproduction workflow

### Tier A — Audit replication (recommended for reviewers)

**Goal:** Regenerate analysis summaries, LaTeX tables, and PDF figures from frozen `runs/` without re-invoking the LLM.

**Requirements:** Python 3.12+, dependencies in `environment/requirements.txt`. No GPU. No Ollama.

**Steps:** See [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md) for exact commands.

Summary:

1. Install Python environment and run `pytest`.
2. Point `PAPER_ROOT` at the manuscript directory containing `experiments/` and `results/main_results_table.csv`.
3. Run `analyze_repair_outcomes.py` and `analyze_patch_failures.py` per pilot (optional refresh of `analysis/`).
4. Run `generate_paper_tables.py` and `generate_paper_figures.py`.
5. Optionally compile `paper/main.tex`.

### Tier B — Full campaign re-execution (optional)

**Goal:** Re-run Ollama-backed repair campaigns. **Will not** reproduce frozen LLM bytes bit-for-bit.

**Requirements:** Ollama, model `qwen2.5-coder:7b`, GPU recommended (see [`ARTIFACT_EVALUATION.md`](ARTIFACT_EVALUATION.md)).

Driver: `scripts/run_diagnostic_granularity_pilot.py` (writes `diagnostic_granularity_summary.json` at campaign end).

## Generated outputs (manuscript)

From `PAPER_ROOT` (companion `paper/` repository):

| Output | Path | Generator |
|--------|------|-----------|
| Main results table | `tables/main_results.tex` | `generate_paper_tables.py` |
| Repair outcomes table | `tables/repair_outcomes.tex` | same |
| Failure analysis table | `tables/failure_analysis.tex` | same |
| Evaluated-slot figure | `figures/evaluated_cases_by_variant.pdf` | `generate_paper_figures.py` |
| Effective-repair ratio figure | `figures/repair_success_rate.pdf` | same |
| Patch-failure figure | `figures/patch_failure_breakdown.pdf` | same |
| Cross-arm CSV | `results/main_results_table.csv` | input to figure script |

Replication bundle: `scripts/package_replication_bundle.py` → `replication_package/` and zip.

## Hardware requirements

| Tier | CPU | RAM | Disk | GPU |
|------|-----|-----|------|-----|
| A (audit) | 2+ cores | 4 GB | ~500 MB–2 GB | Not required |
| B (re-run) | 4+ cores | 16 GB | 10+ GB | NVIDIA ≥16 GB VRAM recommended |

## Software requirements

| Component | Version / notes |
|-----------|-----------------|
| Python | **3.12+** (`pyproject.toml`) |
| pip packages | `environment/requirements.txt` (`jsonschema`, `PyYAML`, `pytest`, `matplotlib`) |
| LaTeX | Optional for manuscript PDF (`pdflatex`, `booktabs`) |
| Ollama | Tier B only; model tag `qwen2.5-coder:7b` |
| Git | Clone and checkout release tag `v2.0.0` |

## Related documents

| Document | Purpose |
|----------|---------|
| [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md) | Exact regeneration commands |
| [`ARTIFACT_EVALUATION.md`](ARTIFACT_EVALUATION.md) | IST reviewer checklist |
| [`ARTIFACT_SCOPE.md`](ARTIFACT_SCOPE.md) | v1.0.0 infrastructure boundary (superseded in part by v2.0.0 notes) |
| [`RELEASE_NOTES_v2.md`](RELEASE_NOTES_v2.md) | v2.0.0 release changelog |
| [`docs/diagnostic_granularity_pilot.md`](docs/diagnostic_granularity_pilot.md) | Pilot design and summary JSON schema |

## Zenodo archival

- **v2.0.0 – IST Artifact Freeze:** [10.5281/zenodo.20517969](https://doi.org/10.5281/zenodo.20517969) (infrastructure + `freezes/`)
- **v1.0.x (superseded for empirical claims):** [10.5281/zenodo.20529518](https://doi.org/10.5281/zenodo.20529518) (infrastructure only)
