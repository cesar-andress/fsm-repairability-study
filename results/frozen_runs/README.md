# Frozen repair runs

Machine-readable records of completed **case × condition** executions (and optional `model_label` for sensitivity runs).

## Naming convention

```
{case_id}__{condition_id}.json
{case_id}__{condition_id}__{model_label}.json   # sensitivity / engine label
```

Example: `case_01__patch_trace_feedback__llama3_8b.json`

## Purpose

Enables **Mode A** replication (see `docs/experimental_setup.md`): verify paper statistics without Ollama or the original RTX 4090 workstation.

Each file should conform to `schemas/repair_run.schema.json` (or a documented superset with summary fields).

## Status

Empty until campaign freeze. Populate from study exports, not from exploratory `paper/` logs.
