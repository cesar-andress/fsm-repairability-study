# Repair case test fixtures

Synthetic v2.0.0 examples for schema contract tests only. Not campaign data.

| File | Role |
|------|------|
| `not_started.json` | Valid entry case (`repair_status: not_started`) |
| `complete_repair.json` | Valid successful repair with full history |
| `overfitting_detected.json` | Valid failed repair with `overfitting_detected: true` |
| `invalid_missing_case_id.json` | Rejects schema (missing `identity.case_id`) |
| `invalid_bpr_out_of_range.json` | Rejects schema (`initial_bpr` > 1) |
| `invalid_outcome_history_mismatch.json` | Rejects schema (`not_started` with non-empty `iterations`) |

Validated by [`tests/test_repair_case_schema.py`](../../test_repair_case_schema.py).
