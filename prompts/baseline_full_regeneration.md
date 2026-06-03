# Baseline prompt — full regeneration (no patch repair)

> **Frozen prompt placeholder.** Condition: `baseline_full_regeneration`.

## System

You are generating a finite state machine (FSM) as structured JSON from a behavioural task specification. Produce a complete FSM document conforming to the project FSM schema. Do not reference any previous incorrect FSM. Respond with JSON only.

## User

**Task specification:**

{{task_spec_ref}}

{{task_spec_body}}

**Constraints (if any):**

{{structural_constraints}}

Produce a new FSM with a fresh `id` field. No patch document is requested for this condition.
