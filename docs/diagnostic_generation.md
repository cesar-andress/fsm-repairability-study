# Diagnostic generation

Deterministic projection from a [`score_repair.py`](../scripts/score_repair.py) **score report** to a **diagnostic artefact** validated against [`schemas/diagnostic.schema.json`](../schemas/diagnostic.schema.json) v2.0.0. Formal artefact definition: [`diagnostic_model.md`](diagnostic_model.md).

Implemented by [`scripts/build_diagnostic.py`](../scripts/build_diagnostic.py).

## Deterministic projection

| Property | Guarantee |
|----------|-----------|
| Input | One score report JSON (read-only; never mutated) |
| Output | One diagnostic JSON per invocation |
| Randomness | None |
| LLM / repair | Not used; not generated |
| BPR | Recomputed as `passed_tests / total_tests` (1.0 if `total_tests == 0`) |
| Identity | `diagnostic_id = {case_id}__{run_id}__iter{NN}__{level}` |
| Schema | `identity.schema_version` is always `"2.0.0"` |
| Validation | Output checked with `jsonschema` (hard failure if package missing) |

The same score report and projection level yield the same diagnostic fields except `reproducibility.generated_at` when the caller does not fix a timestamp.

## Score report → diagnostic mapping

| Score report field | Diagnostic field |
|--------------------|------------------|
| `oracle_suite_id` (if present) | `scoring_summary.oracle_suite_id` |
| `oracle_suite_path` (stem, if no `oracle_suite_id`) | `scoring_summary.oracle_suite_id` |
| `total_tests` | `scoring_summary.total_checks` |
| `passed_tests` | `scoring_summary.passed_checks` |
| `failed_tests` | `scoring_summary.failed_checks` |
| recomputed ratio | `scoring_summary.bpr` |
| `failures[]` | `failed_checks[]` (`test_id` → `check_id`) |
| `failures[].trace` | `failed_checks[].input_trace` (trace / localized only) |
| `failures[].expected` / `observed` | same (trace / localized only) |
| `failures[].diagnostic_hint` | `failed_checks[].diagnostic_hint` (binary when present) |
| `localization` (optional) | `localization` (localized only) |
| `fsm_path` | `reproducibility.source_fsm_path` |
| `oracle_suite_path` | `reproducibility.oracle_suite_path` |
| `score_schema_version` | `reproducibility.scorer_version` |
| score report file | `reproducibility.checksums.score_report_sha256` |
| resolved FSM file | `reproducibility.checksums.source_fsm_sha256` (if path exists) |
| resolved oracle suite file | `reproducibility.checksums.oracle_suite_sha256` (if path exists) |

### Failure category counts

| Counter | Rule |
|---------|------|
| `final_state_failures` | `failure_type == "final_state_mismatch"` |
| `trace_failures` | `failure_type == "trace_mismatch"` |
| `rejection_failures` | `failure_type` in `unexpected_acceptance`, `unexpected_rejection` |
| `simulation_failures` | `failure_type == "simulation_error"` |
| `nondeterminism_failures` | `failure_type == "nondeterminism"` |
| `positive_path_failures` | `final_state_failures + trace_failures` |

## Level-specific filtering

| Content | `binary` | `trace` | `localized` |
|---------|----------|---------|-------------|
| `scoring_summary`, `failure_categories` | ✓ | ✓ | ✓ |
| `failed_checks`: `check_id`, `oracle_type`, `failure_type` | ✓ | ✓ | ✓ |
| `failed_checks`: `diagnostic_hint` | ✓ | ✓ | ✓ |
| `failed_checks`: traces, expected, observed, final-state fields | ✗ | ✓ | ✓ |
| `localization` | ✗ | ✗ | ✓ |

For `localized`, if the score report has no `localization` object, the projector emits empty arrays for `suspicious_states`, `suspicious_transitions`, `missing_transition_candidates`, and `extra_transition_candidates`.

## Preventing diagnostic leakage

Conditions C (`binary`), D (`trace`), and E (`localized`) must receive **different** projected artefacts:

- **C** cannot see execution witnesses or structural localization (enforced in code and schema).
- **D** cannot see localization hints meant for E.
- **Repair prompts** must read the frozen diagnostic JSON path, not the full score report or validation-oracle results.

Only score reports from **feedback** oracle suites should be projected into repair-channel diagnostics. Validation scoring remains on the repair run record.

## CLI

```bash
python scripts/score_repair.py \
  --fsm candidates/iter_000.json \
  --oracles datasets/oracle_suites/feedback_v1.json \
  --output scores/iter_000_score.json

python scripts/build_diagnostic.py \
  --score-report scores/iter_000_score.json \
  --level trace \
  --case-id tlc_01 \
  --run-id tlc_01__patch_trace_feedback__r001 \
  --iteration-index 0 \
  --output feedback/iter_000.json
```

| Flag | Role |
|------|------|
| `--score-report` | Input score report path |
| `--level` | `binary`, `trace`, or `localized` |
| `--case-id`, `--run-id`, `--iteration-index` | Identity and `diagnostic_id` |
| `--output` | Destination diagnostic JSON |

Exit `0` on success; `2` on build or validation error.

## Repair prompts (planned)

After each repair iteration:

1. Score the candidate → score report.
2. `build_diagnostic.py --level` matching the repair condition.
3. Store output as `feedback_summary_path` on the repair run.
4. Prompt templates under [`prompts/`](../prompts/) consume **only** that diagnostic file.

## See also

- [`scoring_interface.md`](scoring_interface.md) — score report format
- [`diagnostic_model.md`](diagnostic_model.md) — diagnostic artefact (v2.0.0)
- [`experimental_conditions.md`](experimental_conditions.md) — conditions C–E
- [`scripts/README.md`](../scripts/README.md)
