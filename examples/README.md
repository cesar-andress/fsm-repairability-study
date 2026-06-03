# Patch engine examples

Worked examples for [`scripts/apply_patch.py`](../scripts/apply_patch.py) (v1: transition operations only).

## Run

From the repository root:

```bash
python scripts/apply_patch.py \
  --fsm examples/traffic_light/candidate_fsm.json \
  --patch examples/traffic_light/patch_fix_yellow.json \
  -o /tmp/traffic_light_repaired.json

diff -u examples/traffic_light/expected_fsm.json /tmp/traffic_light_repaired.json
```

## Bundles

| Directory | Description |
|-----------|-------------|
| [`traffic_light/`](traffic_light/) | Remove spurious transition, add yellow-step edges |
| [`simple_loop/`](simple_loop/) | Add return transition to close a trace |

Expected outputs are checked in `tests/test_apply_patch.py`.
