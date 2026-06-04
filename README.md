# fsm-repairability-study

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20517969.svg)](https://doi.org/10.5281/zenodo.20517969)

**Reproducible protocol and frozen pilots for evaluating behavioural FSM repair with LLMs.**

## Author

| Field | Value |
|-------|--------|
| Name | César Andrés |
| ORCID | [0009-0001-8968-3404](https://orcid.org/0009-0001-8968-3404) |
| Email | [cesar.andress@ucjc.edu](mailto:cesar.andress@ucjc.edu) |

## Citation and archive

**Zenodo (v2.0.0 – IST Artifact Freeze):** [https://doi.org/10.5281/zenodo.20517969](https://doi.org/10.5281/zenodo.20517969)

**GitHub release:** [v2.0.0](https://github.com/cesar-andress/fsm-repairability-study/releases/tag/v2.0.0)

Recommended citation text: [`docs/citation.md`](docs/citation.md) · machine-readable: [`CITATION.cff`](CITATION.cff)

## Purpose

Public artifact for empirical software engineering studies of **behavioural repairability**: given a structurally valid but behaviourally incorrect finite state machine (FSM) from an LLM, how should repair be **measured** under oracle feedback, deterministic patch gates, and constrained patch languages?

This repository is **not** a model leaderboard. The primary contribution is a **reproducible evaluation protocol** (repair executability vs repair effectiveness on identical slots) plus pilot-scale descriptive evidence.

## Quick links

| Document | Purpose |
|----------|---------|
| [`ARTIFACT_OVERVIEW.md`](ARTIFACT_OVERVIEW.md) | Repository purpose, frozen experiments, requirements |
| [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md) | Exact commands to regenerate JSON summaries, tables, figures |
| [`ARTIFACT_EVALUATION.md`](ARTIFACT_EVALUATION.md) | IST reviewer checklist (Tier A / Tier B) |
| [`RELEASE_NOTES_v2.md`](RELEASE_NOTES_v2.md) | v2.0.0 changelog |

## Repository layout

| Path | Purpose |
|------|---------|
| [`freezes/`](freezes/) | Three frozen pilot arms (manuscript evidence base) |
| [`schemas/`](schemas/) | JSON schemas for FSMs, patches, repair runs, diagnostics |
| [`scripts/`](scripts/) | Scoring, analysis, pilot driver, paper table/figure generators |
| [`prompts/`](prompts/) | Frozen repair prompt templates |
| [`docs/`](docs/) | Study design, pilot protocol, terminology |
| [`environment/`](environment/) | Python dependencies, condition and model config |
| [`tests/`](tests/) | Schema and pipeline smoke tests |

## Requirements

**Python 3.12 or newer** (`pyproject.toml`). See [`ARTIFACT_OVERVIEW.md`](ARTIFACT_OVERVIEW.md) for hardware/software tiers.

## Quick start

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r environment/requirements.txt
python -m pytest
```

**Tier A (no GPU):** regenerate manuscript tables/figures from frozen pilots — [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md)

**Tier B (optional):** re-run Ollama campaigns — [`docs/experimental_setup.md`](docs/experimental_setup.md)

## Frozen pilot arms (v2.0.0)

| Variant | Directory under `freezes/` |
|---------|----------------------------|
| `default` | `frozen_pilot_001/` |
| `operation-aware` | `diagnostic_granularity_pilot_diverse_operation_aware_001/` |
| `operation-inferred` | `frozen_main_pilot_001/` |

30 repair cases × conditions C/D/E per arm. Model: `qwen2.5-coder:7b`. One repair iteration per slot.

## License

[MIT](LICENSE)

## Related workspace

Manuscript sources live in the companion `paper/` directory (IST submission). See [`docs/repository_scope.md`](docs/repository_scope.md).

## Releases

| Version | Scope |
|---------|--------|
| **v2.0.0** | Infrastructure + frozen pilots + Tier A docs — [`RELEASE_NOTES_v2.md`](RELEASE_NOTES_v2.md) |
| v1.0.1 | CITATION.cff metadata fix — [`RELEASE_NOTES_v1.0.1.md`](RELEASE_NOTES_v1.0.1.md) |
| v1.0.0 | Core infrastructure only — [`RELEASE_NOTES_v1.0.0.md`](RELEASE_NOTES_v1.0.0.md), [`ARTIFACT_SCOPE.md`](ARTIFACT_SCOPE.md) |

## Status

**v2.0.0 – IST Artifact Freeze** — published on Zenodo ([10.5281/zenodo.20517969](https://doi.org/10.5281/zenodo.20517969)) with frozen pilots and Tier A documentation.
