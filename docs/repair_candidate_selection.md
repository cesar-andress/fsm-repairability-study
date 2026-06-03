# Repair candidate selection

Reuse finite state machines from **prior benchmark or generation studies** as repair cases for pilot repairability experiments. Implemented by [`scripts/extract_repair_candidates.py`](../scripts/extract_repair_candidates.py).

## Purpose

Earlier studies may produce many candidate FSMs. This utility **filters** those outputs against study admission rules and materializes [`repair_case.schema.json`](../schemas/repair_case.schema.json) v2.0.0 bundles under [`datasets/pilot_repair_cases/`](../datasets/pilot_repair_cases/).

It does not run repair, call Ollama, or modify existing orchestration scripts.

## Selection criteria

A benchmark entry is **selected** only if all of the following hold:

| Criterion | Check |
|-----------|--------|
| Structural validity | Candidate and reference pass [`validate_fsm.py`](../scripts/validate_fsm.py) (JSON Schema + referential integrity) |
| Imperfect behaviour | Validation BPR **&lt; 1.0** against the bundled oracle suite |
| Observable failure | **At least one** failed behavioural check in the score report |

Entries that fail any criterion are skipped (not written to the output tree). Only selected cases appear in `candidate_selection_report.csv`.

## Benchmark export layout

Place prior study outputs under a single **`--benchmark-dir`** root with a manifest:

```text
benchmark_export/
  manifest.json
  candidates/
    <candidate>.json
  references/
    <reference>.json
  oracles/
    <suite>.json
```

### `manifest.json`

```json
{
  "schema_version": "1.0.0",
  "campaign_id": "prior_study_batch_01",
  "entries": [
    {
      "case_id": "pilot_loop",
      "system_id": "loop_system",
      "requirement_text": "Natural-language requirement frozen at export.",
      "candidate_fsm_path": "candidates/pilot_loop_candidate.json",
      "reference_fsm_path": "references/pilot_loop_reference.json",
      "oracle_suite_path": "oracles/loop_oracle.json"
    }
  ]
}
```

| Field | Role |
|-------|------|
| `campaign_id` | Slug stored in `repair_case.identity.campaign_id` |
| `case_id` | Unique slug; output directory name |
| `system_id` | Behavioural system / task family |
| `requirement_text` | Frozen NL requirement |
| `*_path` | Paths **relative to** `--benchmark-dir` |

Example fixture: [`tests/fixtures/benchmark_export/`](../tests/fixtures/benchmark_export/).

## CLI (simple benchmark export)

```bash
python scripts/extract_repair_candidates.py \
  --benchmark-dir /path/to/benchmark_export \
  --output-dir datasets/pilot_repair_cases
```

| Flag | Default | Role |
|------|---------|------|
| `--benchmark-dir` | — | Root containing `manifest.json` (mutually exclusive with EMSE mode) |
| `--output-dir` | `datasets/pilot_repair_cases` | Pilot case output root |
| `--max-cases` | unlimited | Cap on cases written (`--max-candidates` alias) |
| `--max-cases-per-system` | unlimited | Cap per `system_id` |
| `--max-cases-per-model` | unlimited | Cap per `model_id` (EMSE mode) |
| `--min-initial-bpr` | none | Keep candidates with validation BPR ≥ this value |
| `--max-initial-bpr` | none | Keep candidates with validation BPR ≤ this value |
| `--prefer-diverse-systems` | off | Round-robin across `system_id` before filling caps |

## Pilot diversity guidance

Pilot repairability studies should **not** rely on a single behavioural system (for example only `vending_machine`). Mixed initial BPR and source-generation models reduce confounding when comparing repair conditions.

Recommended starting point for a private EMSE extract:

```bash
python scripts/extract_repair_candidates.py \
  --emse-ingestion-manifest /path/to/ingestion_manifest.json \
  --output-dir /private/pilot_repair_cases \
  --prefer-diverse-systems \
  --max-cases-per-system 3 \
  --max-cases 30
```

Selection behaviour:

1. Re-score and admit all eligible candidates (structural + behavioural gates).
2. Drop candidates outside `--min-initial-bpr` / `--max-initial-bpr` when set.
3. Order the pool by **insertion order** (default) or **round-robin by `system_id`** when `--prefer-diverse-systems` is set.
4. Take candidates until `--max-cases`, `--max-cases-per-system`, or `--max-cases-per-model` limits apply.

Without `--prefer-diverse-systems`, the first systems in manifest/CSV order can dominate the pilot set under a global `--max-cases` cap.

Interpret repairability only after confirming **multiple systems** and a spread of entry BPR values in `candidate_selection_report.csv`.

## EMSE behavioural campaign layout

Prior EMSE behavioural campaigns store metrics under timestamped run directories, not a flat `manifest.json`. Point the extractor at an **ingestion manifest** (for example `paper/data/campaign/ingestion_manifest.json` on a private checkout):

```json
{
  "c1_metrics": "/path/to/experiments/runs/C1_pilot_ollama_behavioral/20260603T003118Z/metrics.csv",
  "c2_metrics": "/path/to/experiments/runs/C2_.../metrics.csv"
}
```

Each run directory contains:

```text
<run-dir>/
  metrics.csv
  candidates/
  campaign_reports/
```

The **benchmark root** is discovered by walking parents of each metrics file until `benchmark/gold_fsms/` exists. Under that root:

| Asset | Path |
|-------|------|
| Gold FSM | `benchmark/gold_fsms/<system_id>.json` |
| Oracle suite | `benchmark/test_suites/<system_id>.json` |
| System spec | `benchmark/datasets/systems/<system_id>.json` |

### CSV row gates (EMSE mode)

A metrics row is eligible when:

- A behavioural pass rate column is present and **&lt; 1.0** (aliases: `behavioral_pass_rate`, `behavioural_pass_rate`, `bpr`, `BPR`)
- If any structural/G2 column is present, **all** of them must pass (`g2_pass`, `G2`, `schema_valid`, `structural_valid`, `referential_valid`, …)
- If a failed-check count column is present, it must be **&gt; 0**

The script re-scores each exported case; CSV gates only narrow the search space.

### Campaign folder and candidate files

- **Campaign id** for filenames and `case_id`: CSV `campaign_id` if set; otherwise the parent folder of a timestamp run dir (e.g. `C1_pilot_ollama_behavioral`); otherwise the run dir name (fixture layout).
- **Candidate path**: explicit path columns (`candidate_path`, `candidate_fsm_path`, `output_path`, `generated_fsm_path`), else `candidates/<run_id>.json` from `run_id` / `candidate_id`, else:

  `<campaign_id>__<system_id>__<model_sanitized>__rXX.json`

  with `:` and `/` in the model tag replaced by `_`, replicate zero-padded to two digits.

- **Deterministic `case_id`**: `repair__<campaign_slug>__<system_slug>__<model_slug>__rXX`

Missing candidate files emit a **warning** and the row is skipped (same as the simple export mode).

### CLI (EMSE mode)

```bash
python scripts/extract_repair_candidates.py \
  --emse-ingestion-manifest /path/to/ingestion_manifest.json \
  --output-dir /private/pilot_repair_cases \
  --max-cases 50
```

| Flag | Default | Role |
|------|---------|------|
| `--emse-ingestion-manifest` | — | JSON with `c1_metrics` / `c2_metrics` paths |
| `--output-dir` | `datasets/pilot_repair_cases` | **Use a private path** for real campaign exports |
| `--max-cases` | unlimited | Stop after N selected cases |
| `--max-cases-per-system` | unlimited | Per-system cap (see pilot diversity guidance) |
| `--max-cases-per-model` | unlimited | Per-model cap |
| `--min-initial-bpr` / `--max-initial-bpr` | none | Filter on re-scored validation BPR |
| `--prefer-diverse-systems` | off | Round-robin across systems |

Do **not** commit raw campaign logs or real EMSE outputs into the public repository.

Synthetic fixture: [`tests/fixtures/emse_campaign/`](../tests/fixtures/emse_campaign/).

## Outputs

### Per selected case (`<output-dir>/<case_id>/`)

| File | Content |
|------|---------|
| `case.json` | Repair case manifest (`repair_status: not_started`) |
| `candidate_fsm.json` | Structurally valid, behaviourally incorrect candidate |
| `reference_fsm.json` | Reference (gold) FSM |
| `oracle_suite.json` | Copied oracle suite used for admission scoring |
| `requirement.json` | EMSE mode only: copied system spec from `benchmark/datasets/systems/` |

Feedback and validation oracle bindings in `case.json` both reference the local `oracle_suite.json` (pilot default: same suite for admission and repair).

### Campaign report

`<output-dir>/candidate_selection_report.csv`

**Simple export mode**

| Column | Meaning |
|--------|---------|
| `case_id` | Case slug |
| `system_id` | System slug |
| `initial_bpr` | Validation BPR at extraction |
| `failed_tests` | Count of failed oracle tests |
| `candidate_size` | UTF-8 byte size of canonical JSON for candidate FSM |
| `reference_size` | UTF-8 byte size of canonical JSON for reference FSM |
| `selection_rank` | 1-based order in the selected pilot set |
| `selection_reason` | Why the row was kept (e.g. `eligible;insertion_order` or `eligible;bpr_in_range;round_robin_system`) |

**EMSE mode**

| Column | Meaning |
|--------|---------|
| `case_id` | Deterministic repair case slug |
| `campaign_id` | Campaign folder slug |
| `system_id` | System slug |
| `model_id` | Sanitized model tag |
| `replicate` | Replicate suffix (`r01`, …) |
| `initial_bpr` | Validation BPR at extraction |
| `failed_tests` | Failed oracle tests |
| `candidate_path` | Source candidate JSON path |
| `reference_path` | Gold FSM path used |
| `oracle_suite_path` | Oracle suite path used |
| `selection_rank` | 1-based order in the selected pilot set |
| `selection_reason` | Selection policy tags (see pilot diversity guidance) |

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | At least one case selected and written |
| `1` | No cases selected |
| `2` | Manifest or configuration error |

## Downstream use

Selected cases can feed:

- [`run_pilot_campaign.py`](../scripts/run_pilot_campaign.py) with `--cases-dir datasets/pilot_repair_cases`
- [`run_repair_condition.py`](../scripts/run_repair_condition.py) dry-run with `--patch-source`

## Provenance notes

- Extraction **re-scores** candidates; do not trust BPR labels from the source benchmark unless they used the same oracle suite.
- Strip non-schema FSM fields (e.g. undeclared `final_states`) before export, or extraction will reject the document.
- For production corpora, prefer explicit feedback vs validation oracle splits in `case.json`; the pilot layout duplicates one suite for simplicity.

## See also

- [`experimental_unit.md`](experimental_unit.md)
- [`pilot_campaign.md`](pilot_campaign.md)
- [`DATA_STATEMENT.md`](../DATA_STATEMENT.md)
