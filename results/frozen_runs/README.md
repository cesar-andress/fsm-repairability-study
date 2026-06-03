# Frozen repair runs

Machine-readable **repair run** records (schema v2.0.0): one file per execution of one repair condition on one case.

## Format

[`docs/repair_run_format.md`](../../docs/repair_run_format.md) · [`schemas/repair_run.schema.json`](../../schemas/repair_run.schema.json)

## Layout (recommended)

```
results/frozen_runs/
  <case_id>/
    <repair_condition>/
      <run_id>.json
```

Supports repeated runs (`identity.run_sequence`), multiple conditions, and multiple engines (sensitivity).

## Status

Placeholder until campaign freeze.
