# Release notes — v2.0.0

**Title:** v2.0.0 — Frozen pilot campaigns and Tier A reproduction bundle  
**Date:** 2026-06-04  
**Author:** César Andrés ([ORCID 0009-0001-8968-3404](https://orcid.org/0009-0001-8968-3404))

## Overview

Release **v2.0.0** is the **archival evaluation artifact** for the IST manuscript *A Reproducible Protocol for Evaluating Behavioural FSM Repair with Large Language Models*.

Compared with **v1.0.x** (infrastructure only), v2.0.0 adds:

- Frozen pilot campaign outputs under [`freezes/`](freezes/)
- Verified Tier A scripts to regenerate manuscript tables and figures
- IST-oriented documentation ([`ARTIFACT_OVERVIEW.md`](ARTIFACT_OVERVIEW.md), [`ARTIFACT_EVALUATION.md`](ARTIFACT_EVALUATION.md), updated [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md))

**Scientific content:** descriptive pilot-scale evidence only. No change to frozen run artefacts, numerical aggregates, or manuscript tables relative to the submission freeze.

## What is included

| Component | Location |
|-----------|----------|
| Core infrastructure (v1 lineage) | `schemas/`, `scripts/`, `prompts/`, `tests/`, `docs/` |
| Frozen pilot — default arm | `freezes/frozen_pilot_001/` |
| Frozen pilot — operation-aware arm | `freezes/diagnostic_granularity_pilot_diverse_operation_aware_001/` |
| Frozen pilot — operation-inferred arm | `freezes/frozen_main_pilot_001/` |
| Paper generation | `scripts/generate_paper_tables.py`, `scripts/generate_paper_figures.py` |
| Analysis | `scripts/analyze_repair_outcomes.py`, `scripts/analyze_patch_failures.py` |
| Replication packaging | `scripts/package_replication_bundle.py` |

Each frozen pilot includes `diagnostic_granularity_summary.json`, `diagnostic_granularity_results.csv`, full `runs/` trees, and `analysis/` summaries where packaged.

## What is not included

- Private `paper/` drafts (companion repository)
- Bit-identical Tier B re-generation of LLM completions (documented as non-reproducible)
- Multi-model benchmarks or factorial crossing of all protocol factors
- Hypothesis tests or inferential statistics

## Verification performed for this release

1. **Frozen directories referenced by the manuscript** exist under `paper/experiments/` and `freezes/`:
   - `frozen_pilot_001`
   - `diagnostic_granularity_pilot_diverse_operation_aware_001`
   - `frozen_main_pilot_001`
   - `pilot_repair_cases_diverse`

2. **Tier A regeneration** from `$PAPER_ROOT` with v2 scripts reproduces:
   - `tables/main_results.tex`
   - `tables/repair_outcomes.tex`
   - `tables/failure_analysis.tex`
   - `figures/evaluated_cases_by_variant.pdf`
   - `figures/repair_success_rate.pdf`
   - `figures/patch_failure_breakdown.pdf`

   (Timestamps in auto-generated LaTeX headers may differ; numeric cell values unchanged.)

3. **`python -m pytest`** passes on the release tag.

## Author identity

Canonical author: **César Andrés**, ORCID `0009-0001-8968-3404`, email `cesar.andress@ucjc.edu`.

Updated in [`CITATION.cff`](CITATION.cff), [`README.md`](README.md), and [`LICENSE`](LICENSE).

## Zenodo and GitHub publication checklist

1. Tag `v2.0.0` on GitHub.
2. Create GitHub release with these notes (copy from this file).
3. Upload / sync Zenodo deposit including `freezes/` (large); confirm tarball size limits.
4. Update `CITATION.cff` `doi:` and `date-released` with the new Zenodo version DOI.
5. Update manuscript Data availability with the v2.0.0 campaign DOI when assigned.

**Previous DOI (v1.0.x infrastructure):** [10.5281/zenodo.20529518](https://doi.org/10.5281/zenodo.20529518)

## Upgrade from v1.0.1

| v1.0.1 | v2.0.0 |
|--------|--------|
| Infrastructure only | Infrastructure + frozen pilots |
| No campaign data | Three 90-slot pilot arms |
| REPRODUCIBILITY.md — smoke tests | REPRODUCIBILITY.md — full Tier A command list |
| ARTIFACT_SCOPE — no empirical results | ARTIFACT_OVERVIEW — manuscript-linked evidence |

Scripts and schemas remain backward compatible for v1 dry-run and pytest workflows.

## Reproducibility quick start

```bash
export REPO_ROOT="$(pwd)"
export PAPER_ROOT="/path/to/ist2026b/paper"

python3.12 -m venv .venv && source .venv/bin/activate
pip install -r environment/requirements.txt
python -m pytest

# Tier A — see REPRODUCIBILITY.md for full block
python scripts/generate_paper_tables.py --paper-root "$PAPER_ROOT"
python scripts/generate_paper_figures.py --paper-root "$PAPER_ROOT"
```

## Related releases

- [`RELEASE_NOTES_v1.0.0.md`](RELEASE_NOTES_v1.0.0.md) — initial infrastructure
- [`RELEASE_NOTES_v1.0.1.md`](RELEASE_NOTES_v1.0.1.md) — CITATION.cff metadata fix
