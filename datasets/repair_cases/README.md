# Repair cases

Each **repair case** is a structurally valid, behaviourally incorrect FSM eligible for the repairability study.

## Planned layout

```
repair_cases/
  <case_id>/
    case.json              # manifest — see docs/repair_case_format.md
    gold_fsm.json          # reference FSM
    candidate_fsm.json     # initial candidate M_0
    patches/               # optional per-iteration patches
    candidates/            # optional per-iteration snapshots
```

The manifest schema is [`schemas/repair_case.schema.json`](../../schemas/repair_case.schema.json).

## Inclusion criteria

1. `structurally_valid` is true under documented checks
2. `behaviourally_correct` is false against the linked oracle suite(s) at study entry
3. Metadata sufficient to interpret the case without rerunning generation campaigns

## Status

No cases are deposited yet. Add finalized cases only from the private research workspace export process described in `docs/repository_scope.md`.
