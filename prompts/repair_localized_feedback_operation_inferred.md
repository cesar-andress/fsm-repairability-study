# FSM Repair Task (Operation-Inferred Variant)

You are repairing a finite state machine (FSM).

Your goal is to improve behavioural correctness while preserving existing correct behaviour.

## Important

Do NOT decide whether a change is an add_transition or update_transition.

Your job is only to describe the intended behavioural correction.

The repair framework will determine the correct patch operation automatically.

## Candidate FSM

{{candidate_fsm_json}}

## Behavioural Requirement

{{requirement_text}}

## Localized Diagnostic

{{localized_feedback_json}}

## Repair Rules

1. Identify the transition that is causing the failure.
2. Identify the desired target state.
3. Describe only the intended correction.
4. Do not emit patch operations.
5. Do not emit add_transition.
6. Do not emit update_transition.
7. Do not emit remove_transition.
8. If no safe correction can be inferred, return an empty corrections array and explain why.

## Output Schema

Return ONLY valid JSON.

```json
{
  "schema_version": "1.0.0",
  "corrections": [
    {
      "from": "<source_state>",
      "event": "<event>",
      "desired_target": "<target_state>",
      "confidence": "high"
    }
  ],
  "rationale": "<short explanation>"
}
```

If no safe correction exists:

```json
{
  "schema_version": "1.0.0",
  "corrections": [],
  "rationale": "<explanation>"
}
```
