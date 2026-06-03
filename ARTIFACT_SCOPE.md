# Artifact scope — release v1.0.0

## What this release provides

Release **v1.0.0** (*Core Experimental Infrastructure*) publishes the **core experimental infrastructure** for behavioural repairability studies of LLM-generated finite state machines (FSMs). It is a stable, citable software artifact: schemas, documentation, deterministic tooling, controlled prompt templates, and automated tests that define how repair cases are represented, scored, diagnosed, patched, and recorded.

Included capabilities:

- **JSON schemas** — repair case, repair run, diagnostic, patch, FSM, and oracle suite contracts.
- **Documentation** — study design, diagnostic model, scoring interface, patch language, prompt protocol, and dry-run orchestration.
- **Deterministic scoring** — `score_repair.py` evaluates a candidate FSM against a behavioural oracle suite and emits a score report (including BPR).
- **Diagnostic projection** — `build_diagnostic.py` maps score reports to levelled diagnostics (`binary`, `trace`, `localized`) without any language model.
- **Constrained patch application** — `apply_patch.py` applies schema-valid transition patches with validation.
- **Controlled repair prompt templates** — frozen markdown templates for repair conditions C–E (placeholders only; no inference in this release).
- **Dry-run repair orchestration** — `run_repair_condition.py` exercises the loop shape using external patch files (no Ollama).
- **Tests** — schema validation, scoring, diagnostics, patches, prompts, and dry-run fixtures.

This release describes **infrastructure**, not empirical findings. It does **not** assert that large-scale repair experiments have been executed or that any particular repair success rate has been measured.

## What this release does not include

The following are **out of scope** for v1.0.0 and must not be expected in the public archive:

- Large-scale repair **campaigns** or batch experiment outputs.
- **Local model outputs** (Ollama or other LLM generations, raw completions, chat logs).
- **Private experiments**, internal notebooks, or unreleased study runs.
- **Paper drafts**, submission materials, or author-only analysis.
- **Raw campaign logs**, GPU-specific traces, or workstation-local scratch directories.
- **Unpublished empirical results** or summary tables tied to a specific publication.

Researchers who need campaign-level evidence should wait for a **future release** that may ship frozen repair campaigns and aggregated results alongside an accepted or submitted paper, with scope documented in that release’s notes.

## Relationship to Zenodo and GitHub

- **GitHub tag `v1.0.0`** — Source tree at the infrastructure milestone; use [`RELEASE_NOTES_v1.0.0.md`](RELEASE_NOTES_v1.0.0.md) and [`CITATION.cff`](CITATION.cff) for metadata.
- **Zenodo deposit** — Intended to archive the same repository snapshot (source + schemas + docs + tests + minimal fixtures). A DOI will be added to `CITATION.cff` after Zenodo assigns one.

## Future releases

Later versions may add:

- Frozen repair cases and oracle suites from a completed study.
- Completed `repair_run` records and summary aggregates cited in a paper.
- Optional Ollama-backed execution paths documented under reproducibility modes.

Each future release will have its own scope statement and release notes; v1.0.0 remains the **infrastructure-only** baseline.
