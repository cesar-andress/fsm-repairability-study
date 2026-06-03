# Repair case file format

A **repair case** is one experimental unit in the behavioural repairability study. It bundles a frozen requirement, a reference FSM, an initial structurally valid but behaviourally incorrect candidate, oracle linkage, structural diagnostics at entry, and—after experiments—an ordered repair history with terminal outcome.

Cases are stored as self-contained directories under `datasets/repair_cases/<case_id>/`. The manifest file `case.json` must validate against [`schemas/repair_case.schema.json`](../schemas/repair_case.schema.json).

Notation for BPR and repair outcomes aligns with [`repairability_definition.md`](repairability_definition.md).

## Design goals

1. **Long-term reproducibility** — Relative paths, explicit `schema_version`, optional SHA-256 checksums, frozen text and diagnostics (no reliance on live recomputation).
2. **Separation of concerns** — Gold reference, candidate, oracles, and per-iteration artefacts are separate files; the manifest references them.
3. **Condition-centric analysis** — `repair_history` records `condition_id` per iteration; the case file does not encode engine or model identity as a primary field.
4. **Audit without mutation** — Entry fields (`initial_bpr`, `failed_tests`, transition deltas) are fixed at case freeze; `repair_history` and `final_*` document post-study state.

## Directory layout

```
datasets/repair_cases/<case_id>/
  case.json                 # This manifest (required)
  gold_fsm.json             # Reference FSM (required)
  candidate_fsm.json        # Initial candidate M_0 (required)
  patches/                  # Optional: one file per applied patch
    iter_00.json
  candidates/               # Optional: snapshots after iterations
    iter_00.json
```

Paths in `case.json` are **relative to** `datasets/repair_cases/<case_id>/`. Do not use `..` segments.

## Field reference

| Field | Role |
|-------|------|
| `schema_version` | Schema semver (currently `1.0.0`). |
| `case_id` | Unique case slug; must match directory name. |
| `system_id` | Groups cases from the same behavioural system or task family. |
| `requirement_text` | Frozen natural-language requirement. |
| `gold_fsm_path` | Path to reference FSM used for structural comparison (not necessarily run against all oracles in public deposits). |
| `candidate_fsm_path` | Path to initial candidate \(M_0\). |
| `initial_bpr` | \(\mathrm{BPR}(M_0, \mathcal{O}_c)\) at entry; must be \(< 1\) for eligible cases. |
| `oracle_suite_id` | Id of `datasets/oracle_suites/<oracle_suite_id>.json`. |
| `failed_tests` | Oracle checks failing on \(M_0\). |
| `passed_tests` | Oracle checks passing on \(M_0\). |
| `missing_transitions` | Transitions in gold but missing in candidate. |
| `extra_transitions` | Transitions in candidate but not in gold. |
| `repair_history` | Ordered repair iterations (empty before any run). |
| `final_bpr` | Terminal BPR; `null` if `final_status` is `not_started`. |
| `final_status` | Terminal outcome label (see below). |

Optional fields: `structurally_valid` (must be `true`), `created_at`, `checksums`, `provenance`.

### `final_status` values

| Value | Meaning |
|-------|---------|
| `not_started` | Case frozen for study entry; no repair recorded. `repair_history` must be `[]`, `final_bpr` must be `null`. |
| `success` | \(\mathrm{BPR} = 1\) on authoritative suite within budget. |
| `partial` | Terminal \(\mathrm{BPR} \in ( \mathrm{initial\_bpr}, 1 )\). |
| `failed` | Terminal \(\mathrm{BPR} = \mathrm{initial\_bpr}\) (no improvement). |
| `budget_exhausted` | Budget spent without success (may overlap partial or failed). |
| `aborted` | Run stopped by protocol (error, invalid patch, etc.). |
| `regression_terminal` | Terminal \(\mathrm{BPR} < \mathrm{initial\_bpr}\). |

When multiple repair **conditions** are applied to the same case, prefer one `case.json` per condition-specific run bundle, or one history aggregating all iterations with distinct `condition_id` values—the analysis plan must state which convention is used.

### `repair_history` entries

Each element documents one **repair iteration** (score → feedback → transition):

| Subfield | Description |
|----------|-------------|
| `iteration` | Zero-based index. |
| `condition_id` | Repair condition (primary IV). |
| `run_id` | Optional link to a `repair_run` record. |
| `bpr_before`, `bpr_after` | BPR before and after the iteration (optional `bpr_before` on iteration 0). |
| `oracle_passed_all` | Whether all authoritative checks pass after the iteration. |
| `patch_path` | Path to patch JSON, if applicable. |
| `candidate_fsm_path_after` | Snapshot path after the iteration. |
| `failed_tests` | Failing checks after the iteration (optional). |
| `regression` | Whether \(\mathrm{BPR}\) decreased vs. the prior iteration. |

## Integrity and versioning

- Bump `schema_version` on incompatible manifest changes; document migrations in release notes.
- Record `checksums.gold_fsm_sha256` and `checksums.candidate_fsm_sha256` at freeze for Zenodo audit.
- `failed_tests` / `passed_tests` / transition lists are **snapshots** at case construction (or at stated iteration); re-scoring tools may recompute but must not overwrite frozen fields in deposited artefacts.

## Example 1 — Case at study entry (`not_started`)

Eligible case: traffic-light controller, one of four oracle checks already passes.

**Directory:** `datasets/repair_cases/tlc_01/`

**`case.json`:**

```json
{
  "schema_version": "1.0.0",
  "case_id": "tlc_01",
  "system_id": "traffic_light_controller",
  "requirement_text": "The controller cycles green, yellow, and red on events tick. Initial state is green. Each signal lasts one tick before transitioning.",
  "gold_fsm_path": "gold_fsm.json",
  "candidate_fsm_path": "candidate_fsm.json",
  "initial_bpr": 0.25,
  "oracle_suite_id": "tlc_oracle_v1",
  "failed_tests": [
    { "check_id": "trace_yellow_sequence", "check_type": "trace", "summary": "Expected s_green->s_yellow; observed s_green->s_red" },
    { "check_id": "trace_red_return", "check_type": "trace", "summary": "Missing return to s_green after s_red" },
    { "check_id": "forbidden_skip_yellow", "check_type": "trace", "summary": "Yellow state unreachable" }
  ],
  "passed_tests": [
    { "check_id": "initial_state_green", "check_type": "state", "summary": "Initial state matches" }
  ],
  "missing_transitions": [
    { "from": "s_green", "event": "tick", "to": "s_yellow", "note": "Candidate routes green->red" }
  ],
  "extra_transitions": [
    { "from": "s_green", "event": "tick", "to": "s_red" }
  ],
  "repair_history": [],
  "final_bpr": null,
  "final_status": "not_started",
  "structurally_valid": true,
  "created_at": "2026-06-03T12:00:00Z",
  "checksums": {
    "gold_fsm_sha256": "a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456",
    "candidate_fsm_sha256": "fedcba0987654321fedcba0987654321fedcba0987654321fedcba0987654321"
  },
  "provenance": {
    "candidate_origin": "exported_generation",
    "notes": "Structurally validated; BPR computed against tlc_oracle_v1 at freeze."
  }
}
```

Here \(|\mathcal{O}_c| = 4\) and \(\mathrm{initial\_bpr} = 1/4 = 0.25\), consistent with one entry in `passed_tests` and three in `failed_tests`.

## Example 2 — Successful repair after two patch iterations

Same case after a completed run under `patch_trace_feedback` (history abbreviated for readability).

**`case.json` (excerpt — terminal state):**

```json
{
  "schema_version": "1.0.0",
  "case_id": "tlc_01",
  "system_id": "traffic_light_controller",
  "requirement_text": "The controller cycles green, yellow, and red on events tick. Initial state is green. Each signal lasts one tick before transitioning.",
  "gold_fsm_path": "gold_fsm.json",
  "candidate_fsm_path": "candidate_fsm.json",
  "initial_bpr": 0.25,
  "oracle_suite_id": "tlc_oracle_v1",
  "failed_tests": [
    { "check_id": "trace_yellow_sequence", "check_type": "trace" },
    { "check_id": "trace_red_return", "check_type": "trace" },
    { "check_id": "forbidden_skip_yellow", "check_type": "trace" }
  ],
  "passed_tests": [
    { "check_id": "initial_state_green", "check_type": "state" }
  ],
  "missing_transitions": [
    { "from": "s_green", "event": "tick", "to": "s_yellow" }
  ],
  "extra_transitions": [
    { "from": "s_green", "event": "tick", "to": "s_red" }
  ],
  "repair_history": [
    {
      "iteration": 0,
      "condition_id": "patch_trace_feedback",
      "run_id": "tlc_01__patch_trace_feedback__run_20260603",
      "bpr_before": 0.25,
      "bpr_after": 0.5,
      "oracle_passed_all": false,
      "patch_path": "patches/iter_00.json",
      "candidate_fsm_path_after": "candidates/iter_00.json",
      "failed_tests": [
        { "check_id": "trace_red_return", "summary": "Still failing" },
        { "check_id": "forbidden_skip_yellow", "summary": "Still failing" }
      ],
      "regression": false,
      "timestamp": "2026-06-03T14:01:00Z"
    },
    {
      "iteration": 1,
      "condition_id": "patch_trace_feedback",
      "run_id": "tlc_01__patch_trace_feedback__run_20260603",
      "bpr_before": 0.5,
      "bpr_after": 1.0,
      "oracle_passed_all": true,
      "patch_path": "patches/iter_01.json",
      "candidate_fsm_path_after": "candidates/iter_01.json",
      "failed_tests": [],
      "regression": false,
      "timestamp": "2026-06-03T14:02:30Z"
    }
  ],
  "final_bpr": 1.0,
  "final_status": "success",
  "structurally_valid": true
}
```

\(\Delta_{\kappa}(c) = 1.0 - 0.25 = 0.75\) for this condition. Entry snapshots in `failed_tests` / `missing_transitions` at the top level remain the **initial** diagnostic; per-iteration failures appear inside `repair_history`.

## Example 3 — Partial repair (`budget_exhausted`)

Turnstile controller; BPR improves but does not reach 1.

```json
{
  "schema_version": "1.0.0",
  "case_id": "turnstile_07",
  "system_id": "turnstile",
  "requirement_text": "Idle locked until coin; after coin, unlocked until pass event returns to locked.",
  "gold_fsm_path": "gold_fsm.json",
  "candidate_fsm_path": "candidate_fsm.json",
  "initial_bpr": 0.0,
  "oracle_suite_id": "turnstile_oracle_v1",
  "failed_tests": [
    { "check_id": "coin_unlock", "check_type": "trace" },
    { "check_id": "pass_relock", "check_type": "trace" }
  ],
  "passed_tests": [],
  "missing_transitions": [
    { "from": "locked", "event": "coin", "to": "unlocked" }
  ],
  "extra_transitions": [],
  "repair_history": [
    {
      "iteration": 0,
      "condition_id": "patch_binary_feedback",
      "bpr_before": 0.0,
      "bpr_after": 0.5,
      "oracle_passed_all": false,
      "patch_path": "patches/iter_00.json",
      "candidate_fsm_path_after": "candidates/iter_00.json",
      "regression": false
    },
    {
      "iteration": 1,
      "condition_id": "patch_binary_feedback",
      "bpr_before": 0.5,
      "bpr_after": 0.5,
      "oracle_passed_all": false,
      "patch_path": "patches/iter_01.json",
      "candidate_fsm_path_after": "candidates/iter_01.json",
      "regression": false
    }
  ],
  "final_bpr": 0.5,
  "final_status": "partial"
}
```

Classification: **partial repair** per [`repairability_definition.md`](repairability_definition.md); `final_status` may also be reported as `budget_exhausted` when the protocol prioritizes budget semantics—declare the primary label in the analysis plan.

## Example 4 — Regression terminal

```json
{
  "schema_version": "1.0.0",
  "case_id": "vending_03",
  "system_id": "vending_machine",
  "requirement_text": "Accept coin, dispense on select, return to idle.",
  "gold_fsm_path": "gold_fsm.json",
  "candidate_fsm_path": "candidate_fsm.json",
  "initial_bpr": 0.5,
  "oracle_suite_id": "vending_oracle_v1",
  "failed_tests": [{ "check_id": "dispense_trace", "check_type": "trace" }],
  "passed_tests": [{ "check_id": "idle_initial", "check_type": "state" }],
  "missing_transitions": [],
  "extra_transitions": [{ "from": "dispensing", "event": "coin", "to": "idle", "note": "Spurious reset" }],
  "repair_history": [
    {
      "iteration": 0,
      "condition_id": "patch_localized_feedback",
      "bpr_before": 0.5,
      "bpr_after": 0.0,
      "oracle_passed_all": false,
      "regression": true,
      "patch_path": "patches/iter_00.json",
      "candidate_fsm_path_after": "candidates/iter_00.json"
    }
  ],
  "final_bpr": 0.0,
  "final_status": "regression_terminal"
}
```

## Validation (planned)

Manifest validation against `repair_case.schema.json` will be provided by a dedicated script. Until then, use JSON Schema tooling with a local registry including `fsm.schema.json` and sibling schemas.

## See also

- [`repairability_definition.md`](repairability_definition.md) — BPR and outcome definitions
- [`datasets/repair_cases/README.md`](../datasets/repair_cases/README.md) — deposit policy
- [`schemas/repair_run.schema.json`](../schemas/repair_run.schema.json) — per-condition run records
