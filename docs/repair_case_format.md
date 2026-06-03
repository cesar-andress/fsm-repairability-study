# Repair case file format

> **Schema 2.0.0.** The canonical scientific design for the experimental unit is [`experimental_unit.md`](experimental_unit.md). This page summarises file conventions only.

## Manifest

- **Path:** `datasets/repair_cases/<campaign_id>/<case_id>/case.json` (recommended at scale) or `datasets/repair_cases/<case_id>/case.json`
- **Schema:** [`schemas/repair_case.schema.json`](../schemas/repair_case.schema.json) v2.0.0

## Required sections

`identity`, `inputs`, `baseline`, `oracles`, `diagnostics`, `repair_history`, `final_outcome`

See [`experimental_unit.md`](experimental_unit.md) for field semantics, oracle separation, JSON examples, and Zenodo layout.

## Legacy note

Schema 1.0.0 used flat fields (`gold_fsm_path`, `oracle_suite_id`, `final_status`, `repair_history` as a bare array). New corpora must use 2.0.0 nested structure.
