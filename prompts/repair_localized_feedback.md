# Repair prompt — localized feedback condition

> **Frozen prompt placeholder.**

## System

You are repairing a finite state machine (FSM) given as structured JSON. Oracle feedback points to likely states or transitions involved in the failure. Apply minimal edits consistent with the patch grammar. Respond with a single JSON patch document only.

## User

**Task reference:** {{task_spec_ref}}

**Current FSM:**

```json
{{current_fsm_json}}
```

**Oracle feedback (localized):**

- Check id: {{check_id}}
- Suspected states: {{suspected_states}}
- Suspected transitions: {{suspected_transitions}}
- Failure summary: {{failure_summary}}

**Attempt:** {{attempt_index}} of {{attempt_budget}}

Produce a patch conforming to the project patch schema targeting FSM id `{{fsm_id}}`.
