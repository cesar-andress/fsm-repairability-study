# Repair scoring interface

Deterministic layer for evaluating **one FSM candidate** against **one oracle suite**. Implemented by [`scripts/score_repair.py`](../scripts/score_repair.py). Repair runs and patch engines call this interface; it is not the full experimental pipeline.

## CLI

```bash
python scripts/score_repair.py \
  --fsm path/to/candidate.json \
  --oracles path/to/oracle_suite.json \
  --output path/to/score_report.json
```

| Argument | Required | Description |
|----------|----------|-------------|
| `--fsm` | Yes | Candidate FSM JSON |
| `--oracles` | Yes | Oracle suite JSON |
| `--output` | Yes | Score report path (created/overwritten) |

Exit code: `0` if `bpr == 1.0`, else `1`. Scoring itself is deterministic for fixed inputs.

## FSM input format (minimal)

Compatible with study FSM JSON; scoring uses a **minimal subset**:

| Field | Required | Description |
|-------|----------|-------------|
| `states` | Yes | State names |
| `initial_state` | Yes | Start state |
| `transitions` | Yes | List of `{from, event, to}` |
| `final_states` | No | Accepting states; used by `final_state` tests |
| `alphabet` | No | Ignored by scorer (derived from transitions) |
| `id`, `schema_version` | No | Passed through; not required for scoring |

### Transition matching

- Match by **`(from, event)`** only; first enabled matching transition wins.
- **`guard` field:** honoured only for boolean literals (`true` / `false`). `guard: false` disables the edge. **Non-boolean or expression guards are ignored** (edge treated as absent). Complex guards are deferred to future work.
- **Nondeterminism:** multiple enabled transitions for the same `(from, event)` — first in file order is taken (document and keep file order stable).

## Oracle suite format

```json
{
  "schema_version": "1.0.0",
  "suite_id": "example_suite_v1",
  "tests": [
    {
      "test_id": "unique_test_id",
      "type": "trace | final_state | rejected_event",
      "...": "type-specific fields"
    }
  ]
}
```

Legacy alias: `checks` is accepted instead of `tests` (same objects; use `test_id` or `check_id`).

### Test type: `trace`

Positive execution: all events must be defined; state sequence must match.

| Field | Required |
|-------|----------|
| `test_id` | Yes |
| `type` | `"trace"` |
| `events` | Yes — input sequence |
| `expected_states` | Yes — includes initial state |
| `diagnostic_hint` | No |

### Test type: `final_state`

Run `events`, then assert terminal state.

| Field | Required |
|-------|----------|
| `test_id` | Yes |
| `type` | `"final_state"` |
| `events` | Yes (may be empty) |
| `expected_final_state` | Yes |
| `diagnostic_hint` | No |

If `final_states` is set on the FSM, the terminal state must also be a member of that set.

### Test type: `rejected_event`

Assert the event is **not** enabled from `from_state` (undefined transition).

| Field | Required |
|-------|----------|
| `test_id` | Yes |
| `type` | `"rejected_event"` |
| `events` | Yes — exactly one event |
| `from_state` | No — defaults to `initial_state` |
| `diagnostic_hint` | No |

Pass = no enabled transition on `(from_state, event)`.

## Score report output

Written to `--output` and printed to stdout.

```json
{
  "score_schema_version": "1.0.0",
  "fsm_path": "...",
  "oracle_suite_path": "...",
  "suite_id": "...",
  "total_tests": 3,
  "passed_tests": 2,
  "failed_tests": 1,
  "bpr": 0.6666666666666666,
  "component_metrics": {
    "final_state_agreement": 1.0,
    "trace_agreement": 0.0,
    "rejected_event_agreement": 1.0
  },
  "failures": []
}
```

### Behavioural Pass Rate (BPR)

\[
\mathrm{BPR} = \frac{\texttt{passed\_tests}}{\texttt{total\_tests}}
\]

If `total_tests == 0`, BPR is defined as `1.0` (vacuous pass).

### `component_metrics`

Per-type pass rates over tests of that type in the suite:

| Metric | Test type |
|--------|-----------|
| `trace_agreement` | `trace` |
| `final_state_agreement` | `final_state` |
| `rejected_event_agreement` | `rejected_event` |

Value is `null` when the suite contains no tests of that type.

Aligns with repair-case component metrics and dual-oracle reporting ([`experimental_unit.md`](experimental_unit.md)).

### `failures`

List of objects for **failed** tests only:

| Field | Description |
|-------|-------------|
| `test_id` | Failed test |
| `failure_type` | e.g. `trace_mismatch`, `undefined_transition`, `unexpected_transition`, `final_state_mismatch` |
| `expected` | JSON object — expected witness |
| `observed` | JSON object — observed witness |
| `trace` | Input events / context |
| `diagnostic_hint` | Copied from test spec or engine message |

## Determinism guarantees

- No randomness, network, or clock dependency in scoring logic.
- Same FSM file + same suite file → identical report JSON (key order fixed in `write_report`).
- FSM integrity checked via [`validate_fsm`](../scripts/validate_fsm.py) referential rules before tests run.

## Limitations (v1)

| Topic | Status |
|-------|--------|
| Boolean / absent guards only | Expression guards disable edge |
| First-match transition semantics | No full nondeterministic exploration |
| No timers, variables, or outputs | Pure state–event steps |
| No partial-order or LTL oracles | Only trace / final / reject |
| `checks` legacy key | Supported for migration |

## Fixtures

See [`tests/fixtures/scoring/`](../tests/fixtures/scoring/):

| File | Role |
|------|------|
| `oracle_suite.json` | Three tests (trace, final_state, rejected_event) |
| `fsm_pass.json` | BPR = 1.0 |
| `fsm_fail_trace.json` | Fails trace test |
| `fsm_reject_ok.json` | Same as pass for reject (alias) |
| `fsm_fail_reject.json` | Fails rejected_event test |

## Programmatic use

```python
from score_repair import score_fsm

report = score_fsm(fsm_dict, suite_dict)
bpr = report["bpr"]
```

`score_against_suite()` remains a thin legacy adapter returning `{passed, checks, bpr}` for older scripts.

## Downstream: diagnostic projection

Score reports feed the formal diagnostic model ([`diagnostic_model.md`](diagnostic_model.md)); projected diagnostics are the repair feedback channel for conditions C–E.

## See also

- [`diagnostic_model.md`](diagnostic_model.md) — feedback levels 1–3
- [`repairability_definition.md`](repairability_definition.md) — BPR definition
- [`patch_language.md`](patch_language.md) — candidate edits before re-score
- [`local_model_execution.md`](local_model_execution.md) — engine vs evaluation separation
