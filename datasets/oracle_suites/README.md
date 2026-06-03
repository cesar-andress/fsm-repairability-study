# Oracle suites

**Behavioural oracles** define how candidate FSMs are executed and checked against expected behaviour.

## Planned layout

```
oracle_suites/
  <suite_id>.json
```

Suite format will be documented when the oracle schema is frozen (may extend `repair_case` linking fields). Minimum expectation per suite:

- Stable `suite_id`
- Execution semantics reference (link to `docs/terminology.md`)
- Ordered list of checks (traces, I/O sequences, or equivalent)

## Use in replication

```bash
python scripts/score_repair.py --fsm <path> --oracles datasets/oracle_suites/<suite_id>.json --output /tmp/score.json
```

## Status

Placeholder only. Do not commit proprietary task sources; use redistributable or synthetic specifications.
