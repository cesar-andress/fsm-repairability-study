# Results

Aggregated outputs for paper claims: repair rates, attempt distributions, and condition contrasts.

## Planned layout

```
results/
  MANIFEST.md        # Model tags, Ollama version, file hashes (at release)
  summary/           # CSV or JSON tables cited in the paper (by condition_id)
  figures/           # Optional exported plots (vector preferred)
  frozen_runs/       # Repair runs for audit without Ollama
  sensitivity/       # Optional model-stratified summaries (secondary)
```

## Policy

- Only results **needed to reproduce reported claims** are deposited.
- Raw LLM transcripts are omitted unless required for a specific audit trail (see `DATA_STATEMENT.md`).
- Regenerated outputs should match frozen files within documented tolerances (exact match for JSON summaries).

## Status

Empty except placeholders. Populate after analysis freeze.
