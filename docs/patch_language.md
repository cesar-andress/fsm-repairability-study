# Constrained FSM patch language

This document specifies the **patch language** used in oracle-guided behavioural repair experiments. Patches edit finite state machines (FSMs) represented as JSON conforming to [`schemas/fsm.schema.json`](../schemas/fsm.schema.json). Patch documents validate against [`schemas/patch.schema.json`](../schemas/patch.schema.json).

## Design principles

| Principle | Implication |
|-----------|-------------|
| **Explicit and auditable** | Every edit is a typed operation with fully specified parameters; no implicit diff. |
| **Reversible** | Each operation has a defined inverse (see [Reversibility](#reversibility)). |
| **Machine-applicable** | A deterministic applicator updates the FSM JSON; no free-form regeneration. |
| **Constrained** | Only the seven operations below are permitted; arbitrary graph replacement is out of scope. |

Patches support **oracle-guided repair**: failing checks motivate localized operations (e.g. add a missing transition surfaced by a trace oracle) rather than replacing the entire machine.

## Patch document envelope

```json
{
  "schema_version": "1.0.0",
  "patch_id": "tlc_01_iter_00",
  "target_fsm_id": "tlc_01_candidate",
  "case_id": "tlc_01",
  "condition_id": "patch_trace_feedback",
  "iteration": 0,
  "operations": [ /* ordered */ ],
  "inverse_operations": [ /* optional, recommended at freeze */ ],
  "created_at": "2026-06-03T14:01:00Z"
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `schema_version` | Yes | Patch schema semver (`1.0.0`). |
| `patch_id` | Yes | Unique slug for this patch file. |
| `target_fsm_id` | Yes | Must match `id` of the FSM being edited. |
| `operations` | Yes | Non-empty ordered list (max 64 operations per patch). |
| `inverse_operations` | No | Precomputed undo sequence in **reverse** order of forward ops. |
| `case_id`, `condition_id`, `iteration` | No | Audit linkage to repair protocol. |

**Application semantics:** Operations apply **sequentially** to a deep copy of the target FSM. The applicator must reject operations that violate [validation constraints](#validation-constraints-at-application-time) on the current intermediate FSM.

**Determinism:** Given the same FSM snapshot and patch, the result is unique. No randomness or external text parsing is involved in application.

---

## Reversibility

Each forward operation \(op\) has an inverse \(op^{-1}\) such that applying \(op\) then \(op^{-1}\) (on the post-state) restores the pre-state, subject to validation constraints.

| Forward | Inverse |
|---------|---------|
| `add_transition` (from, event, to) | `remove_transition` (from, event, to) |
| `remove_transition` (from, event, to) | `add_transition` (from, event, to) |
| `update_transition` (from, event, old_to, new_to) | `update_transition` (from, event, new_to, old_to) |
| `add_state` (state) | `remove_state` (state, incident_transitions: []) |
| `remove_state` (state, incident_transitions: T) | `add_state` (state) then each `add_transition` in T (order: state first, then transitions) |
| `rename_state` (old_name, new_name) | `rename_state` (new_name, old_name) |
| `change_initial_state` (previous_initial, new_initial) | `change_initial_state` (new_initial, previous_initial) |

For `remove_state`, **`incident_transitions` must list every transition removed** so auditors and undo procedures do not depend on hidden applicator state.

A full patch inverse is the **reverse-ordered** list of per-operation inverses. Storing `inverse_operations` in the patch file is recommended at artifact freeze.

---

## Operations

### 1. `add_transition`

#### Rationale

Adds a single labelled transition without replacing the full graph. Typical use: satisfy a trace oracle by connecting states that the gold FSM reaches but the candidate omits (see repair case `missing_transitions`).

#### JSON structure

```json
{
  "op": "add_transition",
  "from": "s_green",
  "event": "tick",
  "to": "s_yellow"
}
```

| Field | Type | Required |
|-------|------|----------|
| `op` | `"add_transition"` | Yes |
| `from` | state id | Yes |
| `event` | event id | Yes |
| `to` | state id | Yes |

#### Example

```json
{
  "schema_version": "1.0.0",
  "patch_id": "tlc_01_add_green_yellow",
  "target_fsm_id": "tlc_01_candidate",
  "operations": [
    { "op": "add_transition", "from": "s_green", "event": "tick", "to": "s_yellow" }
  ],
  "inverse_operations": [
    { "op": "remove_transition", "from": "s_green", "event": "tick", "to": "s_yellow" }
  ]
}
```

#### Validation constraints

- `from` and `to` must exist in `states` at application time.
- No existing transition with the same `(from, event)` pair (deterministic semantics).
- `event` is added to `alphabet` if not already present.
- `from` must not equal `to` unless self-loops are explicitly allowed by the case protocol (default: **reject** self-loops).

---

### 2. `remove_transition`

#### Rationale

Deletes one transition identified by source, event, and target. Used to eliminate spurious edges (`extra_transitions` in repair cases) or to undo a mistaken `add_transition`.

#### JSON structure

```json
{
  "op": "remove_transition",
  "from": "s_green",
  "event": "tick",
  "to": "s_red",
  "note": "Spurious skip-yellow edge"
}
```

| Field | Type | Required |
|-------|------|----------|
| `op` | `"remove_transition"` | Yes |
| `from`, `event`, `to` | ids | Yes |
| `note` | string | No |

#### Example

```json
{
  "op": "remove_transition",
  "from": "s_green",
  "event": "tick",
  "to": "s_red"
}
```

#### Validation constraints

- A transition exactly matching `(from, event, to)` must exist.
- If multiple transitions share `(from, event)` but differ in `to`, **`to` is required** to disambiguate (schema enforces `to`).
- After removal, if `event` no longer appears in any transition, remove `event` from `alphabet` (applicator convention).

---

### 3. `update_transition`

#### Rationale

Changes the target of an existing transition while keeping `(from, event)` fixed. Models “redirect” repairs suggested by trace feedback without deleting and re-adding the edge (preserves audit trail of which arc was corrected).

#### JSON structure

```json
{
  "op": "update_transition",
  "from": "s_green",
  "event": "tick",
  "old_to": "s_red",
  "new_to": "s_yellow"
}
```

| Field | Type | Required |
|-------|------|----------|
| `op` | `"update_transition"` | Yes |
| `from`, `event` | ids | Yes |
| `old_to` | state id | Yes |
| `new_to` | state id | Yes |

#### Example

```json
{
  "operations": [
    {
      "op": "update_transition",
      "from": "s_green",
      "event": "tick",
      "old_to": "s_red",
      "new_to": "s_yellow"
    }
  ],
  "inverse_operations": [
    {
      "op": "update_transition",
      "from": "s_green",
      "event": "tick",
      "old_to": "s_yellow",
      "new_to": "s_red"
    }
  ]
}
```

#### Validation constraints

- Exactly one transition must match `(from, event, old_to)`.
- `new_to` must exist in `states`.
- `old_to` ≠ `new_to`.
- After update, no duplicate `(from, event)` to a different target (if `new_to` would create conflict with another edge, reject).

---

### 4. `add_state`

#### Rationale

Introduces an isolated state before wiring transitions. Supports repair when oracles require new modes not present in the candidate.

#### JSON structure

```json
{
  "op": "add_state",
  "state": "s_yellow"
}
```

#### Example

```json
{ "op": "add_state", "state": "s_yellow" }
```

#### Validation constraints

- `state` must not already exist in `states`.
- Does not change `initial_state` unless followed by `change_initial_state`.

---

### 5. `remove_state`

#### Rationale

Removes a state and all incident transitions. Requires explicit `incident_transitions` for audit and reversal.

#### JSON structure

```json
{
  "op": "remove_state",
  "state": "s_unused",
  "incident_transitions": [
    { "from": "s_idle", "event": "reset", "to": "s_unused" },
    { "from": "s_unused", "event": "timeout", "to": "s_idle" }
  ]
}
```

| Field | Type | Required |
|-------|------|----------|
| `op` | `"remove_state"` | Yes |
| `state` | state id | Yes |
| `incident_transitions` | array of triples | Yes (may be `[]`) |

#### Example

```json
{
  "op": "remove_state",
  "state": "s_dead",
  "incident_transitions": [
    { "from": "s_live", "event": "fail", "to": "s_dead" }
  ]
}
```

#### Validation constraints

- `state` must exist.
- **`state` must not be `initial_state`** (use `change_initial_state` first).
- Every triple in `incident_transitions` must match an existing transition incident on `state` (as `from` or `to`).
- The set of transitions removed by the applicator must equal `incident_transitions` (no omissions, no extras).
- After removal, `states` has no reference to `state`.

---

### 6. `rename_state`

#### Rationale

Renames a state identifier and updates all incident transitions and `initial_state` if affected. Avoids delete-and-recreate sequences that lose identity in audit logs.

#### JSON structure

```json
{
  "op": "rename_state",
  "old_name": "s_yellow",
  "new_name": "s_amber"
}
```

#### Validation constraints

- `old_name` must exist; `new_name` must not exist.
- `old_name` ≠ `new_name`.
- All transitions and `initial_state` referencing `old_name` are updated atomically in one operation.

#### Example

```json
{
  "inverse_operations": [
    { "op": "rename_state", "old_name": "s_amber", "new_name": "s_yellow" }
  ],
  "operations": [
    { "op": "rename_state", "old_name": "s_yellow", "new_name": "s_amber" }
  ]
}
```

---

### 7. `change_initial_state`

#### Rationale

Sets the initial state when oracle feedback indicates wrong entry behaviour. Records `previous_initial` for audit and reversal.

#### JSON structure

```json
{
  "op": "change_initial_state",
  "previous_initial": "s_idle",
  "new_initial": "s_ready"
}
```

#### Validation constraints

- `previous_initial` must equal the current `initial_state` at application time.
- `new_initial` must exist in `states`.
- `previous_initial` ≠ `new_initial`.

#### Example

```json
{
  "operations": [
    {
      "op": "change_initial_state",
      "previous_initial": "s_wrong",
      "new_initial": "s_idle"
    }
  ],
  "inverse_operations": [
    {
      "op": "change_initial_state",
      "previous_initial": "s_idle",
      "new_initial": "s_wrong"
    }
  ]
}
```

---

## Validation constraints at application time

Beyond JSON Schema validation, the applicator enforces **semantic** rules on the evolving FSM:

1. **Referential integrity** — Every `from`/`to` in transitions must appear in `states`; `initial_state` ∈ `states`.
2. **Deterministic arc key** — At most one transition per `(from, event)` unless a future schema version explicitly allows nondeterminism.
3. **Alphabet consistency** — `alphabet` contains exactly the events used in transitions (after each operation).
4. **Target binding** — `target_fsm_id` equals `fsm.id`.
5. **Ordered composition** — Operation \(i\) validates against the FSM produced after operations \(0..i-1\).
6. **Post-condition (optional case rules)** — Case-specific structural rules (e.g. totality on a subset of events) may reject otherwise valid patches; document per `system_id`.

Failed application must not partially mutate the input FSM (atomic patch application).

---

## Composite patch example (oracle-guided)

Repair iteration fixing a traffic-light case: add yellow state, rewire green transition, remove spurious edge.

```json
{
  "schema_version": "1.0.0",
  "patch_id": "tlc_01_iter_00",
  "target_fsm_id": "tlc_01_candidate",
  "case_id": "tlc_01",
  "condition_id": "patch_trace_feedback",
  "iteration": 0,
  "operations": [
    { "op": "add_state", "state": "s_yellow" },
    { "op": "remove_transition", "from": "s_green", "event": "tick", "to": "s_red" },
    {
      "op": "add_transition",
      "from": "s_green",
      "event": "tick",
      "to": "s_yellow"
    },
    {
      "op": "add_transition",
      "from": "s_yellow",
      "event": "tick",
      "to": "s_red"
    }
  ],
  "metadata": {
    "motivated_by_checks": ["trace_yellow_sequence", "forbidden_skip_yellow"]
  }
}
```

This patch is **not** a regeneration: it performs four typed edits auditable in `repair_history` on the repair case.

---

## What the patch language forbids

- Replacing the entire FSM JSON in one untyped blob (use `baseline_full_regeneration` condition instead).
- Free-text “edit” operations without schema.
- Implicit inference of removed transitions on `remove_state` without listing `incident_transitions`.
- Operations on states or events outside the declared `states` / `alphabet` without prior `add_state` or explicit event introduction via `add_transition`.

---

## See also

- [`repair_case_format.md`](repair_case_format.md) — `patches/iter_*.json` references
- [`repairability_definition.md`](repairability_definition.md) — repair cost via patch operation counts
- [`scripts/apply_patch.py`](../scripts/apply_patch.py) — applicator implementation (aligned with this spec)
