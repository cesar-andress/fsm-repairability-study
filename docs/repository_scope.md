# Repository scope

This project maintains two directories with distinct roles.

## Private research workspace (`paper/`)

**Purpose:** Day-to-day research, writing, and exploration.

**May contain:**

- Manuscript drafts and revision history
- Exploratory scripts and one-off analyses
- Raw experiment logs and incomplete campaigns
- Notes, hypotheses, and discarded approaches
- Temporary figures and internal checklists

**Must not be assumed:** Reproducible, complete, or redistributable. No replication instructions are required here.

## Public artifact repository (`fsm-repairability-study/`)

**Purpose:** GitHub and Zenodo deposit supporting the empirical study of behavioural repairability.

**Must contain only:**

- Final (or paper-reported) datasets and oracle definitions
- Frozen prompts used in reported conditions
- JSON schemas and minimal deterministic scripts
- Aggregated results needed to verify claims
- Documentation: study design, terminology, reproducibility, data statement

**Must not contain:**

- Unpublished manuscript sources
- Exploratory campaigns or model-comparison leaderboards
- Intermediate files not needed to reproduce reported results
- Material whose primary goal is benchmarking more LLM models

## Scientific boundary

Previous work established that structural validity and behavioural correctness can diverge for LLM-generated FSMs. **This artifact does not restate that finding as the main contribution.**

The public repository supports study of **behavioural repairability**: repair of structurally valid but behaviourally incorrect FSMs using behavioural oracle feedback, under explicitly defined **repair conditions** (primary independent variable). Local Ollama models are experimental engines for optional re-execution and sensitivity analysis, not the main scientific object.

Structural gates (e.g. G1/G2/G3-style checks) may appear as **preconditions** or filtering steps, but they are not the scientific object of the repository.

## Synchronization policy

1. Design and pilot in `paper/`.
2. Freeze cases, prompts, and results that appear in the paper.
3. Copy or export only the frozen subset into `fsm-repairability-study/`.
4. Version the public repo (tag + Zenodo DOI) at submission or acceptance, per journal policy.

## Maintainer checklist (before release)

- [ ] No paths or files reference `paper/`
- [ ] `CITATION.cff` and `LICENSE` finalized
- [ ] `DATA_STATEMENT.md` matches actual Zenodo contents
- [ ] `REPRODUCIBILITY.md` commands run on a clean machine
- [ ] Dataset and result checksums documented
