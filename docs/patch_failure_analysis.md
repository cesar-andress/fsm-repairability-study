# Patch failure analysis

Private post-hoc utility for classifying **patch application failures** observed in diagnostic granularity pilot outputs.

Implemented by [`scripts/analyze_patch_failures.py`](../scripts/analyze_patch_failures.py).

## Purpose

When pilot conditions report `patch_application_error`, repair effectiveness is confounded by patch-engine rejection (duplicate transitions, missing states, and similar). This tool aggregates those failures for interpretation **without** modifying pilot artefacts, re-running repair, or calling Ollama.

## Input

```bash
python scripts/analyze_patch_failures.py \
  --pilot-dir /path/to/diagnostic_granularity_pilot_output
```

| Flag | Role |
|------|------|
| `--pilot-dir` | Root written by [`run_diagnostic_granularity_pilot.py`](../scripts/run_diagnostic_granularity_pilot.py) (read-only) |
| `--output-dir` | Optional; default writes summaries into `--pilot-dir` |

Expected layout (see [`diagnostic_granularity_pilot.md`](diagnostic_granularity_pilot.md)):

```text
<pilot-dir>/
  diagnostic_granularity_results.csv
  runs/<case_id>/<C|D|E>/
    error.txt
    ollama/patch.json
    prep/candidate.json
    ...
```

## Output

| File | Content |
|------|---------|
| `patch_failure_summary.csv` | One row per classified patch-application failure |
| `patch_failure_summary.json` | Same rows plus aggregate counts |

### Per-failure columns (CSV)

| Column | Meaning |
|--------|---------|
| `case_id` | Repair case slug |
| `condition` | Pilot label `C`, `D`, or `E` |
| `status` | Status from results CSV (typically `patch_application_error`) |
| `error_message` | Text from `error.txt` or results CSV |
| `patch_path` | Resolved `ollama/patch.json` when present |
| `operation_index` | Parsed `operation[N]` index from the error |
| `operation_type` | `op` field from the patch at that index |
| `source_state` | `from` (transition operations) |
| `event` | `event` |
| `target_state` | `to` or `new_to` for updates |
| `failure_class` | Taxonomy below |

### Failure classes

| Class | Typical error signal |
|-------|---------------------|
| `duplicate_transition` | Duplicate `(from, event)` on add/update |
| `missing_state` | `from` / `to` / `new_to` not in `states` |
| `unknown_event` | Unknown or invalid event (reserved) |
| `transition_not_found` | Remove/update could not match a transition |
| `invalid_operation_semantics` | Self-loops, schema/target mismatch, unsupported ops, post-patch validation |
| `other` | Unclassified patch application errors |

Classification uses error text heuristics aligned with [`apply_patch.py`](../scripts/apply_patch.py).

### JSON aggregates

`aggregates` in `patch_failure_summary.json`:

| Key | Meaning |
|-----|---------|
| `total_failures` | Row count |
| `by_condition` | Counts per `C` / `D` / `E` |
| `by_failure_class` | Counts per failure class |
| `by_system_id` | Counts per system slug inferred from `case_id` |
| `by_operation_type` | Counts per `op` (or `(unknown)`) |

## Selection rules

A case–condition pair is analyzed when:

- `status_*` in `diagnostic_granularity_results.csv` is `patch_application_error`, or
- `error.txt` / CSV error text matches patch-application markers (`patch application failed`, etc.).

Non-patch failures (generation, scoring, and similar) are **excluded**.

## Privacy

Do not commit real pilot output trees or generated summaries from production runs. Use the synthetic fixture at [`tests/fixtures/patch_failure_pilot/`](../tests/fixtures/patch_failure_pilot/) for tests.

## See also

- [`diagnostic_granularity_pilot.md`](diagnostic_granularity_pilot.md)
- [`patch_language.md`](patch_language.md)
- [`repair_candidate_selection.md`](repair_candidate_selection.md)
