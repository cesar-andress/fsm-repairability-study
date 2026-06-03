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

## CLI

```bash
python scripts/extract_repair_candidates.py \
  --benchmark-dir /path/to/benchmark_export \
  --output-dir datasets/pilot_repair_cases
```

| Flag | Default | Role |
|------|---------|------|
| `--benchmark-dir` | (required) | Root containing `manifest.json` |
| `--output-dir` | `datasets/pilot_repair_cases` | Pilot case output root |
| `--max-candidates` | none | Optional cap on cases written |

## Outputs

### Per selected case (`<output-dir>/<case_id>/`)

| File | Content |
|------|---------|
| `case.json` | Repair case manifest (`repair_status: not_started`) |
| `candidate_fsm.json` | Structurally valid, behaviourally incorrect candidate |
| `reference_fsm.json` | Reference (gold) FSM |
| `oracle_suite.json` | Copied oracle suite used for admission scoring |

Feedback and validation oracle bindings in `case.json` both reference the local `oracle_suite.json` (pilot default: same suite for admission and repair).

### Campaign report

`<output-dir>/candidate_selection_report.csv`

| Column | Meaning |
|--------|---------|
| `case_id` | Case slug |
| `system_id` | System slug |
| `initial_bpr` | Validation BPR at extraction |
| `failed_tests` | Count of failed oracle tests |
| `candidate_size` | UTF-8 byte size of canonical JSON for candidate FSM |
| `reference_size` | UTF-8 byte size of canonical JSON for reference FSM |

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
