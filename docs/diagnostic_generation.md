# Diagnostic generation

Deterministic conversion from a [`score_repair.py`](../scripts/score_repair.py) **score report** to a **diagnostic JSON** artefact that validates against [`schemas/diagnostic.schema.json`](../schemas/diagnostic.schema.json) v2.0.0.

Formal definition of the artefact: [`diagnostic_model.md`](diagnostic_model.md).

## Deterministic projection

`scripts/build_diagnostic.py` is a pure projector:

| Guarantee | How |
|-----------|-----|
| No LLM, no patches | Reads/writes JSON only |
| Score report unchanged | Input dict is never mutated |
| Stable identity | `diagnostic_id = diag_{case_id}_{run_id}_i{N}_{level}` |
| Stable metrics | BPR recomputed as `passed_tests / total_tests` (not copied from input) |
| Audit | SHA-256 of the score report file in `reproducibility.checksums` |

Same score report, level, and identity arguments produce the same diagnostic except `reproducibility.generated_at` when not fixed by the caller.

## Failure type normalization

`score_repair.py` may emit legacy or scorer-specific `failure_type` strings that are not listed in the diagnostic schema. During projection, `build_diagnostic.py` maps aliases before writing `failed_checks` and before aggregating `failure_categories`:

| Score report `failure_type` | Diagnostic `failure_type` |
|---------------------------|---------------------------|
| `invalid_test_spec` | `invalid_check_spec` |
| `invalid_oracle_spec` | `invalid_check_spec` |
| `unsupported_test_type` | `unsupported_check_type` |

All other values pass through unchanged. The score report file is never modified.

## Score report → diagnostic mapping

| Score report | Diagnostic |
|--------------|------------|
| `suite_id` / `oracle_suite_id` / `oracle_suite_path` stem | `scoring_summary.oracle_suite_id` |
| `total_tests` | `scoring_summary.total_checks` |
| `passed_tests` | `scoring_summary.passed_checks` |
| `failed_tests` | `scoring_summary.failed_checks` |
| recomputed | `scoring_summary.bpr` |
| `failures[]` | `failed_checks[]` (`test_id` → `check_id`) |
| `failures[].trace` | `failed_checks[].input_trace` (trace / localized) |
| `failures[].expected`, `observed` | same (trace / localized) |
| `failures[].diagnostic_hint` | `failed_checks[].diagnostic_hint` (binary may include) |
| `localization` (optional) | `localization` (localized only) |
| `fsm_path` | `reproducibility.source_fsm_path` |
| `oracle_suite_path` | `reproducibility.oracle_suite_path` |
| `score_schema_version` | `reproducibility.scorer_version` |
| score report bytes | `reproducibility.checksums.score_report_sha256` |

## Information filtering by level

| Field group | `binary` | `trace` | `localized` |
|-------------|----------|---------|-------------|
| `scoring_summary`, `failure_categories` | ✓ | ✓ | ✓ |
| `check_id`, `oracle_type`, `failure_type`, `diagnostic_hint` | ✓ | ✓ | ✓ |
| `input_trace`, `expected`, `observed`, final-state fields | ✗ | ✓ | ✓ |
| `localization` | ✗ | ✗ | ✓ |

For `localized`, absent `localization` in the score report yields empty arrays for `suspicious_states`, `suspicious_transitions`, `missing_transition_candidates`, and `extra_transition_candidates`.

## Leakage prevention

Experimental conditions C (`binary`), D (`trace`), and E (`localized`) must receive different projected artefacts:

- Condition **C** must not see traces, expected/observed witnesses, or localization.
- Condition **D** must not see localization meant for E.
- **Repair prompts** must consume the frozen diagnostic JSON path only—not the full score report or validation-oracle results.

Project feedback-suite score reports only; keep validation scoring on the repair run record.

## CLI

```bash
python scripts/score_repair.py \
  --fsm candidate.json \
  --oracles suite.json \
  --output score_report.json

python scripts/build_diagnostic.py \
  --score-report score_report.json \
  --level trace \
  --case-id case01 \
  --run-id case01_run01 \
  --iteration-index 0 \
  --output diagnostic.json
```

## Later use by repair prompts

Planned pipeline per repair iteration:

1. Score candidate → `score_report.json`.
2. `build_diagnostic.py --level` matching repair condition (`patch_binary_feedback` → `binary`, etc.).
3. Save output as `feedback_summary_path` on the repair run.
4. Prompt templates under [`prompts/`](../prompts/) embed summaries from **diagnostic.json** only.

## See also

- [`scoring_interface.md`](scoring_interface.md)
- [`scripts/README.md`](../scripts/README.md)
