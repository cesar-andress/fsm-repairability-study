# Release notes — v1.0.0

**Title:** v1.0.0 — Core Experimental Infrastructure  
**Date:** 2026-06-03 (tag when published)

## Overview

This is the **first stable public release** of `fsm-repairability-study`. It packages the experimental **infrastructure** needed to study behavioural repairability of LLM-generated FSMs: artefact schemas, deterministic scoring and diagnostics, constrained patching, controlled prompt templates, dry-run orchestration, tests, and documentation.

This release does **not** report empirical repair outcomes or large-scale experimental results. It enables audit replication of the **machinery** (validate → score → diagnose → apply patch → record run) using minimal synthetic fixtures.

See also: [`ARTIFACT_SCOPE.md`](ARTIFACT_SCOPE.md).

## Included in this release

| Area | Contents |
|------|----------|
| Schemas | Repair case, repair run, diagnostic, patch, FSM, oracle suite (JSON Schema) |
| Scoring | Deterministic scoring interface (`scripts/score_repair.py`, `docs/scoring_interface.md`) |
| Diagnostics | Deterministic projection (`scripts/build_diagnostic.py`, `docs/diagnostic_generation.md`, `docs/diagnostic_model.md`) |
| Patching | Constrained patch application (`scripts/apply_patch.py`, `docs/patch_language.md`) |
| Prompts | Controlled repair prompt templates (`prompts/repair_*_feedback.md`, `docs/repair_prompt_protocol.md`) |
| Orchestration | Dry-run repair condition runner (`scripts/run_repair_condition.py`, `docs/repair_condition_runner.md`) |
| Validation | FSM validation (`scripts/validate_fsm.py`) |
| Tests | Pytest suite with schema, scoring, diagnostic, patch, prompt, and dry-run fixtures |
| Documentation | Study design, experimental setup, repository scope, reproducibility guide |
| Citation | `CITATION.cff` (version 1.0.0; DOI to be added after Zenodo registration) |

## Not included in this release

- Large-scale repair campaign datasets or frozen study runs.
- Local model execution records (Ollama outputs, GPU logs, raw inference traces).
- Empirical repair results or paper-specific summary tables.
- Private campaigns, author notes, or paper drafts.
- Full multi-iteration LLM repair loops (patch **generation** via model is not part of v1.0.0).

## Reproducibility check

From the repository root (**Python 3.12 or newer is required**):

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r environment/requirements.txt
python -m pytest
```

Minimal deterministic pipeline (no Ollama), using checked-in fixtures:

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

Details: [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md).

## Intended Zenodo archive contents

- Full git source tree at tag `v1.0.0` (schemas, `scripts/`, `docs/`, `prompts/`, `environment/`, `tests/`, `LICENSE`, citation and scope files).
- Minimal public fixtures under `tests/fixtures/` (synthetic cases for validation only).
- **Excluded** from the deposit intent: private `paper/` workspace material, campaign logs, model outputs, and any paths listed in [`.gitignore`](.gitignore) as non-publishable.

After upload, update `CITATION.cff` with the Zenodo DOI.

## Known limitations

- **No campaign data** — Cannot reproduce paper-level condition comparisons from this tag alone.
- **No local model execution records** — Ollama integration paths are documented but not required for v1.0.0 verification.
- **No empirical repair results** — BPR improvements in tests use synthetic fixtures only.
- **Guard handling** — Transition guards are only honoured when boolean literals; other guards disable matching (documented in scoring).
- **Examples are minimal** — Fixtures are small synthetic FSMs for schema and pipeline smoke tests, not representative study cases.
- **Patch language v1** — Transition operations only; state-level patch ops are not implemented.
- **README quick start** — Some CLI examples in older docs may refer to planned flags; prefer `docs/repair_condition_runner.md` for dry-run orchestration.

## Next planned release

A subsequent release (e.g. v1.1.0 or v2.0.0) may add:

- Frozen repair campaigns and oracle suites associated with a submitted paper.
- Aggregated `results/` summaries and manifest hashes for audit replication.
- Ollama-backed patch generation behind the same `repair_run` contract.
- Zenodo DOI back-filled in `CITATION.cff`.

Until then, cite **v1.0.0** as the infrastructure baseline, not as evidence of study outcomes.
