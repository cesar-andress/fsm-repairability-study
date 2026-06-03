# Repair cases

Each **repair case** is a structurally valid, behaviourally incorrect FSM eligible for the repairability study.

## Planned layout

```
repair_cases/
  <case_id>/
    case.json           # conforms to repair_case.schema.json
    initial_fsm.json    # conforms to fsm.schema.json
```

Alternatively, a single `cases.jsonl` index may be used if the release checklist prefers one manifest; the schema remains the same per record.

## Inclusion criteria

1. `structurally_valid` is true under documented checks
2. `behaviourally_correct` is false against the linked oracle suite(s) at study entry
3. Metadata sufficient to interpret the case without rerunning generation campaigns

## Status

No cases are deposited yet. Add finalized cases only from the private research workspace export process described in `docs/repository_scope.md`.
