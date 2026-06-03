# Repair prompt — trace feedback condition

> **Frozen prompt placeholder.**

## System

You are repairing a finite state machine (FSM) given as structured JSON. Use the execution trace below to identify where observed behaviour diverges from expected behaviour. Apply minimal edits consistent with the patch grammar. Respond with a single JSON patch document only.

## User

**Task reference:** {{task_spec_ref}}

**Current FSM:**

```json
{{current_fsm_json}}
```

**Oracle feedback (trace):**

- Check id: {{check_id}}
- Input sequence: {{input_sequence}}
- Expected trace: {{expected_trace}}
- Observed trace: {{observed_trace}}

**Attempt:** {{attempt_index}} of {{attempt_budget}}

Produce a patch conforming to the project patch schema targeting FSM id `{{fsm_id}}`.
