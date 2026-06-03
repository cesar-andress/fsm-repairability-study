# Data statement

This document states what will and will not be included in the Zenodo (or equivalent) publication bundle associated with this study.

## Will be included (at release)

- **Repair cases** — A curated set of structurally valid, behaviourally incorrect LLM-generated FSMs, each with documented metadata sufficient to interpret the case without rerunning generation campaigns.
- **Oracle suites** — Frozen behavioural oracle definitions (inputs, expected observations, or equivalent specifications) used to evaluate repair success.
- **Frozen prompts** — Exact prompt templates per repair condition under `prompts/`, with canonical ids in `environment/conditions.yaml`.
- **Frozen repair runs** — Completed case × condition (× model for sensitivity) records under `results/frozen_runs/` for audit without Ollama.
- **Environment metadata** — Ollama model tags and versions recorded in `results/MANIFEST.md` (not live credentials).
- **Aggregated results** — Tables and machine-readable summaries needed to reproduce paper claims (repair rates, attempt counts, condition contrasts), not raw model transcripts unless essential for audit.
- **Schemas and scripts** — JSON schemas and minimal Python tooling to validate FSMs, apply patches, and score outcomes locally.

## Will not be included

- **Private research workspace material** — Manuscript drafts, reviewer correspondence, exploratory notes (see `paper/` outside this repo).
- **Full generation campaigns** — Complete logs of initial FSM generation, model routing, or hyperparameter sweeps.
- **Intermediate experiments** — Discarded cases, failed structural candidates, or ablations not reported in the paper.
- **Proprietary or licensed third-party content** — Any task specification or oracle source that cannot be redistributed; such items will be replaced by summaries or public substitutes.
- **Live API credentials or replayable API keys** — No cloud LLM APIs; optional local Ollama re-execution is not required for audit.
- **Mandatory GPU or original workstation** — Audit replication uses frozen runs; RTX 4090/Ollama only needed for optional re-execution.
- **Large binary blobs** — Raw embeddings, checkpoints, or full conversation dumps unless a specific subset is required for a reported claim (kept minimal).

## Data minimization rationale

The scientific contribution concerns **behavioural repairability under stated conditions**, not maximal model coverage. The artifact therefore prioritizes:

1. Enough frozen context to interpret each repair case
2. Enough tooling to verify structural and behavioural claims locally
3. Small, stable files suitable for long-term archival

## Placeholder status

Directories under `datasets/` and `results/` currently contain README placeholders only. Final file lists and checksums will be added in the release checklist.

## Ethics and privacy

No human subjects data are anticipated. If task specifications are derived from real systems, only anonymized or synthetic public variants will be deposited.

## Contact

Update with corresponding author contact before Zenodo release.
