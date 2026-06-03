# Release notes — v1.0.1

**Title:** v1.0.1 — Zenodo citation metadata fix  
**Date:** 2026-06-03

## Overview

Release **v1.0.1** is a **metadata-only** update. It corrects [`CITATION.cff`](CITATION.cff) so Zenodo can archive the GitHub release without falling back to a generated example citation file.

Release **v1.0.0** remains the first **core experimental infrastructure** release (schemas, scripts, tests, documentation). v1.0.1 does not supersede that scientific scope; it only fixes publication metadata.

## What changed

| Item | Change |
|------|--------|
| `CITATION.cff` | Valid CFF 1.2.0 with author, ORCID, repository URL, version `1.0.1`, and abstract |
| `README.md` | Release section notes v1.0.0 vs v1.0.1 |
| `RELEASE_NOTES_v1.0.1.md` | This file |

## What did not change

- JSON schemas under `schemas/`
- Python scripts under `scripts/`
- Pytest suite and fixtures under `tests/`
- Prompt templates, study design docs, or deterministic tooling behaviour
- Empirical study content (still none in the public artifact)

No DOI is assigned in this commit; add the Zenodo DOI to `CITATION.cff` after the archive is published.

## Zenodo archival

GitHub release **v1.0.0** failed Zenodo integration when `CITATION.cff` contained placeholder authors (`SURNAME`), placeholder ORCID, and a non-existent `ORG` repository URL. Zenodo then displayed a **generated example** `CITATION.cff` instead of repository metadata.

After tagging **v1.0.1** (when you choose to publish it), re-trigger or create the Zenodo-GitHub release deposit so the archive picks up the corrected file.

## Relation to v1.0.0

- **v1.0.0** — [`RELEASE_NOTES_v1.0.0.md`](RELEASE_NOTES_v1.0.0.md), [`ARTIFACT_SCOPE.md`](ARTIFACT_SCOPE.md)
- **v1.0.1** — citation fix only; same infrastructure artifact

## Reproducibility

Unchanged from v1.0.0. **Python 3.12 or newer is required.** Quick check:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r environment/requirements.txt
python -m pytest
```

See [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md).
