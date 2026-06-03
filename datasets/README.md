# Datasets

Frozen inputs for the behavioural repairability study. Files are added before Zenodo release; this directory currently holds structure and documentation only.

## Contents (planned)

| Subdirectory | Description |
|--------------|-------------|
| [`repair_cases/`](repair_cases/) | One folder or file bundle per repair case |
| [`oracle_suites/`](oracle_suites/) | Behavioural oracle definitions referenced by cases |

## Conventions (planned)

- Each repair case is self-describing via `schemas/repair_case.schema.json`.
- Oracle suite ids are stable strings referenced from case metadata.
- No dataset file in this repository should require live LLM API access to interpret.

## Placeholder policy

JSON data files are gitignored until explicitly released (see root `.gitignore`). Use `.gitkeep` to preserve empty directories in version control.

See [`../DATA_STATEMENT.md`](../DATA_STATEMENT.md) for inclusion boundaries.
