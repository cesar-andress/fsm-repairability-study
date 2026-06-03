# Repair cases

Each **repair case** is a structurally valid, behaviourally incorrect FSM eligible for the repairability study.

## Planned layout

```
repair_cases/
  <campaign_id>/
    <case_id>/
      case.json
      candidate_fsm.json
      reference_fsm.json
      patches/
      candidates/
```

Design: [`docs/experimental_unit.md`](../../docs/experimental_unit.md). Schema: [`schemas/repair_case.schema.json`](../../schemas/repair_case.schema.json) v2.0.0.

## Inclusion criteria

1. `structurally_valid` is true under documented checks
2. `behaviourally_correct` is false against the linked oracle suite(s) at study entry
3. Metadata sufficient to interpret the case without rerunning generation campaigns

## Status

No cases are deposited yet. Add finalized cases only from the private research workspace export process described in `docs/repository_scope.md`.
