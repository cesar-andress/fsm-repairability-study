# Pilot repair cases

Repair case bundles produced by [`scripts/extract_repair_candidates.py`](../../scripts/extract_repair_candidates.py) from prior benchmark exports.

## Layout

```text
pilot_repair_cases/
  candidate_selection_report.csv
  <case_id>/
    case.json
    candidate_fsm.json
    reference_fsm.json
    oracle_suite.json
```

## Population

```bash
python scripts/extract_repair_candidates.py \
  --benchmark-dir /path/to/benchmark_export \
  --output-dir datasets/pilot_repair_cases
```

Selection criteria and manifest format: [`docs/repair_candidate_selection.md`](../../docs/repair_candidate_selection.md).

## Status

Empty until extraction is run. Generated case directories may be gitignored in local workflows; commit only curated pilot subsets intended for public release.
