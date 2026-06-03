# Experimental unit: repair case

The **repair case** is the fundamental **observation** in the behavioural repairability study. Each case fixes one structurally valid, behaviourally deficient candidate FSM, frozen requirements, separated oracle roles, a complete **repair history**, and a **terminal outcome** suitable for statistical analysis and Zenodo archival.

Formal metrics (BPR, regression, overfitting) are defined in [`repairability_definition.md`](repairability_definition.md). Machine validation: [`schemas/repair_case.schema.json`](../schemas/repair_case.schema.json) (**version 2.0.0**).

## Scientific role

| Concept | Role |
|---------|------|
| **Population** | Set of eligible repair cases \(\mathcal{C}\) |
| **Observation** | One case record (not one patch, not one oracle check) |
| **Primary IV** | Applied at **run** level (`repair_condition` in [`repair_run`](repair_run_format.md)); case stores **history** of conditioned iterations |
| **Outcomes** | `final_bpr`, `repair_status`, `regression_detected`, `overfitting_detected` on **validation oracles** |

Cases are **not** independent replicates of the same protocol unless the analysis plan defines repeated runs per case; the default unit is **one case manifest per (case, condition, engine) export** or a merged history per pre-registered convention.

## Design principles (scale and Zenodo)

1. **Path externalisation** — At thousands of cases, embed FSMs only in tiny fixtures; default to `candidate_fsm` / `reference_fsm` as **relative paths** inside the case directory.
2. **Campaign partitioning** — `campaign_id` supports sharded storage: `datasets/repair_cases/<campaign_id>/<case_id>/`.
3. **Oracle separation** — `feedback_oracles` vs `validation_oracles` prevents conflating repair guidance with confirmatory measurement ([`experimental_conditions.md`](experimental_conditions.md)).
4. **Immutable baseline** — `baseline.*` and entry `diagnostics.*` are frozen at case construction; they are not overwritten by repair.
5. **Append-only history** — `repair_history` grows by iterations; `intermediate_bpr` is a dense BPR trace on validation oracles (index 0 = initial).
6. **Archival block** — `archival.checksums` and timestamps support long-term integrity without recomputation.

## Record structure

```
repair_case (case.json)
├── schema_version
├── identity          case_id, system_id, campaign_id
├── inputs            requirement_text, candidate_fsm, reference_fsm
├── baseline          initial_bpr, initial_component_metrics
├── oracles           feedback_oracles, validation_oracles
├── diagnostics       missing_transitions, extra_transitions, failure_summary
├── repair_history    iterations, applied_patches, intermediate_bpr
├── final_outcome     final_bpr, repair_status, regression_detected, overfitting_detected
├── admission         (optional eligibility flags)
└── archival          (optional Zenodo metadata)
```

## Section specifications

### Identity

| Field | Purpose |
|-------|---------|
| `case_id` | Unique key; equals directory name. |
| `system_id` | Stratification by behavioural system (traffic light, turnstile, …). |
| `campaign_id` | Batch that produced or exported candidates (generation campaign, not repair condition). |

Enables joins: `campaign_id` → generation manifest; `case_id` → `repair_run.input_case_id`.

### Inputs

| Field | Purpose |
|-------|---------|
| `requirement_text` | Frozen NL specification. |
| `candidate_fsm` | \(M_0\) at study entry. |
| `reference_fsm` | Reference machine for structural diagnostics (not necessarily identical to validation oracle ground truth). |

### Baseline

| Field | Purpose |
|-------|---------|
| `initial_bpr` | \(\mathrm{BPR}(M_0, \mathcal{O}_{\mathrm{validation}})\). |
| `initial_component_metrics` | Per-check pass/fail on **validation** oracles; supports component-level analysis beyond scalar BPR. |

Eligibility: `initial_bpr < 1` (documented in `admission`).

### Oracles (separation)

| Binding | Role |
|---------|------|
| `feedback_oracles` | Checks allowed to shape prompts between iterations (subset permitted). |
| `validation_oracles` | **Authoritative** suite for BPR in `intermediate_bpr` and `final_bpr`. |

When suites share a file, differ by `check_ids`. For overfitting detection: compare feedback-driven gains vs validation `component_metrics` ([`repairability_definition.md`](repairability_definition.md) §7).

### Diagnostics (entry snapshot)

Structural comparison **candidate vs reference** at freeze time:

- `missing_transitions` — in reference, absent in candidate.
- `extra_transitions` — in candidate, absent in reference.
- `failure_summary` — short frozen narrative of behavioural failures.

Not updated after repair; per-iteration failures belong in `repair_history.iterations`.

### Repair history

| Field | Purpose |
|-------|---------|
| `iterations[]` | One record per repair iteration (condition, BPR delta, patch path, regression flag). |
| `applied_patches[]` | Ordered list of patch JSON paths (audit trail). |
| `intermediate_bpr[]` | \( \mathrm{BPR}_0, \mathrm{BPR}_1, \ldots \) on **validation** oracles; `intermediate_bpr[0] == baseline.initial_bpr`. |

Supports multiple attempts, multiple conditions (each iteration tags `repair_condition`), and reconstruction of repair trajectories without raw engine logs.

### Final outcome

| Field | Purpose |
|-------|---------|
| `final_bpr` | Terminal validation BPR; `null` if `repair_status == not_started`. |
| `repair_status` | Categorical outcome (success, partial, failed, …). |
| `regression_detected` | Any iteration with strictly decreasing validation BPR. |
| `overfitting_detected` | Feedback-suite improvement without validation improvement (operational rule in analysis plan). |

## Directory layout (recommended at scale)

```
datasets/repair_cases/
  <campaign_id>/
    <case_id>/
      case.json
      candidate_fsm.json
      reference_fsm.json
      patches/
        iter_000.json
      candidates/
        iter_000.json
```

For small public samples, flat `datasets/repair_cases/<case_id>/` remains valid if `campaign_id` is still set in the manifest.

## JSON example 1 — Case at study entry (`not_started`)

```json
{
  "schema_version": "2.0.0",
  "identity": {
    "case_id": "tlc_01",
    "system_id": "traffic_light_controller",
    "campaign_id": "gen_2026_q2_batch_a"
  },
  "inputs": {
    "requirement_text": "The controller cycles green, yellow, and red on tick. Initial state is green.",
    "candidate_fsm": "candidate_fsm.json",
    "reference_fsm": "reference_fsm.json"
  },
  "baseline": {
    "initial_bpr": 0.25,
    "initial_component_metrics": {
      "suite_id": "tlc_validation_v1",
      "total_count": 4,
      "passed_count": 1,
      "failed_count": 3,
      "checks": [
        { "check_id": "initial_state_green", "passed": true, "check_type": "state" },
        { "check_id": "trace_yellow_sequence", "passed": false, "check_type": "trace", "summary": "Skips yellow" },
        { "check_id": "trace_red_return", "passed": false, "check_type": "trace" },
        { "check_id": "forbidden_skip_yellow", "passed": false, "check_type": "trace" }
      ]
    }
  },
  "oracles": {
    "feedback_oracles": {
      "suite_id": "tlc_feedback_v1",
      "check_ids": ["trace_yellow_sequence", "trace_red_return", "forbidden_skip_yellow"]
    },
    "validation_oracles": {
      "suite_id": "tlc_validation_v1"
    }
  },
  "diagnostics": {
    "missing_transitions": [
      { "from": "s_green", "event": "tick", "to": "s_yellow" }
    ],
    "extra_transitions": [
      { "from": "s_green", "event": "tick", "to": "s_red" }
    ],
    "failure_summary": "Candidate skips yellow; three validation checks fail, one structural check passes."
  },
  "repair_history": {
    "iterations": [],
    "applied_patches": [],
    "intermediate_bpr": [0.25]
  },
  "final_outcome": {
    "final_bpr": null,
    "repair_status": "not_started",
    "regression_detected": false,
    "overfitting_detected": false
  },
  "admission": {
    "structurally_valid": true,
    "eligible_for_repair_study": true,
    "initial_bpr_below_one": true
  },
  "archival": {
    "created_at": "2026-06-03T10:00:00Z",
    "checksums": {
      "candidate_fsm_sha256": "a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456",
      "reference_fsm_sha256": "fedcba0987654321fedcba0987654321fedcba0987654321fedcba0987654321"
    }
  }
}
```

## JSON example 2 — Successful repair (two iterations)

After a completed run under `patch_trace_feedback` (history may be merged into the case at export).

```json
{
  "schema_version": "2.0.0",
  "identity": {
    "case_id": "tlc_01",
    "system_id": "traffic_light_controller",
    "campaign_id": "gen_2026_q2_batch_a"
  },
  "inputs": {
    "requirement_text": "The controller cycles green, yellow, and red on tick. Initial state is green.",
    "candidate_fsm": "candidate_fsm.json",
    "reference_fsm": "reference_fsm.json"
  },
  "baseline": {
    "initial_bpr": 0.25,
    "initial_component_metrics": {
      "suite_id": "tlc_validation_v1",
      "total_count": 4,
      "passed_count": 1,
      "failed_count": 3,
      "checks": [
        { "check_id": "initial_state_green", "passed": true },
        { "check_id": "trace_yellow_sequence", "passed": false },
        { "check_id": "trace_red_return", "passed": false },
        { "check_id": "forbidden_skip_yellow", "passed": false }
      ]
    }
  },
  "oracles": {
    "feedback_oracles": { "suite_id": "tlc_feedback_v1" },
    "validation_oracles": { "suite_id": "tlc_validation_v1" }
  },
  "diagnostics": {
    "missing_transitions": [{ "from": "s_green", "event": "tick", "to": "s_yellow" }],
    "extra_transitions": [{ "from": "s_green", "event": "tick", "to": "s_red" }],
    "failure_summary": "Entry: skip-yellow failure (frozen at case construction)."
  },
  "repair_history": {
    "iterations": [
      {
        "iteration_index": 0,
        "repair_condition": "patch_trace_feedback",
        "run_id": "tlc_01__patch_trace_feedback__run_001",
        "bpr_before": 0.25,
        "bpr_after": 0.5,
        "validation_passed_all": false,
        "feedback_checks_used": ["trace_yellow_sequence"],
        "patch_path": "patches/iter_000.json",
        "candidate_fsm_after": "candidates/iter_000.json",
        "regression": false,
        "timestamp": "2026-06-03T14:01:00Z"
      },
      {
        "iteration_index": 1,
        "repair_condition": "patch_trace_feedback",
        "run_id": "tlc_01__patch_trace_feedback__run_001",
        "bpr_before": 0.5,
        "bpr_after": 1.0,
        "validation_passed_all": true,
        "feedback_checks_used": ["trace_red_return"],
        "patch_path": "patches/iter_001.json",
        "candidate_fsm_after": "candidates/iter_001.json",
        "regression": false,
        "timestamp": "2026-06-03T14:02:30Z"
      }
    ],
    "applied_patches": ["patches/iter_000.json", "patches/iter_001.json"],
    "intermediate_bpr": [0.25, 0.5, 1.0]
  },
  "final_outcome": {
    "final_bpr": 1.0,
    "repair_status": "success",
    "regression_detected": false,
    "overfitting_detected": false,
    "final_component_metrics": {
      "suite_id": "tlc_validation_v1",
      "total_count": 4,
      "passed_count": 4,
      "failed_count": 0,
      "checks": [
        { "check_id": "initial_state_green", "passed": true },
        { "check_id": "trace_yellow_sequence", "passed": true },
        { "check_id": "trace_red_return", "passed": true },
        { "check_id": "forbidden_skip_yellow", "passed": true }
      ]
    }
  },
  "archival": {
    "frozen_at": "2026-06-03T14:05:00Z",
    "zenodo_bundle": "fsm-repairability-study-v0.1.0"
  }
}
```

## JSON example 3 — Partial repair with regression flag

```json
{
  "schema_version": "2.0.0",
  "identity": {
    "case_id": "vending_03",
    "system_id": "vending_machine",
    "campaign_id": "gen_2026_q2_batch_b"
  },
  "inputs": {
    "requirement_text": "Accept coin, dispense on select, return to idle.",
    "candidate_fsm": "candidate_fsm.json",
    "reference_fsm": "reference_fsm.json"
  },
  "baseline": {
    "initial_bpr": 0.5,
    "initial_component_metrics": {
      "suite_id": "vending_validation_v1",
      "total_count": 2,
      "passed_count": 1,
      "failed_count": 1,
      "checks": [
        { "check_id": "idle_initial", "passed": true },
        { "check_id": "dispense_trace", "passed": false }
      ]
    }
  },
  "oracles": {
    "feedback_oracles": {
      "suite_id": "vending_feedback_v1",
      "check_ids": ["dispense_trace"]
    },
    "validation_oracles": { "suite_id": "vending_validation_v1" }
  },
  "diagnostics": {
    "missing_transitions": [],
    "extra_transitions": [
      { "from": "dispensing", "event": "coin", "to": "idle", "note": "Spurious reset" }
    ],
    "failure_summary": "Dispense trace fails; spurious coin transition from dispensing."
  },
  "repair_history": {
    "iterations": [
      {
        "iteration_index": 0,
        "repair_condition": "patch_localized_feedback",
        "bpr_before": 0.5,
        "bpr_after": 0.0,
        "validation_passed_all": false,
        "patch_path": "patches/iter_000.json",
        "regression": true
      }
    ],
    "applied_patches": ["patches/iter_000.json"],
    "intermediate_bpr": [0.5, 0.0]
  },
  "final_outcome": {
    "final_bpr": 0.0,
    "repair_status": "regression_terminal",
    "regression_detected": true,
    "overfitting_detected": false
  }
}
```

## JSON example 4 — Overfitting signal (illustrative)

Feedback checks pass; validation BPR unchanged — flag for qualitative review.

```json
{
  "schema_version": "2.0.0",
  "identity": {
    "case_id": "sensor_12",
    "system_id": "sensor_arbiter",
    "campaign_id": "gen_2026_q2_batch_a"
  },
  "inputs": {
    "requirement_text": "Arbitrate sensor requests without starvation.",
    "candidate_fsm": "candidate_fsm.json",
    "reference_fsm": "reference_fsm.json"
  },
  "baseline": {
    "initial_bpr": 0.2,
    "initial_component_metrics": {
      "suite_id": "sensor_validation_v1",
      "total_count": 5,
      "passed_count": 1,
      "failed_count": 4,
      "checks": [
        { "check_id": "c1", "passed": true },
        { "check_id": "c2", "passed": false },
        { "check_id": "c3", "passed": false },
        { "check_id": "c4", "passed": false },
        { "check_id": "c5", "passed": false }
      ]
    }
  },
  "oracles": {
    "feedback_oracles": { "suite_id": "sensor_feedback_v1", "check_ids": ["c2"] },
    "validation_oracles": { "suite_id": "sensor_validation_v1" }
  },
  "diagnostics": {
    "missing_transitions": [],
    "extra_transitions": [],
    "failure_summary": "Multiple validation failures; localized feedback targets c2 only."
  },
  "repair_history": {
    "iterations": [
      {
        "iteration_index": 0,
        "repair_condition": "patch_localized_feedback",
        "bpr_before": 0.2,
        "bpr_after": 0.2,
        "validation_passed_all": false,
        "feedback_checks_used": ["c2"],
        "patch_path": "patches/iter_000.json",
        "regression": false
      }
    ],
    "applied_patches": ["patches/iter_000.json"],
    "intermediate_bpr": [0.2, 0.2]
  },
  "final_outcome": {
    "final_bpr": 0.2,
    "repair_status": "failed",
    "regression_detected": false,
    "overfitting_detected": true
  }
}
```

## Relationship to repair runs

| Artefact | Granularity |
|----------|-------------|
| **Repair case** | One observation unit; cumulative validation BPR trace and diagnostics. |
| **Repair run** | One protocol execution (case × condition × engine); maps to `run_id` on iterations. |

Export policy: either append iterations from each `repair_run` into the case, or deposit runs separately and aggregate at analysis time—state explicitly in `results/MANIFEST.md`.

## Analysis mapping

| Research question | Case fields |
|-------------------|-------------|
| Repair rate | `final_outcome.repair_status`, `final_bpr` |
| \(\Delta\)BPR | `final_bpr - baseline.initial_bpr` |
| Repair cost | `len(repair_history.iterations)`, `len(applied_patches)`, patch op counts (external) |
| Feedback effect | Stratify by `iterations[].repair_condition` |
| Regression | `final_outcome.regression_detected` |
| Overfitting | `final_outcome.overfitting_detected` |

## Migration from schema 1.0.0

Schema 1.x flat fields (`gold_fsm_path`, `oracle_suite_id`, `final_status`) are superseded by nested sections. Conversion scripts are out of scope here; see release notes when migrating corpora.

## See also

- [`repair_case_format.md`](repair_case_format.md) — legacy field guide (deprecated layout)
- [`repair_run_format.md`](repair_run_format.md)
- [`experimental_conditions.md`](experimental_conditions.md)
- [`DATA_STATEMENT.md`](../DATA_STATEMENT.md)
