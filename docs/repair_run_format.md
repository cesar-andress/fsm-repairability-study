# Repair run file format

A **repair run** is one **execution** of one **repair condition** on one **repair case**. It records iteration-level evidence, terminal outcomes on separated feedback and validation oracles, execution cost, and reproducibility metadata for Zenodo archival.

**Schema:** [`schemas/repair_run.schema.json`](../schemas/repair_run.schema.json) version **2.0.0**.

**Related:** [`experimental_unit.md`](experimental_unit.md) (case observation), [`experimental_conditions.md`](experimental_conditions.md) (condition definitions), [`local_model_execution.md`](local_model_execution.md) (engine backend).

## One record, one execution

\[
\text{run} = (\text{case\_id}, \kappa, \text{engine}) \rightarrow \{\text{iterations}\} \rightarrow \text{outcome}
\]

- **Repeated runs:** distinct `run_id` (use `identity.run_sequence` or timestamp suffix).
- **Multiple conditions:** separate files per `execution.repair_condition`.
- **Multiple engines:** separate files per `execution.model_name` (sensitivity only in main analysis).

Do not merge conditions or engines into one run document.

## Archival layout

```
results/frozen_runs/
  <case_id>/
    <repair_condition>/
      <run_id>.json
```

Example: `results/frozen_runs/tlc_01/patch_trace_feedback/tlc_01__patch_trace_feedback__r001.json`

Paths inside the run file are **relative to the run file directory** (or a documented run root prefix in `results/MANIFEST.md`).

## Record sections

| Section | Purpose |
|---------|---------|
| `schema_version` | Semver (top-level, duplicated in docs with identity block). |
| `identity` | `run_id`, `case_id`, `system_id`, optional `run_sequence` |
| `execution` | Condition, engine, timing, decoding controls |
| `inputs` | Case path, initial candidate, oracle set ids |
| `iterations` | Per-iteration audit trail |
| `outcome` | Terminal FSM, BPRs, `outcome_class`, boolean flags |
| `cost` | Tokens, wall time, oracle calls, patch ops |
| `reproducibility` | Git version, command, checksums |

## Dual BPR tracking

Each iteration and the outcome record separate:

| Field | Oracle set |
|-------|------------|
| `*_bpr_feedback` | `inputs.feedback_oracle_set_id` |
| `*_bpr_validation` | `inputs.validation_oracle_set_id` |

**Published conclusions** use **validation** BPR only. Feedback BPR supports overfitting analysis (`overfitting_detected` when feedback improves without validation improvement).

## `outcome_class` values

| Value | Meaning |
|-------|---------|
| `complete_repair` | `final_bpr_validation == 1` |
| `effective_repair` | Validation BPR strictly increased, but `< 1` |
| `no_improvement` | Terminal validation BPR equals run-start validation BPR |
| `behavioural_degradation` | Terminal validation BPR below run-start |
| `invalid_patch` | Engine output could not be validated as a patch |
| `structurally_invalid_output` | Output fails FSM structural checks |
| `non_convergent` | Plateau or oscillation per protocol rules |
| `execution_error` | Engine or infrastructure failure |
| `aborted` | Run stopped before protocol completion |

Boolean flags `outcome.complete_repair`, `outcome.effective_repair`, and `outcome.behavioural_degradation` provide redundant encodings for analysis scripts.

## Iteration fields

Every iteration documents the **full loop**: score → feedback artefact → generate patch → apply → re-score.

| Field | Role |
|-------|------|
| `input_candidate_path` / `output_candidate_path` | FSM snapshots |
| `input_bpr_*` / `output_bpr_*` | BPR before and after the iteration |
| `feedback_summary_path` | Frozen feedback (JSON or text) |
| `generated_patch_path` | Patch proposal (null if none) |
| `patch_valid` / `patch_applied` | Validation and application status |
| `regression_detected` | Validation BPR decreased |
| `overfitting_detected` | Feedback up, validation not up |
| `error_type` / `error_message` | `none` and empty string if no error |

## Reproducibility block

| Field | Role |
|-------|------|
| `code_version` | Git commit or release tag |
| `command` | Exact invocation |
| `environment_id` | Frozen hardware/software profile |
| `input_checksums` | Named SHA-256 at run start |
| `output_checksums` | Named SHA-256 at run end |

## Example 1 — Baseline: no repair (`baseline_no_repair`)

No engine; empty `iterations`; evaluation-only outcome.

```json
{
  "schema_version": "2.0.0",
  "identity": {
    "run_id": "tlc_01__baseline_no_repair__r001",
    "case_id": "tlc_01",
    "system_id": "traffic_light_controller",
    "run_sequence": 1
  },
  "execution": {
    "repair_condition": "baseline_no_repair",
    "model_name": null,
    "model_digest": null,
    "execution_backend": "none",
    "started_at": "2026-06-03T10:00:00Z",
    "completed_at": "2026-06-03T10:00:05Z",
    "max_iterations": 0,
    "temperature": 0.0,
    "seed": null
  },
  "inputs": {
    "input_case_path": "../../../../datasets/repair_cases/gen_2026_q2_batch_a/tlc_01/case.json",
    "initial_candidate_path": "candidates/initial.json",
    "feedback_oracle_set_id": "tlc_feedback_v1",
    "validation_oracle_set_id": "tlc_validation_v1"
  },
  "iterations": [],
  "outcome": {
    "final_candidate_path": "candidates/initial.json",
    "final_bpr_feedback": 0.25,
    "final_bpr_validation": 0.25,
    "outcome_class": "no_improvement",
    "complete_repair": false,
    "effective_repair": false,
    "behavioural_degradation": false,
    "regression_detected": false,
    "overfitting_detected": false,
    "iterations_to_outcome": 0
  },
  "cost": {
    "prompt_tokens_estimated": 0,
    "completion_tokens_estimated": 0,
    "wall_time_seconds": 5.1,
    "oracle_executions": 2,
    "patch_operations_total": 0
  },
  "reproducibility": {
    "code_version": "a14e167",
    "command": "python scripts/run_repair_condition.py --case tlc_01 --condition baseline_no_repair",
    "environment_id": "workstation_rtx4090_v1",
    "input_checksums": {
      "case.json": "a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456",
      "initial_candidate.json": "fedcba0987654321fedcba0987654321fedcba0987654321fedcba0987654321"
    },
    "output_checksums": {
      "initial_candidate.json": "fedcba0987654321fedcba0987654321fedcba0987654321fedcba0987654321"
    }
  }
}
```

## Example 2 — Successful patch repair (two iterations)

```json
{
  "schema_version": "2.0.0",
  "identity": {
    "run_id": "tlc_01__patch_trace_feedback__r001",
    "case_id": "tlc_01",
    "system_id": "traffic_light_controller"
  },
  "execution": {
    "repair_condition": "patch_trace_feedback",
    "model_name": "llama3:8b",
    "model_digest": "sha256:abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
    "execution_backend": "ollama",
    "started_at": "2026-06-03T14:00:00Z",
    "completed_at": "2026-06-03T14:05:00Z",
    "max_iterations": 5,
    "temperature": 0.2,
    "seed": 42
  },
  "inputs": {
    "input_case_path": "../../../../datasets/repair_cases/gen_2026_q2_batch_a/tlc_01/case.json",
    "initial_candidate_path": "candidates/initial.json",
    "feedback_oracle_set_id": "tlc_feedback_v1",
    "validation_oracle_set_id": "tlc_validation_v1"
  },
  "iterations": [
    {
      "iteration_index": 0,
      "input_candidate_path": "candidates/initial.json",
      "input_bpr_feedback": 0.25,
      "input_bpr_validation": 0.25,
      "feedback_summary_path": "feedback/iter_000.json",
      "generated_patch_path": "patches/iter_000.json",
      "patch_valid": true,
      "patch_applied": true,
      "output_candidate_path": "candidates/iter_000.json",
      "output_bpr_feedback": 0.5,
      "output_bpr_validation": 0.5,
      "regression_detected": false,
      "overfitting_detected": false,
      "error_type": "none",
      "error_message": "",
      "patch_operation_count": 3
    },
    {
      "iteration_index": 1,
      "input_candidate_path": "candidates/iter_000.json",
      "input_bpr_feedback": 0.5,
      "input_bpr_validation": 0.5,
      "feedback_summary_path": "feedback/iter_001.json",
      "generated_patch_path": "patches/iter_001.json",
      "patch_valid": true,
      "patch_applied": true,
      "output_candidate_path": "candidates/iter_001.json",
      "output_bpr_feedback": 1.0,
      "output_bpr_validation": 1.0,
      "regression_detected": false,
      "overfitting_detected": false,
      "error_type": "none",
      "error_message": "",
      "patch_operation_count": 1
    }
  ],
  "outcome": {
    "final_candidate_path": "candidates/iter_001.json",
    "final_bpr_feedback": 1.0,
    "final_bpr_validation": 1.0,
    "outcome_class": "complete_repair",
    "complete_repair": true,
    "effective_repair": true,
    "behavioural_degradation": false,
    "regression_detected": false,
    "overfitting_detected": false,
    "iterations_to_outcome": 1
  },
  "cost": {
    "prompt_tokens_estimated": 4200,
    "completion_tokens_estimated": 380,
    "wall_time_seconds": 298.4,
    "oracle_executions": 8,
    "patch_operations_total": 4
  },
  "reproducibility": {
    "code_version": "a14e167",
    "command": "python scripts/run_repair_condition.py --case tlc_01 --condition patch_trace_feedback --model llama3:8b",
    "environment_id": "workstation_rtx4090_v1",
    "input_checksums": {
      "case.json": "a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456",
      "initial_candidate.json": "fedcba0987654321fedcba0987654321fedcba0987654321fedcba0987654321"
    },
    "output_checksums": {
      "final_candidate.json": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    },
    "zenodo_bundle": "fsm-repairability-study-v0.1.0"
  }
}
```

## Example 3 — Repeated run (same case, condition, engine)

Second replicate for robustness; different `run_id` and `run_sequence`.

```json
{
  "schema_version": "2.0.0",
  "identity": {
    "run_id": "tlc_01__patch_trace_feedback__r002",
    "case_id": "tlc_01",
    "system_id": "traffic_light_controller",
    "run_sequence": 2
  },
  "execution": {
    "repair_condition": "patch_trace_feedback",
    "model_name": "llama3:8b",
    "model_digest": "sha256:abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
    "execution_backend": "ollama",
    "started_at": "2026-06-04T09:00:00Z",
    "completed_at": "2026-06-04T09:04:30Z",
    "max_iterations": 5,
    "temperature": 0.2,
    "seed": 43
  },
  "inputs": {
    "input_case_path": "../../../../datasets/repair_cases/gen_2026_q2_batch_a/tlc_01/case.json",
    "initial_candidate_path": "candidates/initial.json",
    "feedback_oracle_set_id": "tlc_feedback_v1",
    "validation_oracle_set_id": "tlc_validation_v1"
  },
  "iterations": [],
  "outcome": {
    "final_candidate_path": "candidates/initial.json",
    "final_bpr_feedback": 0.25,
    "final_bpr_validation": 0.5,
    "outcome_class": "effective_repair",
    "complete_repair": false,
    "effective_repair": true,
    "behavioural_degradation": false,
    "regression_detected": false,
    "overfitting_detected": false,
    "iterations_to_outcome": 2
  },
  "cost": {
    "prompt_tokens_estimated": 5100,
    "completion_tokens_estimated": 410,
    "wall_time_seconds": 270.0,
    "oracle_executions": 10,
    "patch_operations_total": 5
  },
  "reproducibility": {
    "code_version": "a14e167",
    "command": "python scripts/run_repair_condition.py --case tlc_01 --condition patch_trace_feedback --model llama3:8b --seed 43",
    "environment_id": "workstation_rtx4090_v1",
    "input_checksums": {
      "case.json": "a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456"
    },
    "output_checksums": {
      "final_candidate.json": "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789"
    }
  }
}
```

*(Example 3 omits full `iterations` array for brevity; deposited runs must include complete iteration records.)*

## Example 4 — Execution error at iteration 0

```json
{
  "schema_version": "2.0.0",
  "identity": {
    "run_id": "vending_03__patch_binary_feedback__err01",
    "case_id": "vending_03",
    "system_id": "vending_machine"
  },
  "execution": {
    "repair_condition": "patch_binary_feedback",
    "model_name": "mistral:7b",
    "model_digest": "sha256:1111111111111111111111111111111111111111111111111111111111111111",
    "execution_backend": "ollama",
    "started_at": "2026-06-04T11:00:00Z",
    "completed_at": "2026-06-04T11:00:45Z",
    "max_iterations": 5,
    "temperature": 0.2,
    "seed": 42
  },
  "inputs": {
    "input_case_path": "../../../../datasets/repair_cases/gen_2026_q2_batch_b/vending_03/case.json",
    "initial_candidate_path": "candidates/initial.json",
    "feedback_oracle_set_id": "vending_feedback_v1",
    "validation_oracle_set_id": "vending_validation_v1"
  },
  "iterations": [
    {
      "iteration_index": 0,
      "input_candidate_path": "candidates/initial.json",
      "input_bpr_feedback": 0.5,
      "input_bpr_validation": 0.5,
      "feedback_summary_path": "feedback/iter_000.json",
      "generated_patch_path": null,
      "patch_valid": false,
      "patch_applied": false,
      "output_candidate_path": "candidates/initial.json",
      "output_bpr_feedback": 0.5,
      "output_bpr_validation": 0.5,
      "regression_detected": false,
      "overfitting_detected": false,
      "error_type": "parse_error",
      "error_message": "Engine response was not valid JSON.",
      "patch_operation_count": 0
    }
  ],
  "outcome": {
    "final_candidate_path": "candidates/initial.json",
    "final_bpr_feedback": 0.5,
    "final_bpr_validation": 0.5,
    "outcome_class": "execution_error",
    "complete_repair": false,
    "effective_repair": false,
    "behavioural_degradation": false,
    "regression_detected": false,
    "overfitting_detected": false,
    "iterations_to_outcome": 0
  },
  "cost": {
    "prompt_tokens_estimated": 800,
    "completion_tokens_estimated": 120,
    "wall_time_seconds": 45.0,
    "oracle_executions": 2,
    "patch_operations_total": 0
  },
  "reproducibility": {
    "code_version": "a14e167",
    "command": "python scripts/run_repair_condition.py --case vending_03 --condition patch_binary_feedback --model mistral:7b",
    "environment_id": "workstation_rtx4090_v1",
    "input_checksums": {
      "case.json": "2222222222222222222222222222222222222222222222222222222222222222"
    },
    "output_checksums": {
      "final_candidate.json": "3333333333333333333333333333333333333333333333333333333333333333"
    }
  }
}
```

## Mapping to repair case

After study export, selected fields from `repair_run` may be merged into `repair_case.repair_history` ([`experimental_unit.md`](experimental_unit.md)). The run file remains the authoritative **execution** record; the case file remains the authoritative **observation** for analysis.

## Migration from schema 1.0.0

Version 1.x used flat fields (`timestamp`, `input_case_id`, `convergence_status`). Version 2.0.0 nests sections and splits feedback vs validation BPR. Conversion tooling is deferred.

## See also

- [`repairability_definition.md`](repairability_definition.md)
- [`results/frozen_runs/README.md`](../results/frozen_runs/README.md)
- [`REPRODUCIBILITY.md`](../REPRODUCIBILITY.md)
