# Repair run file format

A **repair run** is a frozen record of one complete execution of a repair protocol on one repair case: one **repair condition** (primary independent variable), one **input case**, and—when applicable—one **model name** (experimental engine). Documents validate against [`schemas/repair_run.schema.json`](../schemas/repair_run.schema.json) and are intended for long-term archival on Zenodo alongside repair cases and aggregated results.

## Scope of one record

One `repair_run.json` describes:

\[
\text{run} = (\text{case}, \kappa, \text{engine}, \text{iterations}) \rightarrow \text{terminal BPR and convergence label}
\]

where \(\kappa\) is `repair_condition` and the engine is `model_name` (or null when no inference is performed).

Multiple runs per case are expected (different conditions, sensitivity engines). Do not merge conditions into a single run file.

## Archival layout

```
results/frozen_runs/
  <input_case_id>__<repair_condition>__<model_slug>.json
```

Example filename: `tlc_01__patch_trace_feedback__llama3_8b.json`

Use a stable `model_slug` derived from `model_name` (lowercase, non-alphanumeric → `_`). For `baseline_no_repair`, omit the model suffix: `tlc_01__baseline_no_repair.json`.

## Required fields

| Field | Type | Description |
|-------|------|-------------|
| `schema_version` | string | Schema semver (e.g. `1.0.0`). |
| `run_id` | string | Unique run slug (may equal filename stem). |
| `timestamp` | ISO 8601 | UTC time when the run completed or was frozen. |
| `model_name` | string \| null | Engine tag; **null** for `baseline_no_repair`. |
| `repair_condition` | enum | Primary IV; see `environment/conditions.yaml`. |
| `iteration_number` | integer ≥ 0 | Count of repair iterations executed. |
| `input_case_id` | string | Links to `datasets/repair_cases/<id>/`. |
| `input_bpr` | number ∈ [0,1] | BPR at run entry (\(M_0\)). |
| `output_bpr` | number ∈ [0,1] | BPR of terminal candidate. |
| `patch_count` | integer ≥ 0 | Number of patch **files** applied. |
| `patch_size` | integer ≥ 0 | Sum of `operations` lengths across all patches. |
| `regression_detected` | boolean | True if any iteration decreased BPR vs. prior. |
| `convergence_status` | enum | Process outcome (see below). |

### Derived quantities

- **BPR delta:** \(\texttt{output\_bpr} - \texttt{input\_bpr}\) (store optionally as `bpr_delta`).
- **Repair success:** `output_bpr == 1` and `convergence_status == "success"`.

Definitions: [`repairability_definition.md`](repairability_definition.md).

## `convergence_status` values

| Value | When to use |
|-------|-------------|
| `success` | Terminal `output_bpr == 1`. |
| `partial_improvement` | `output_bpr > input_bpr` and `output_bpr < 1`. |
| `no_improvement` | `output_bpr == input_bpr` and run ended without success. |
| `plateau` | BPR unchanged for ≥ 2 consecutive iterations before stop, below 1. |
| `oscillating` | BPR strictly increases and decreases across iterations. |
| `regression_terminal` | `output_bpr < input_bpr` at termination. |
| `budget_exhausted` | Iteration limit reached without `success`. |
| `aborted` | Run stopped by error or invalid artefact. |
| `not_applicable` | `baseline_no_repair` (evaluation only, `iteration_number == 0`). |

`final_status` (optional) aligns with repair case outcomes: `success`, `partial`, `failed`, `budget_exhausted`, `aborted`, `regression_terminal`, `not_applicable`.

## `patch_count` vs `patch_size`

- **`patch_count`** — Cardinality of patch documents (one per repair iteration in typical patch conditions).
- **`patch_size`** — Total operation count: \(\sum_i |\texttt{operations}(P_i)|\) over applied patches. Matches **edit cost** in the repairability definition.

Example: two patches with 3 and 1 operations → `patch_count: 2`, `patch_size: 4`.

## Optional fields (recommended at Zenodo freeze)

| Field | Purpose |
|-------|---------|
| `started_at` | Run start time for duration analysis. |
| `attempt_budget` | Protocol cap on iterations. |
| `oracle_suite_id` | Suite used for all BPR values in the run. |
| `patch_paths` | Ordered relative paths to patch JSON files. |
| `output_candidate_path` | Terminal FSM snapshot path. |
| `iterations` | Per-iteration BPR trajectory and regression flags. |
| `checksums` | SHA-256 of run file and output FSM. |
| `provenance` | Bundle id, engine runtime version, short notes. |

## Relationship to repair cases

| Repair case | Repair run |
|-------------|------------|
| Frozen entry snapshot (`initial_bpr`, diagnostics) | Executes protocol; may update case `repair_history` / `final_*` at study export |
| One case, many conditions | One run per (case, condition, engine) |
| `case_id` | Recorded as `input_case_id` on the run |

## Example 1 — Baseline, no repair (`not_applicable`)

Evaluation only; no patches; no engine.

```json
{
  "schema_version": "1.0.0",
  "run_id": "tlc_01__baseline_no_repair",
  "timestamp": "2026-06-03T10:00:00Z",
  "model_name": null,
  "repair_condition": "baseline_no_repair",
  "iteration_number": 0,
  "input_case_id": "tlc_01",
  "input_bpr": 0.25,
  "output_bpr": 0.25,
  "patch_count": 0,
  "patch_size": 0,
  "regression_detected": false,
  "convergence_status": "not_applicable",
  "bpr_delta": 0.0,
  "attempt_budget": 0,
  "oracle_suite_id": "tlc_oracle_v1",
  "final_status": "not_applicable"
}
```

## Example 2 — Successful patch repair (`success`)

Two iterations, trace feedback, local engine tag.

```json
{
  "schema_version": "1.0.0",
  "run_id": "tlc_01__patch_trace_feedback__llama3_8b",
  "timestamp": "2026-06-03T14:05:00Z",
  "started_at": "2026-06-03T14:01:00Z",
  "model_name": "llama3:8b",
  "repair_condition": "patch_trace_feedback",
  "iteration_number": 2,
  "input_case_id": "tlc_01",
  "input_bpr": 0.25,
  "output_bpr": 1.0,
  "patch_count": 2,
  "patch_size": 4,
  "regression_detected": false,
  "convergence_status": "success",
  "bpr_delta": 0.75,
  "attempt_budget": 5,
  "oracle_suite_id": "tlc_oracle_v1",
  "final_status": "success",
  "patch_paths": [
    "patches/iter_00.json",
    "patches/iter_01.json"
  ],
  "output_candidate_path": "candidates/iter_01.json",
  "iterations": [
    {
      "iteration": 0,
      "bpr_before": 0.25,
      "bpr_after": 0.5,
      "oracle_passed_all": false,
      "regression": false,
      "patch_id": "tlc_01_iter_00",
      "patch_path": "patches/iter_00.json",
      "patch_operation_count": 3
    },
    {
      "iteration": 1,
      "bpr_before": 0.5,
      "bpr_after": 1.0,
      "oracle_passed_all": true,
      "regression": false,
      "patch_id": "tlc_01_iter_01",
      "patch_path": "patches/iter_01.json",
      "patch_operation_count": 1
    }
  ],
  "checksums": {
    "output_candidate_sha256": "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789"
  },
  "provenance": {
    "artifact_bundle": "fsm-repairability-study-v0.1.0",
    "engine_runtime": "ollama/0.1.0",
    "notes": "Primary engine run for main analysis table."
  }
}
```

## Example 3 — Partial repair, budget exhausted

```json
{
  "schema_version": "1.0.0",
  "run_id": "turnstile_07__patch_binary_feedback__mistral_7b",
  "timestamp": "2026-06-04T09:30:00Z",
  "model_name": "mistral:7b",
  "repair_condition": "patch_binary_feedback",
  "iteration_number": 5,
  "input_case_id": "turnstile_07",
  "input_bpr": 0.0,
  "output_bpr": 0.5,
  "patch_count": 5,
  "patch_size": 7,
  "regression_detected": false,
  "convergence_status": "budget_exhausted",
  "bpr_delta": 0.5,
  "attempt_budget": 5,
  "oracle_suite_id": "turnstile_oracle_v1",
  "final_status": "partial"
}
```

## Example 4 — Regression detected mid-run, terminal regression

```json
{
  "schema_version": "1.0.0",
  "run_id": "vending_03__patch_localized_feedback__qwen2_5_7b",
  "timestamp": "2026-06-04T11:00:00Z",
  "model_name": "qwen2.5:7b",
  "repair_condition": "patch_localized_feedback",
  "iteration_number": 1,
  "input_case_id": "vending_03",
  "input_bpr": 0.5,
  "output_bpr": 0.0,
  "patch_count": 1,
  "patch_size": 2,
  "regression_detected": true,
  "convergence_status": "regression_terminal",
  "bpr_delta": -0.5,
  "attempt_budget": 5,
  "oracle_suite_id": "vending_oracle_v1",
  "final_status": "regression_terminal",
  "iterations": [
    {
      "iteration": 0,
      "bpr_before": 0.5,
      "bpr_after": 0.0,
      "oracle_passed_all": false,
      "regression": true,
      "patch_operation_count": 2
    }
  ]
}
```

## Example 5 — Full regeneration baseline

One regeneration iteration; `patch_count` may be 0 if the engine emits a full FSM file rather than a patch document.

```json
{
  "schema_version": "1.0.0",
  "run_id": "tlc_01__baseline_full_regeneration__llama3_8b",
  "timestamp": "2026-06-03T15:00:00Z",
  "model_name": "llama3:8b",
  "repair_condition": "baseline_full_regeneration",
  "iteration_number": 1,
  "input_case_id": "tlc_01",
  "input_bpr": 0.25,
  "output_bpr": 0.75,
  "patch_count": 0,
  "patch_size": 0,
  "regression_detected": false,
  "convergence_status": "partial_improvement",
  "bpr_delta": 0.5,
  "attempt_budget": 1,
  "oracle_suite_id": "tlc_oracle_v1",
  "final_status": "partial",
  "output_candidate_path": "candidates/regenerated_00.json",
  "provenance": {
    "notes": "Baseline comparison; not patch-based repair."
  }
}
```

## Validation and versioning

- Validate with JSON Schema and a local registry including sibling schemas.
- Bump `schema_version` on incompatible changes; retain migration notes in release documentation.
- At Zenodo deposit, include a manifest listing all `run_id`, file paths, and checksums.

## Analysis use

- **Condition contrasts:** aggregate `output_bpr`, `convergence_status`, and repair rate by `repair_condition`.
- **Sensitivity:** stratify by `model_name` only as supplementary analysis.
- **Cost:** correlate `patch_count`, `patch_size`, and `iteration_number` with \(\Delta\)BPR.

## See also

- [`repair_case_format.md`](repair_case_format.md)
- [`repairability_definition.md`](repairability_definition.md)
- [`experimental_setup.md`](experimental_setup.md)
- [`results/frozen_runs/README.md`](../results/frozen_runs/README.md)
