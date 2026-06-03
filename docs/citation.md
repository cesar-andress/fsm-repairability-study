# Citation and archival policy

## Recommended citation

When you cite this software artifact in a paper, report, or replication package, use the **Zenodo DOI** for the archived release, not an informal GitHub URL alone.

**Andrés, C. (2026).** *fsm-repairability-study: Core Experimental Infrastructure for Behavioural Repairability Studies* (Version 1.0.0) [Computer software]. Zenodo. https://doi.org/10.5281/zenodo.20529518

Machine-readable metadata: [`CITATION.cff`](../CITATION.cff) at the repository root (CFF 1.2.0).

## Persistent identifiers

| Resource | Identifier |
|----------|------------|
| **DOI (Zenodo)** | [10.5281/zenodo.20529518](https://doi.org/10.5281/zenodo.20529518) |
| **GitHub repository** | [https://github.com/cesar-andress/fsm-repairability-study](https://github.com/cesar-andress/fsm-repairability-study) |
| **Archived release** | v1.0.0 — Core Experimental Infrastructure (Zenodo record) |

## GitHub `main` vs Zenodo archived releases

| | GitHub (`main` branch) | Zenodo archived release |
|--|------------------------|-------------------------|
| **Purpose** | Ongoing development, documentation fixes, metadata updates | Long-term preservation and **citable** snapshot |
| **Mutability** | May change after publication | **Immutable** for a given Zenodo version |
| **What to cite** | Use only if you explicitly need the latest commit; prefer Zenodo for reproducibility claims | **Preferred** for papers and replication audits |

The Zenodo deposit associated with DOI [10.5281/zenodo.20529518](https://doi.org/10.5281/zenodo.20529518) corresponds to the **initial public infrastructure** release (**v1.0.0**). Later commits on GitHub (for example citation-metadata fixes on `main`) do not alter that frozen archive unless a **new Zenodo version** is published.

## Scientific claims and archived releases

- **Infrastructure claims** (schemas exist, scoring is deterministic, dry-run orchestration shape) should reference the **archived** artifact version you verified, ideally via the Zenodo DOI.
- **Empirical claims** (repair success rates, condition comparisons, model sensitivity outcomes) must cite the **specific frozen campaign or results deposit** cited in the paper. The v1.0.0 infrastructure archive does **not** include large-scale empirical results; see [`ARTIFACT_SCOPE.md`](../ARTIFACT_SCOPE.md).
- Do not attribute unpublished results or private experiments to the public Zenodo record.

## Related documentation

- Artifact boundary: [`ARTIFACT_SCOPE.md`](../ARTIFACT_SCOPE.md)
- Reproducibility modes: [`REPRODUCIBILITY.md`](../REPRODUCIBILITY.md)
- Release notes (v1.0.0): [`RELEASE_NOTES_v1.0.0.md`](../RELEASE_NOTES_v1.0.0.md)
