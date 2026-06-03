# Repair prompt — binary feedback condition

> **Frozen prompt placeholder.** Replace `{{...}}` bindings when the protocol is finalized.

## System

You are repairing a finite state machine (FSM) given as structured JSON. The current FSM is structurally valid but fails behavioural checks. Apply minimal edits consistent with the patch grammar. Respond with a single JSON patch document only.

## User

**Task reference:** {{task_spec_ref}}

**Current FSM:**

```json
{{current_fsm_json}}
```

**Oracle feedback (binary):**

- Overall result: {{oracle_pass_fail}}
- Failed check ids: {{failed_check_ids}}

**Attempt:** {{attempt_index}} of {{attempt_budget}}

Produce a patch conforming to the project patch schema targeting FSM id `{{fsm_id}}`.
