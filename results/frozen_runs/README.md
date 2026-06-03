# Frozen repair runs

Machine-readable **complete repair run** records for audit replication without re-invoking an experimental engine.

## File format

Each file is one JSON document conforming to [`schemas/repair_run.schema.json`](../../schemas/repair_run.schema.json). See [`docs/repair_run_format.md`](../../docs/repair_run_format.md).

## Naming convention

```
<input_case_id>__<repair_condition>__<model_slug>.json
<input_case_id>__baseline_no_repair.json
```

Example: `tlc_01__patch_trace_feedback__llama3_8b.json`

## Required summary fields

`run_id`, `timestamp`, `model_name`, `repair_condition`, `iteration_number`, `input_case_id`, `input_bpr`, `output_bpr`, `patch_count`, `patch_size`, `regression_detected`, `convergence_status`.

## Status

Placeholder directory until campaign freeze. Populate from study exports only.
