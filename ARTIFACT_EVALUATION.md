# Artifact Evaluation — Diagnostic Granularity FSM Repair Pilot

This document supports **Information and Software Technology (IST)** artifact evaluation for the pilot study *Diagnostic Granularity for LLM-Based Repair of Finite State Machines*.

The evaluation is designed in two tiers:

| Tier | Goal | Ollama / GPU | Time (indicative) |
|------|------|--------------|-------------------|
| **A (recommended)** | Reproduce **aggregates, tables, figures, and selected runs** from frozen outputs | Not required | ~15–30 minutes |
| **B (optional)** | Re-execute the full pilot on all 30 cases | Required | Hours (model-dependent) |

Tier **A** matches what reviewers need to validate the paper’s descriptive claims without re-invoking the language model.

---

## 1. Artifact components

| Component | Location | Role |
|-----------|----------|------|
| Study code | This repository (`fsm-repairability-study`) | Schemas, deterministic pipeline, analysis and packaging scripts, tests |
| Replication package | Zenodo deposit and/or `paper/replication_package.zip` (companion bundle) | Frozen summaries, LaTeX tables, PDF figures, selected `repair_run` artefacts |
| Full pilot outputs | `paper/experiments/` (when provided with the submission) | Complete `runs/` trees for three frozen arms |

**Public code archive:** [https://doi.org/10.5281/zenodo.20529518](https://doi.org/10.5281/zenodo.20529518) (infrastructure release; check `metadata.json` in the replication package for the analysis revision used in the paper freeze).

**Three frozen experiment arms:**

| Prompt variant | Directory under `experiments/` |
|----------------|-------------------------------|
| `default` | `frozen_pilot_001` |
| `operation-aware` | `diagnostic_granularity_pilot_diverse_operation_aware_001` |
| `operation-inferred` | `frozen_main_pilot_001` |

**Diagnostic conditions:** `C` (binary), `D` (trace), `E` (localized feedback).  
**Pilot scale:** 30 diverse repair cases, model `qwen2.5-coder:7b`, one repair iteration per case–condition.

---

## 2. Hardware requirements

### Tier A — Audit replication (recommended)

| Resource | Minimum |
|----------|---------|
| CPU | 2 cores |
| RAM | 4 GB |
| Disk | 500 MB free (repository + replication package + generated outputs) |
| GPU | **Not required** |

### Tier B — Full pilot re-execution (optional)

| Resource | Recommended |
|----------|-------------|
| CPU | 4+ cores |
| RAM | 16 GB |
| GPU | NVIDIA GPU with ≥16 GB VRAM (e.g. RTX 4090 class, as in the original workstation) |
| Disk | 10+ GB for run artefacts and Ollama model weights |

Network access is required only for **initial** Ollama model pull (`qwen2.5-coder:7b`); Tier A does not need network after downloads.

---

## 3. Software requirements

### Required (Tier A and B)

| Software | Version |
|----------|---------|
| **Python** | **3.12 or newer** (`pyproject.toml`: `requires-python >= 3.12`) |
| `pip` | Current for Python 3.12 |
| Git | Any recent version |

### Required for Tier A — paper tables (optional but expected in AE)

| Software | Purpose |
|----------|---------|
| `pdflatex` + `bibtex` | Compile `paper/main.tex` if verifying the manuscript bundle |
| LaTeX package `booktabs` | Included in generated table fragments |

### Required for Tier B only

| Software | Purpose |
|----------|---------|
| [Ollama](https://ollama.com/) | Local LLM backend |
| Model tag | `qwen2.5-coder:7b` (pull before running the pilot) |

### Python dependencies

Install from this repository:

```bash
python -m pip install -r environment/requirements.txt
```

Includes: `jsonschema`, `PyYAML`, `pytest`, `matplotlib` (figures). No cloud API keys.

---

## 4. Installation

### 4.1 Clone the study repository

```bash
git clone <repository-url> fsm-repairability-study
cd fsm-repairability-study
```

Check out the revision recorded in the replication package:

```bash
# After unpacking replication_package/metadata.json:
git checkout <study_repository.revision>
```

### 4.2 Python environment

```bash
python3.12 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r environment/requirements.txt
```

### 4.3 Obtain experiment data

**Option 1 — Replication package (smallest):**

```bash
unzip replication_package.zip -d paper
# Layout: paper/replication_package/{summaries,tables,figures,repair_runs,...}
```

**Option 2 — Full pilot tree (if supplied with the paper workspace):**

Ensure the following exist:

```text
paper/experiments/frozen_pilot_001/
paper/experiments/diagnostic_granularity_pilot_diverse_operation_aware_001/
paper/experiments/frozen_main_pilot_001/
paper/results/main_results_table.csv
```

Set `PAPER_ROOT` to the directory that contains `experiments/` and `results/` (parent of `replication_package/` when both are present).

### 4.4 Verify installation

```bash
python -m pytest -q
```

**Expected:** all tests pass (300+). Failures usually indicate wrong Python version or missing dependencies.

---

## 5. Reproduction steps (Tier A — recommended)

All commands assume the repository root `fsm-repairability-study/` and an activated virtual environment.

Set paths (adjust to your layout):

```bash
export REPO_ROOT="$(pwd)"
export PAPER_ROOT="/path/to/paper"    # contains experiments/ and results/
```

### Step 1 — Confirm frozen inputs

```bash
test -f "$PAPER_ROOT/results/main_results_table.csv"
test -f "$PAPER_ROOT/experiments/frozen_pilot_001/diagnostic_granularity_summary.json"
```

### Step 2 — Regenerate per-pilot analysis (read-only on `runs/`)

For each pilot directory `PILOT` in the three folders listed above:

```bash
python scripts/analyze_repair_outcomes.py --pilot-dir "$PAPER_ROOT/experiments/frozen_pilot_001"
python scripts/analyze_patch_failures.py --pilot-dir "$PAPER_ROOT/experiments/frozen_pilot_001"
python scripts/analyze_successful_repairs.py --pilot-dir "$PAPER_ROOT/experiments/frozen_pilot_001"
python scripts/analyze_regressions.py --pilot-dir "$PAPER_ROOT/experiments/frozen_pilot_001"
```

Repeat for `diagnostic_granularity_pilot_diverse_operation_aware_001` and `frozen_main_pilot_001`.

**Writes (under each pilot):** `analysis/repair_outcome_summary.{json,csv}`, `analysis/patch_failure_summary.{json,csv}`, `analysis/successful_repairs.{json,csv}`, `analysis/regression_summary.{json,csv}`.

### Step 3 — Regenerate paper tables and figures

```bash
python scripts/generate_paper_tables.py --paper-root "$PAPER_ROOT"
python scripts/generate_paper_figures.py --paper-root "$PAPER_ROOT"
```

**Writes:** `paper/tables/{main_results,repair_outcomes,failure_analysis}.tex`, `paper/figures/*.pdf`.

### Step 4 — Regenerate Results narrative fragment

```bash
python scripts/generate_results_section.py --paper-root "$PAPER_ROOT"
```

**Writes:** `paper/generated/results_generated.tex`.

### Step 5 — Build replication package (optional checksum)

```bash
python scripts/package_replication_bundle.py --paper-root "$PAPER_ROOT"
```

**Writes:** `paper/replication_package/`, `paper/replication_package.zip`.

### Step 6 — Inspect selected repair runs

Compare bundled runs under `replication_package/repair_runs/` (or the same paths under `experiments/.../runs/`) with:

- `repair_run.json` — `outcome.effective_repair`, `final_bpr_validation`, `initial` BPR in `iterations[0]`
- `scores_validation_before.json` / `scores_validation_after.json` (when copied)
- `patch_source.json` — operation list

### Step 7 — Run test suite against paper tree (optional)

```bash
python -m pytest tests/test_generate_paper_tables.py \
  tests/test_generate_paper_figures.py \
  tests/test_generate_results_section.py \
  tests/test_package_replication_bundle.py -q
```

Skips integration tests if `PAPER_ROOT` is absent.

---

## 6. Reproduction steps (Tier B — optional full re-execution)

Requires Ollama, GPU, and the **30-case corpus** (`pilot_repair_cases_diverse` or equivalent under `paper/experiments/`).

```bash
ollama pull qwen2.5-coder:7b
ollama serve   # if not already running
```

```bash
python scripts/run_diagnostic_granularity_pilot.py \
  --cases-dir "$PAPER_ROOT/experiments/pilot_repair_cases_diverse" \
  --model qwen2.5-coder:7b \
  --output-dir "$PAPER_ROOT/experiments/my_replication_run" \
  --prompt-variant default
```

Use `--prompt-variant operation-aware` or `operation-inferred` for the other arms (see [`docs/diagnostic_granularity_pilot.md`](docs/diagnostic_granularity_pilot.md)).

**Note:** Stochastic LLM outputs will **not** match frozen pilot bytes. Tier B validates the **pipeline**, not bit-identical reproduction. Compare distributions and failure taxonomy, not exact patch JSON.

---

## 7. Expected outputs (Tier A)

Compare regenerated files to the replication package (or submission freeze). Values below are **descriptive** for the reference freeze; treat small timestamp or path differences as non-failures.

### 7.1 `main_results_table.csv` (condition E exemplar)

| Variant | Evaluated | Failed (approx.) | Patch failures (CSV column) |
|---------|-----------|------------------|----------------------------|
| `default` | 9 | 21 | 21 |
| `operation-aware` | 13 | 17 | 17 |
| `operation-inferred` | 23 | 7 | 0 |

### 7.2 `diagnostic_granularity_summary.json` (per pilot, all conditions)

- `cases_attempted`: **30** per condition label  
- `complete_repair_rate`: **0** in the reference freeze (no case reached validation BPR = 1.0)  
- Dominant failure mode under default/aware patch authoring: **`duplicate_transition`** (see `patch_failure_summary.json`)

### 7.3 `repair_outcome_summary.json` (default pilot, condition E)

- `cases_evaluated`: **9**  
- `effective_repair_count`: **3**  
- `improved_count`: **3**  
- `complete_repair_count`: **0**

### 7.4 `successful_repairs.json` (default pilot)

- `aggregates.effective_repair_count`: **3** (all `bike_rental`, condition **E** in reference freeze)

### 7.5 `regression_summary.json` (default pilot)

- `aggregates.degraded_count`: **3** (condition **C** in reference freeze)

### 7.6 Generated figures

| File | Content |
|------|---------|
| `evaluated_cases_by_variant.pdf` | Bar chart of evaluated runs |
| `repair_success_rate.pdf` | Effective repair rate on evaluated runs |
| `patch_failure_breakdown.pdf` | Stacked failure classes by variant |

### 7.7 Tests

```bash
python -m pytest -q
```

**Expected:** exit code 0, no failures.

### 7.8 What is *not* expected

- Bit-identical Ollama completions across machines (Tier B).  
- Population-level claims beyond the 30-case pilot (paper scope is explicitly pilot-scale).  
- Non-zero `complete_repair_count` in the reference freeze unless new experiments were run.

---

## 8. Troubleshooting

### `Python 3.12` not found

Install Python 3.12+ or use `pyenv` / distro packages. Confirm with `python3.12 --version`. Older interpreters fail on syntax and type hints.

### `pytest` failures after install

```bash
python -m pip install -r environment/requirements.txt
python -m pytest tests/test_schemas.py -q
```

If schema tests fail, confirm the working tree matches `metadata.json` → `study_repository.revision`.

### `missing runs directory` / `missing experiments directory`

`PAPER_ROOT` must point to the paper workspace that contains `experiments/`, not the repository root alone. Unzip `replication_package.zip` or obtain the full `paper/experiments/` tree.

### `missing diagnostic_granularity_summary.json`

Run Tier B for that arm, or use the bundled copy under `replication_package/summaries/experiments/<slug>/`.

### `matplotlib` / figure generation errors

```bash
python -m pip install 'matplotlib>=3.8,<4'
```

Headless servers: export `MPLBACKEND=Agg` (scripts set this internally; set manually if invoking matplotlib elsewhere).

### `pdflatex` errors when building the paper

```bash
cd paper && make clean && make
```

Install `texlive-latex-base` and `texlive-latex-extra` (for `booktabs`). Macro errors on `\DeltaBPR` in section titles were fixed in `paper/macros.tex`; pull latest `paper/` sources if needed.

### Analysis counts differ from Section 7

1. Confirm the same three pilot directories.  
2. Confirm analysis scripts were run **after** checkout of the frozen revision.  
3. Do not mix pilots (e.g. broken `operation_inferred_001`); use `frozen_main_pilot_001` for operation-inferred.  
4. Re-run all four analyzers before `generate_paper_*` scripts.

### Ollama / Tier B: generation failures dominate

Expected on some case–condition pairs. Compare **failure category counters** in `diagnostic_granularity_summary.json`, not only mean ΔBPR on evaluated runs.

### `package_replication_bundle.py` permission or zip errors

Ensure `paper/replication_package/` is writable. Use `--no-clean` to append without deleting an existing bundle.

### Integration tests skipped

Tests under `tests/test_*paper*` skip when `../paper` is absent. This is normal in a code-only checkout; provide `PAPER_ROOT` for full integration coverage.

---

## 9. Mapping to paper claims (evaluator checklist)

| Claim type | Evidence to inspect |
|------------|---------------------|
| Executability (operation-inferred on E) | `main_results_table.csv` / Table `tab:main_results`: patch failures 21→0 on E; `patch_failure_summary.json` |
| Limited behavioural lift | `repair_outcome_summary.json`: low mean ΔBPR; `complete_repair_count` = 0 |
| Effective repairs exist but are rare | `successful_repairs.csv`; `repair_runs/` selection reason `effective_repair` |
| Regressions occur | `regression_summary.csv`; selected runs with negative ΔBPR |
| Pilot scale only | 30 cases, single model in summaries; README in replication package |

---

## 10. Further reading

| Document | Topic |
|----------|--------|
| [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md) | General study reproducibility modes |
| [`docs/diagnostic_granularity_pilot.md`](docs/diagnostic_granularity_pilot.md) | Pilot protocol and CSV/summary fields |
| [`docs/experimental_setup.md`](docs/experimental_setup.md) | Workstation and Ollama setup |
| [`ARTIFACT_SCOPE.md`](ARTIFACT_SCOPE.md) | What the public v1.0.x archive includes |
| `paper/replication_package/README.md` | Bundle layout (when available) |

---

## 11. Contact and evaluation metadata

Record in your evaluation form:

- **Artifact type:** Reusable research / replication package + study code  
- **Recommended tier:** A (audit, no GPU)  
- **Estimated Tier A duration:** 15–30 minutes excluding LaTeX  
- **License:** MIT (study code); replication package license per Zenodo record (`metadata.json` → `license_spdx`)

For questions about paths or freeze identifiers, cite `replication_package/metadata.json` (`created_at`, `study_repository.revision`, `pilots`).
