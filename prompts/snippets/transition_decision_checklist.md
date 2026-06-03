## Transition Decision Checklist (MANDATORY)

Before generating any operation:

**Step 1.** Search all transitions in `candidate_fsm_json.transitions`.

**Step 2.** Check whether a transition already exists with the same `(from, event)` (source state and event).

**Step 3.** IF a transition exists:

- NEVER use `add_transition`
- MUST use `update_transition`
- `old_to` must be the current destination
- `new_to` must be different from `old_to`

**Step 4.** IF no transition exists:

- use `add_transition`

**Step 5.** Before returning JSON verify:

- no duplicated `(from, event)` pairs in `operations`
- all referenced states exist in `candidate_fsm_json.states`
- all referenced events exist in `candidate_fsm_json.alphabet` (or the requirement text)
- the patch preserves FSM determinism (at most one transition per `(from, event)`)

**Step 6.** If any uncertainty remains:

Return a patch document with empty operations:

```json
{
  "operations": [],
  "metadata": {
    "rationale": "Unable to determine a safe repair."
  }
}
```

Returning an empty patch is preferred to producing a duplicated transition.
