# Scripts

Deterministic utilities and **local Ollama** helpers. No cloud APIs.

| Script | Purpose | Status |
|--------|---------|--------|
| [`validate_fsm.py`](validate_fsm.py) | Validate FSM JSON against schema | Functional |
| [`apply_patch.py`](apply_patch.py) | Patch engine v1 (transition ops; see `examples/`) | Functional |
| [`score_repair.py`](score_repair.py) | Score FSM against oracle suite | Partial |
| [`ollama_client.py`](ollama_client.py) | Stdlib HTTP client for local Ollama | Functional |
| [`run_repair_condition.py`](run_repair_condition.py) | Run one case × condition (primary IV) | Partial |

## Repair condition runner

Primary entry point for experiments (condition = independent variable):

```bash
# Deterministic baseline (no GPU, no Ollama)
python scripts/run_repair_condition.py --case case_01 --condition baseline_no_repair

# Inspect prompt without inference
python scripts/run_repair_condition.py \
  --case case_01 --condition patch_trace_feedback --model llama3:8b --dry-run

# Local Ollama execution (study workstation)
python scripts/run_repair_condition.py \
  --case case_01 --condition patch_binary_feedback --model llama3:8b

# Audit replication from frozen runs (no Ollama)
python scripts/run_repair_condition.py \
  --case case_01 --condition patch_binary_feedback --model llama3:8b --offline
```

## Scoring and patches

```bash
python scripts/validate_fsm.py --input path/to/fsm.json
python scripts/apply_patch.py --fsm fsm.json --patch patch.json -o out.json
python scripts/score_repair.py --fsm out.json --oracle-suite datasets/oracle_suites/suite.json
```

A batch driver for full campaigns is deferred; use frozen `results/frozen_runs/` for audit.
