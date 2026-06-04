# v2.0.0 — IST Artifact Freeze

**Release date:** 2026-06-04  
**Repository:** [fsm-repairability-study](https://github.com/cesar-andress/fsm-repairability-study)  
**Author:** César Andrés · ORCID [0009-0001-8968-3404](https://orcid.org/0009-0001-8968-3404)

Companion manuscript (Information and Software Technology): *A Reproducible Protocol for Evaluating Behavioural FSM Repair with Large Language Models*.

---

## 1. Overview

Release **v2.0.0 — IST Artifact Freeze** is the archival software-and-data bundle for artifact evaluation and independent replication of the IST repairability protocol study.

Compared with **v1.0.x** (infrastructure only), this release adds:

- Three **frozen pilot campaigns** under `freezes/`
- **Tier A** analysis and manuscript-generation scripts (no GPU, no Ollama)
- Reviewer-oriented documentation ([`ARTIFACT_EVALUATION.md`](ARTIFACT_EVALUATION.md), [`ARTIFACT_OVERVIEW.md`](ARTIFACT_OVERVIEW.md), [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md))

**Recommended for:** IST reviewers (Tier A audit), researchers extending the protocol, and replication users verifying tables and figures from frozen JSON.

**Not included:** manuscript LaTeX sources (companion `paper/` workspace), bit-identical LLM re-execution, or inferential statistics.

---

## 2. Scientific scope

This artifact supports a **measurement and protocol contribution**, not a model benchmark or proof of diagnostic superiority.

| In scope | Out of scope |
|----------|--------------|
| Reproducible protocol for evaluating oracle-gated FSM patch repair with LLMs | New LLM, benchmark, or repair algorithm |
| Joint reporting of **repair executability** (scoring reached) and **repair effectiveness** (validation BPR movement on scored slots) | Causal claims about diagnostic granularity |
| Pilot-scale **descriptive** evidence from three separately frozen arms | Population-level FSM repair effectiveness |
| Patch-failure taxonomies and pipeline terminal counters | Hypothesis tests or confidence intervals |
| Diagnostic conditions C (binary), D (trace), E (localized) | Multi-model leaderboard |

**Pilot scale:** 30 diverse repair cases, model `qwen2.5-coder:7b`, one repair iteration per case–condition slot (90 slots per arm).

**Primary independent variables:** diagnostic feedback shape (within-arm contrasts in the default arm) and repair representation (across separately frozen arms).

---

## 3. Frozen experiments included

All paths relative to repository root.

| Prompt variant | Directory | Notes |
|----------------|-----------|--------|
| `default` | `freezes/frozen_pilot_001/` | Default patch authoring; granularity contrasts C/D/E |
| `operation-aware` | `freezes/diagnostic_granularity_pilot_diverse_operation_aware_001/` | Operation checklist prompts |
| `operation-inferred` | `freezes/frozen_main_pilot_001/` | Inferred corrections on condition E only |

Each pilot directory contains:

- `diagnostic_granularity_summary.json` — arm-level executability aggregates (campaign freeze)
- `diagnostic_granularity_results.csv` — per slot row log
- `runs/<case_id>/{C,D,E}/` — slot artefacts (`repair_run.json`, diagnostics, model outputs)
- `analysis/repair_outcome_summary.json` — behavioural outcome classes (Tier A regeneratable)
- `analysis/patch_failure_summary.json` — patch-application failure taxonomy (Tier A regeneratable)

Shared repair case corpus (30 cases): shipped with the companion paper tree as `experiments/pilot_repair_cases_diverse/` when using the full submission bundle.

---

## 4. Reproduction workflow

Two tiers are documented; **Tier A is sufficient for IST artifact evaluation**.

### Tier A — Audit replication (recommended)

**Goal:** Regenerate analysis summaries, LaTeX tables, and PDF figures from frozen `runs/` **without** re-invoking the LLM.

| Requirement | Detail |
|-------------|--------|
| Python | 3.12+ |
| GPU / Ollama | Not required |
| Time | ~15–30 minutes |
| Companion path | `PAPER_ROOT` → manuscript directory with `experiments/` and `results/main_results_table.csv` |

**Steps:**

1. Create virtual environment; install `environment/requirements.txt`; run `pytest`.
2. Optionally refresh per-pilot analysis JSON with `analyze_repair_outcomes.py` and `analyze_patch_failures.py`.
3. Run `generate_paper_tables.py` and `generate_paper_figures.py` against `PAPER_ROOT`.
4. Optionally compile `paper/main.tex`.

Full command blocks: [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md).

### Tier B — Full campaign re-execution (optional)

**Goal:** Re-run Ollama-backed campaigns via `run_diagnostic_granularity_pilot.py`.

**Warning:** LLM completions will **not** match the freeze byte-for-bit. Use for sensitivity exploration only, not for verifying submission numbers.

Requires Ollama, model `qwen2.5-coder:7b`, and GPU as described in [`ARTIFACT_EVALUATION.md`](ARTIFACT_EVALUATION.md).

---

## 5. Main generated artifacts

When Tier A is run with the companion paper workspace (`PAPER_ROOT`):

| Manuscript output | Path under `PAPER_ROOT` | Generator |
|-------------------|-------------------------|-----------|
| Main results table | `tables/main_results.tex` | `generate_paper_tables.py` |
| Repair outcomes table | `tables/repair_outcomes.tex` | same |
| Failure analysis table | `tables/failure_analysis.tex` | same |
| Evaluated-slot figure | `figures/evaluated_cases_by_variant.pdf` | `generate_paper_figures.py` |
| Effective-repair ratio figure | `figures/repair_success_rate.pdf` | same |
| Patch-failure figure | `figures/patch_failure_breakdown.pdf` | same |

**Intermediate JSON (regeneratable from frozen `runs/`):**

| Summary | Script |
|---------|--------|
| `repair_outcome_summary.json` | `analyze_repair_outcomes.py` |
| `patch_failure_summary.json` | `analyze_patch_failures.py` |
| `diagnostic_granularity_summary.json` | Written at campaign time by `run_diagnostic_granularity_pilot.py` (read-only in Tier A) |

Optional bundle: `package_replication_bundle.py` → `replication_package/` and zip.

---

## 6. Replication instructions

### Layout

```text
ist2026b/
├── fsm-repairability-study/    ← this repository (REPO_ROOT)
└── paper/                      ← manuscript + experiments mirror (PAPER_ROOT)
```

### Quick start (Tier A)

```bash
export REPO_ROOT="/path/to/fsm-repairability-study"
export PAPER_ROOT="/path/to/ist2026b/paper"

cd "$REPO_ROOT"
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r environment/requirements.txt
python -m pytest
```

### Regenerate all manuscript tables and figures

```bash
for PILOT in frozen_pilot_001 \
  diagnostic_granularity_pilot_diverse_operation_aware_001 \
  frozen_main_pilot_001; do
  python scripts/analyze_repair_outcomes.py \
    --pilot-dir "$PAPER_ROOT/experiments/$PILOT"
  python scripts/analyze_patch_failures.py \
    --pilot-dir "$PAPER_ROOT/experiments/$PILOT"
done

python scripts/generate_paper_tables.py --paper-root "$PAPER_ROOT"
python scripts/generate_paper_figures.py --paper-root "$PAPER_ROOT"
```

### Verify frozen inputs exist

```bash
for PILOT in frozen_pilot_001 \
  diagnostic_granularity_pilot_diverse_operation_aware_001 \
  frozen_main_pilot_001; do
  test -f "$PAPER_ROOT/experiments/$PILOT/diagnostic_granularity_summary.json" \
    || echo "MISSING: $PILOT"
done
test -f "$PAPER_ROOT/results/main_results_table.csv" \
  || echo "MISSING: main_results_table.csv"
```

Equivalent frozen bundles are also available under `$REPO_ROOT/freezes/` when the paper mirror is not used.

**Reviewer checklist:** [`ARTIFACT_EVALUATION.md`](ARTIFACT_EVALUATION.md)

---

## 7. Citation information

**Author:** César Andrés  
**ORCID:** https://orcid.org/0009-0001-8968-3404  
**Email:** cesar.andress@ucjc.edu  
**License:** MIT ([`LICENSE`](LICENSE))

**Machine-readable metadata:** [`CITATION.cff`](CITATION.cff) (version `2.0.0`)

**Zenodo:**

| Release | Scope | DOI |
|---------|--------|-----|
| **v2.0.0 – IST Artifact Freeze** | Infrastructure + frozen pilot campaigns | [10.5281/zenodo.20517969](https://doi.org/10.5281/zenodo.20517969) |
| v1.0.x | Core infrastructure only (superseded for empirical claims) | [10.5281/zenodo.20529518](https://doi.org/10.5281/zenodo.20529518) |

Human-readable citation guidance: [`docs/citation.md`](docs/citation.md)

**Suggested acknowledgment for reviewers:**

> We used fsm-repairability-study v2.0.0 (IST artifact freeze) to regenerate manuscript tables and figures from frozen pilot JSON under Tier A.

---

## 8. No scientific changes after freeze

This release tag marks a **fixed empirical snapshot** for IST submission and artifact evaluation.

**Frozen and unchanged after the freeze date:**

- All files under `freezes/*/runs/`
- Campaign-level `diagnostic_granularity_summary.json` and `diagnostic_granularity_results.csv` in each pilot
- Numerical cell values in manuscript tables derived from the freeze
- Descriptive claims reported in the companion paper

**May differ without changing scientific content:**

- Auto-generated LaTeX comment timestamps in `tables/*.tex` after Tier A re-run
- Documentation and citation metadata updates between GitHub tag and Zenodo deposit

**Explicitly not re-run for this release:**

- Ollama inference (Tier B)
- Re-scoring or patch application logic changes that would alter frozen aggregates

If a post-freeze erratum is ever required, it will be released under a **new version tag** with an documented changelog; v2.0.0 remains the IST submission baseline.

---

## Related documentation

| Document | Purpose |
|----------|---------|
| [`ARTIFACT_OVERVIEW.md`](ARTIFACT_OVERVIEW.md) | Repository purpose and requirements |
| [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md) | Complete command reference |
| [`ARTIFACT_EVALUATION.md`](ARTIFACT_EVALUATION.md) | IST reviewer evaluation guide |
| [`RELEASE_NOTES_v2.md`](RELEASE_NOTES_v2.md) | Maintainer publication checklist |

**Previous releases:** [`RELEASE_NOTES_v1.0.0.md`](RELEASE_NOTES_v1.0.0.md), [`RELEASE_NOTES_v1.0.1.md`](RELEASE_NOTES_v1.0.1.md)
