# Contributing

This document describes how to maintain the public replication artifact for the behavioural repairability study.

## Public artifact discipline

This repository is intended for **GitHub** and **Zenodo**. It must remain a small, clean, reproducible publication artifact.

**Include only:**

- Final or paper-reported datasets and oracle definitions
- Frozen repair prompts and condition configuration
- JSON schemas and minimal deterministic scripts
- Aggregated results and frozen repair runs needed to verify claims
- Documentation for study design, terminology, reproducibility, and data scope

**Do not include:**

- Private research workspace material (manuscript drafts, reviewer notes, exploratory scripts)
- Raw generation or repair campaigns not required for reported results
- Temporary files, logs, caches, virtual environments, or local model output dumps
- Unpublished or non-redistributable content

Exploratory work belongs in the separate private research workspace, not in this repository. Export only frozen subsets after review.

## Commit message format

Every commit in this repository must use:

```
<type>: <short imperative summary>
```

### Allowed types

| Type | Use for |
|------|---------|
| `init` | Initial repository or major skeleton setup |
| `docs` | Documentation only |
| `data` | Datasets, oracle suites, frozen inputs |
| `schema` | JSON Schema changes |
| `script` | Python scripts and tooling |
| `test` | Tests and test configuration |
| `results` | Published summaries and frozen runs |
| `refactor` | Non-functional code or layout changes |
| `chore` | Maintenance (e.g. `.gitignore`, dependencies) |

### Rules

- Use **English** only.
- Use **lowercase** type prefix.
- Use **imperative mood** in the summary (e.g. "add", "fix", "update").
- Keep the subject line **under 72 characters**.
- Do not add a commit body unless the change genuinely needs explanation.
- Do not mention tools used to author the change.
- Do not mention private research notes or unpublished manuscript content.

### Valid examples

```
init: create public artifact skeleton
docs: define repository scope
schema: add repair case schema
script: add patch application stub
test: cover patch schema validation
docs: add reproducibility workflow
chore: update gitignore rules
```

### Invalid examples

Commit subjects that name authoring tools, private drafts, or non-scientific meta-commentary are not acceptable for this artifact.

## Pre-commit checklist

Before each commit:

1. Run `git status` and review all staged and unstaged paths.
2. Confirm **no private files** are included (nothing from the private research workspace).
3. Confirm **no raw exploratory outputs** are included (campaign logs, scratch runs, local caches).
4. Run tests if available:
   ```bash
   python -m pytest
   ```
   If tests are not yet configured, note that explicitly before committing.
5. Update **documentation** if the repository structure, conditions, schemas, or replication workflow changed.

## Scope of changes

- Apply contribution rules only within this public artifact repository.
- Keep commits focused; prefer several small commits over one large mixed commit when practical.
- Do not commit secrets, credentials, or machine-specific paths that are not part of the documented replication setup.
