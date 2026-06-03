# Scripts

Deterministic utilities and **local Ollama** helpers. No cloud APIs.

| Script | Purpose | Status |
|--------|---------|--------|
| [`validate_fsm.py`](validate_fsm.py) | Validate FSM JSON against schema | Functional |
| [`apply_patch.py`](apply_patch.py) | Patch engine v1 (transition ops; see `examples/`) | Functional |
| [`score_repair.py`](score_repair.py) | Deterministic FSM vs oracle scoring | Functional |
| [`build_diagnostic.py`](build_diagnostic.py) | Project score report → diagnostic artefact | Functional |
| [`ollama_client.py`](ollama_client.py) | Stdlib HTTP client for local Ollama | Functional |
| [`extract_repair_candidates.py`](extract_repair_candidates.py) | Import repair cases (manifest or EMSE layout) | Functional |
| [`generate_patch_ollama.py`](generate_patch_ollama.py) | Pilot patch generation via Ollama + prompt templates | Functional |
| [`run_pilot_campaign.py`](run_pilot_campaign.py) | Multi-case pilot campaign (Ollama + full pipeline) | Functional |
| [`run_diagnostic_granularity_pilot.py`](run_diagnostic_granularity_pilot.py) | Compare diagnostic levels C/D/E on same cases | Functional |
| [`run_repair_condition.py`](run_repair_condition.py) | Dry-run repair loop (no Ollama); emits `repair_run` | Functional |

## Repair condition runner (dry-run)

Deterministic loop without Ollama — see [`docs/repair_condition_runner.md`](../docs/repair_condition_runner.md):

```bash
python scripts/run_repair_condition.py \
  --case-dir tests/fixtures/dry_run_case \
  --condition patch_trace_feedback \
  --patch-source tests/fixtures/dry_run_case/repair_patch.json \
  --work-dir /tmp/dry_run_work \
  --output-run /tmp/dry_run_work/repair_run.json
```

## Scoring and patches

```bash
python scripts/validate_fsm.py --input path/to/fsm.json
python scripts/apply_patch.py --fsm fsm.json --patch patch.json -o out.json
python scripts/score_repair.py --fsm out.json --oracles datasets/oracle_suites/suite.json --output /tmp/score.json
python scripts/build_diagnostic.py \
  --score-report /tmp/score.json --level trace \
  --case-id case_01 --run-id case_01__patch_trace_feedback__r001 \
  --iteration-index 0 --output /tmp/diagnostic.json
```

See [`docs/diagnostic_generation.md`](../docs/diagnostic_generation.md).

A batch driver for full campaigns is deferred; use frozen `results/frozen_runs/` for audit.
