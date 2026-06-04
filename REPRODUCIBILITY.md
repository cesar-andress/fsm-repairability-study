# Reproducibility — fsm-repairability-study v2.0.0

This document lists **exact commands** to regenerate the JSON summaries, LaTeX tables, and PDF figures cited by the IST manuscript. Commands assume a sibling layout:

```text
ist2026b/
├── fsm-repairability-study/    ← REPO_ROOT (this repository)
└── paper/                      ← PAPER_ROOT (manuscript + experiments mirror)
```

Adjust paths if your checkout differs. **Python 3.12 or newer is required.**

## Environment setup

```bash
export REPO_ROOT="/path/to/fsm-repairability-study"
export PAPER_ROOT="/path/to/paper"

cd "$REPO_ROOT"
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r environment/requirements.txt
python -m pytest
```

## Frozen inputs (verify before Tier A)

Manuscript pilot directories under `$PAPER_ROOT/experiments/`:

| Pilot directory | Variant |
|---------------|---------|
| `frozen_pilot_001` | default |
| `diagnostic_granularity_pilot_diverse_operation_aware_001` | operation-aware |
| `frozen_main_pilot_001` | operation-inferred |

Each must contain `diagnostic_granularity_summary.json` and `runs/`. Shared cases: `$PAPER_ROOT/experiments/pilot_repair_cases_diverse/`.

Equivalent bundles ship in this repository under `$REPO_ROOT/freezes/<same-directory-name>/`.

```bash
for PILOT in frozen_pilot_001 \
  diagnostic_granularity_pilot_diverse_operation_aware_001 \
  frozen_main_pilot_001; do
  test -f "$PAPER_ROOT/experiments/$PILOT/diagnostic_granularity_summary.json" \
    || echo "MISSING: $PILOT/diagnostic_granularity_summary.json"
done
test -f "$PAPER_ROOT/results/main_results_table.csv" \
  || echo "MISSING: results/main_results_table.csv"
```

---

## 1. `diagnostic_granularity_summary.json`

**Source:** Written at **campaign completion** by `run_diagnostic_granularity_pilot.py` (Tier B). Tier A **reads** the frozen file; it is not recomputed from `runs/` by the analysis scripts.

**Tier B — illustrative re-run (one arm; outputs will differ from the freeze):**

```bash
cd "$REPO_ROOT"
source .venv/bin/activate
ollama pull qwen2.5-coder:7b   # once, requires network

python scripts/run_diagnostic_granularity_pilot.py \
  --cases-dir "$PAPER_ROOT/experiments/pilot_repair_cases_diverse" \
  --model qwen2.5-coder:7b \
  --output-dir "$PAPER_ROOT/experiments/my_rerun_001" \
  --prompt-variant default
```

Outputs in `$PAPER_ROOT/experiments/my_rerun_001/`:

- `diagnostic_granularity_summary.json`
- `diagnostic_granularity_results.csv`
- `runs/<case_id>/{C,D,E}/`

Use `--prompt-variant operation-aware` or `operation-inferred` for other arms.

---

## 2. `repair_outcome_summary.json`

**Source:** `analyze_repair_outcomes.py` — read-only scan of `runs/**/repair_run.json`.

**Writes:**

- `<pilot-dir>/analysis/repair_outcome_summary.json`
- `<pilot-dir>/analysis/repair_outcome_summary.csv`

**Exact commands (all three manuscript arms):**

```bash
cd "$REPO_ROOT"
source .venv/bin/activate

python scripts/analyze_repair_outcomes.py \
  --pilot-dir "$PAPER_ROOT/experiments/frozen_pilot_001"

python scripts/analyze_repair_outcomes.py \
  --pilot-dir "$PAPER_ROOT/experiments/diagnostic_granularity_pilot_diverse_operation_aware_001"

python scripts/analyze_repair_outcomes.py \
  --pilot-dir "$PAPER_ROOT/experiments/frozen_main_pilot_001"
```

---

## 3. `patch_failure_summary.json`

**Source:** `analyze_patch_failures.py` — classifies patch-application failures from pilot `runs/`.

**Writes:**

- `<pilot-dir>/patch_failure_summary.json`
- `<pilot-dir>/patch_failure_summary.csv`
- (optional copy under `analysis/` when packaged for submission)

**Exact commands:**

```bash
cd "$REPO_ROOT"
source .venv/bin/activate

python scripts/analyze_patch_failures.py \
  --pilot-dir "$PAPER_ROOT/experiments/frozen_pilot_001"

python scripts/analyze_patch_failures.py \
  --pilot-dir "$PAPER_ROOT/experiments/diagnostic_granularity_pilot_diverse_operation_aware_001"

python scripts/analyze_patch_failures.py \
  --pilot-dir "$PAPER_ROOT/experiments/frozen_main_pilot_001"
```

---

## 4. LaTeX tables

**Source:** `generate_paper_tables.py`

**Reads:**

- `<pilot-dir>/diagnostic_granularity_summary.json` (main results / executability)
- `runs/` via `analyze_repair_outcomes()` (repair outcomes)
- `runs/` via `analyze_patch_failures()` (failure analysis)

**Writes:**

- `$PAPER_ROOT/tables/main_results.tex`
- `$PAPER_ROOT/tables/repair_outcomes.tex`
- `$PAPER_ROOT/tables/failure_analysis.tex`

**Exact command:**

```bash
cd "$REPO_ROOT"
source .venv/bin/activate

python scripts/generate_paper_tables.py --paper-root "$PAPER_ROOT"
```

---

## 5. PDF figures

**Source:** `generate_paper_figures.py`

**Reads:** `$PAPER_ROOT/results/main_results_table.csv` and pilot summaries as configured in the script.

**Writes:**

- `$PAPER_ROOT/figures/evaluated_cases_by_variant.pdf`
- `$PAPER_ROOT/figures/repair_success_rate.pdf`
- `$PAPER_ROOT/figures/patch_failure_breakdown.pdf`

**Exact command:**

```bash
cd "$REPO_ROOT"
source .venv/bin/activate

python scripts/generate_paper_figures.py --paper-root "$PAPER_ROOT"
```

---

## 6. Full Tier A pipeline (single script block)

```bash
export REPO_ROOT="/path/to/fsm-repairability-study"
export PAPER_ROOT="/path/to/paper"
cd "$REPO_ROOT"
source .venv/bin/activate

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

Optional manuscript PDF:

```bash
cd "$PAPER_ROOT" && latexmk -pdf main.tex
```

From `$PAPER_ROOT`, `make tables` and `make figures` wrap the same generators when `$REPO_ROOT/.venv` exists.

---

## 7. Optional replication package

```bash
cd "$REPO_ROOT"
source .venv/bin/activate

python scripts/package_replication_bundle.py --paper-root "$PAPER_ROOT"
```

Creates `$PAPER_ROOT/replication_package/` and `$PAPER_ROOT/replication_package.zip`.

---

## v1.0.x infrastructure smoke test (no campaign data)

Release v1.0.0 validated schemas and deterministic tooling only:

```bash
cd "$REPO_ROOT"
source .venv/bin/activate
python -m pytest

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

---

## Citation

Cite the Zenodo record for the release you used. Update after v2.0.0 deposit:

- v1.0.x infrastructure: [10.5281/zenodo.20529518](https://doi.org/10.5281/zenodo.20529518)
- v2.0.0: see [`CITATION.cff`](CITATION.cff) after publication

See [`docs/citation.md`](docs/citation.md).
