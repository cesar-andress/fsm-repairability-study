#!/usr/bin/env python3
"""
Assemble a Zenodo-oriented replication bundle from the private paper workspace.

Creates:
  <output-dir>/          (default: <paper-root>/replication_package)
  <zip-path>             (default: <paper-root>/replication_package.zip)

Contents: experiment summaries, selected repair-run artefacts, paper tables/figures,
metadata manifest, and README.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

PILOT_VARIANTS: tuple[tuple[str, str, str], ...] = (
    ("default", "frozen_pilot_001", "frozen_pilot_001"),
    (
        "operation-aware",
        "diagnostic_granularity_pilot_diverse_operation_aware_001",
        "operation_aware_001",
    ),
    ("operation-inferred", "frozen_main_pilot_001", "frozen_main_pilot_001"),
)

SUMMARY_FILES = (
    "diagnostic_granularity_summary.json",
    "diagnostic_granularity_results.csv",
)

ANALYSIS_FILES = (
    "repair_outcome_summary.json",
    "repair_outcome_summary.csv",
    "patch_failure_summary.json",
    "patch_failure_summary.csv",
    "successful_repairs.json",
    "successful_repairs.csv",
    "regression_summary.json",
    "regression_summary.csv",
)

REPAIR_RUN_ARTEFACTS = (
    ("repair_run.json", "repair_run.json"),
    ("run/patches/iter_000_source.json", "patch_source.json"),
    ("ollama/patch.json", "ollama_patch.json"),
    ("run/scores/iter_000_input_validation.json", "scores_validation_before.json"),
    ("run/scores/iter_001_validation.json", "scores_validation_after.json"),
    ("run/diagnostics/iter_000_feedback.json", "diagnostic_feedback.json"),
    ("error.txt", "error.txt"),
)

RESULTS_CSV = "main_results_table.csv"
PACKAGE_README = "README.md"
METADATA_JSON = "metadata.json"
ZIP_NAME = "replication_package.zip"


class PackageError(Exception):
    """Raised when required inputs are missing."""


@dataclass(frozen=True)
class SelectedRun:
    pilot_slug: str
    case_id: str
    condition: str
    reason: str


def default_paper_root() -> Path:
    candidate = REPO_ROOT.parent / "paper"
    return candidate if candidate.is_dir() else REPO_ROOT / "paper"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def git_revision(repo: Path) -> str | None:
    if not (repo / ".git").exists():
        return None
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def load_selection_from_analysis(
    pilot_dir: Path, pilot_slug: str
) -> list[SelectedRun]:
    selected: list[SelectedRun] = []
    analysis = pilot_dir / "analysis"
    for json_name, reason in (
        ("successful_repairs.json", "effective_repair"),
        ("regression_summary.json", "behavioural_regression"),
    ):
        path = analysis / json_name
        if not path.is_file():
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        key = "repairs" if "repairs" in doc else "regressions"
        for row in doc.get(key, []):
            selected.append(
                SelectedRun(
                    pilot_slug=pilot_slug,
                    case_id=str(row["case_id"]),
                    condition=str(row["condition"]),
                    reason=reason,
                )
            )
    return selected


def dedupe_selection(runs: list[SelectedRun]) -> list[SelectedRun]:
    seen: set[tuple[str, str, str]] = set()
    out: list[SelectedRun] = []
    for run in runs:
        key = (run.pilot_slug, run.case_id, run.condition)
        if key in seen:
            continue
        seen.add(key)
        out.append(run)
    return sorted(out, key=lambda r: (r.pilot_slug, r.case_id, r.condition))


def pilot_dir_for_slug(experiments_dir: Path, slug: str) -> Path | None:
    for _variant, folder, short in PILOT_VARIANTS:
        if short == slug or folder == slug:
            return experiments_dir / folder
    return None


def pilot_slug_lookup(experiments_dir: Path, pilot_dir: Path) -> str:
    for _variant, folder, short in PILOT_VARIANTS:
        if pilot_dir == experiments_dir / folder:
            return short
    return pilot_dir.name


def copy_summaries(
    experiments_dir: Path,
    bundle_root: Path,
    manifest: list[dict[str, Any]],
) -> None:
    summaries_dir = bundle_root / "summaries"
    summaries_dir.mkdir(parents=True, exist_ok=True)

    results_src = experiments_dir.parent / "results" / RESULTS_CSV
    if results_src.is_file():
        dest = summaries_dir / RESULTS_CSV
        shutil.copy2(results_src, dest)
        manifest.append({"kind": "results_table", "path": f"summaries/{RESULTS_CSV}"})

    for variant, folder, slug in PILOT_VARIANTS:
        pilot_dir = experiments_dir / folder
        if not pilot_dir.is_dir():
            raise PackageError(f"missing experiment directory: {pilot_dir}")
        pilot_dest = summaries_dir / "experiments" / slug
        pilot_dest.mkdir(parents=True, exist_ok=True)
        for name in SUMMARY_FILES:
            src = pilot_dir / name
            if src.is_file():
                shutil.copy2(src, pilot_dest / name)
        analysis_src = pilot_dir / "analysis"
        if analysis_src.is_dir():
            analysis_dest = pilot_dest / "analysis"
            analysis_dest.mkdir(parents=True, exist_ok=True)
            for name in ANALYSIS_FILES:
                src = analysis_src / name
                if src.is_file():
                    shutil.copy2(src, analysis_dest / name)
        manifest.append(
            {
                "kind": "pilot_summaries",
                "variant": variant,
                "slug": slug,
                "source_dir": str(pilot_dir),
            }
        )


def copy_tables_and_figures(paper_root: Path, bundle_root: Path, manifest: list) -> None:
    for sub, label in (("tables", "tables"), ("figures", "figures")):
        src_dir = paper_root / sub
        if not src_dir.is_dir():
            continue
        dest_dir = bundle_root / sub
        dest_dir.mkdir(parents=True, exist_ok=True)
        for path in sorted(src_dir.iterdir()):
            if path.is_file():
                shutil.copy2(path, dest_dir / path.name)
        manifest.append({"kind": label, "file_count": len(list(dest_dir.iterdir()))})


def copy_selected_runs(
    experiments_dir: Path,
    bundle_root: Path,
    selected: list[SelectedRun],
    file_manifest: list[dict[str, str]],
) -> None:
    runs_root = bundle_root / "repair_runs"
    for sel in selected:
        pilot_dir = pilot_dir_for_slug(experiments_dir, sel.pilot_slug)
        if pilot_dir is None:
            pilot_dir = experiments_dir / sel.pilot_slug
        cond_dir = pilot_dir / "runs" / sel.case_id / sel.condition
        if not cond_dir.is_dir():
            continue
        dest_dir = (
            runs_root
            / sel.pilot_slug
            / sel.case_id
            / sel.condition
        )
        dest_dir.mkdir(parents=True, exist_ok=True)
        (dest_dir / "selection_reason.txt").write_text(
            sel.reason + "\n", encoding="utf-8"
        )
        for rel_src, rel_dest in REPAIR_RUN_ARTEFACTS:
            src = cond_dir / rel_src
            dest = dest_dir / rel_dest
            if src.is_file():
                shutil.copy2(src, dest)
                file_manifest.append(
                    {
                        "pilot": sel.pilot_slug,
                        "case_id": sel.case_id,
                        "condition": sel.condition,
                        "file": rel_dest,
                        "sha256": sha256_file(dest),
                    }
                )


def build_readme(bundle_root: Path, metadata: dict[str, Any]) -> None:
    pilots = ", ".join(v for v, _, _ in PILOT_VARIANTS)
    text = f"""# Replication package — Diagnostic Granularity FSM Repair Pilot

This bundle supports reproduction and inspection of a **pilot-scale**
diagnostic granularity study for LLM-based FSM patch repair.

## Contents

| Path | Description |
|------|-------------|
| `metadata.json` | Manifest, provenance, and file inventory |
| `summaries/` | Aggregated CSV/JSON summaries per frozen experiment arm |
| `summaries/{RESULTS_CSV}` | Cross-variant main results table |
| `tables/` | LaTeX tables used in the paper |
| `figures/` | PDF figures used in the paper |
| `repair_runs/` | Selected case--condition artefacts (effective repairs and regressions) |

## Experiment arms

{pilots}

## Selected repair runs

Runs are included when listed in `successful_repairs.json` or
`regression_summary.json` under each pilot's `analysis/` folder.
Each selected folder contains `repair_run.json`, patch sources, validation
scores before/after repair, and diagnostics when present.

## Public study code

Analysis scripts live in the **fsm-repairability-study** repository
(see `metadata.json` → `study_repository`).

## Citation

Use the paper DOI when available; until then cite the Zenodo record
for this package and the public code repository revision in `metadata.json`.

## License

TODO: Set SPDX license before Zenodo upload (metadata `license_spdx`).
"""
    (bundle_root / PACKAGE_README).write_text(text, encoding="utf-8")


def build_metadata(
    *,
    paper_root: Path,
    bundle_root: Path,
    selected: list[SelectedRun],
    file_manifest: list[dict[str, str]],
    study_repo: Path,
) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "title": "Diagnostic Granularity FSM Repair Pilot — Replication Package",
        "description": (
            "Frozen summaries, selected repair-run artefacts, and paper tables/figures "
            "for a pilot comparing binary, trace, and localized diagnostic feedback."
        ),
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "paper_root": str(paper_root.resolve()),
        "bundle_root": str(bundle_root.resolve()),
        "study_repository": {
            "path": str(study_repo.resolve()),
            "revision": git_revision(study_repo),
        },
        "license_spdx": "TODO",
        "upload_target": "Zenodo",
        "pilots": [
            {"variant": v, "source_folder": f, "bundle_slug": s}
            for v, f, s in PILOT_VARIANTS
        ],
        "selected_repair_run_count": len(selected),
        "selected_repair_runs": [
            {
                "pilot_slug": r.pilot_slug,
                "case_id": r.case_id,
                "condition": r.condition,
                "reason": r.reason,
            }
            for r in selected
        ],
        "artefact_files": file_manifest,
    }


def create_zip(bundle_dir: Path, zip_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    if zip_path.is_file():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(bundle_dir.rglob("*")):
            if path.is_file():
                arcname = path.relative_to(bundle_dir.parent)
                zf.write(path, arcname)


def package_replication_bundle(
    *,
    paper_root: Path,
    bundle_dir: Path,
    zip_path: Path,
    study_repo: Path,
    clean: bool = True,
) -> tuple[Path, Path]:
    paper_root = paper_root.resolve()
    experiments_dir = paper_root / "experiments"
    if not experiments_dir.is_dir():
        raise PackageError(f"missing experiments directory: {experiments_dir}")

    if clean and bundle_dir.exists():
        shutil.rmtree(bundle_dir)

    bundle_dir.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, Any]] = []
    file_manifest: list[dict[str, str]] = []

    copy_summaries(experiments_dir, bundle_dir, manifest)
    copy_tables_and_figures(paper_root, bundle_dir, manifest)

    selected: list[SelectedRun] = []
    for _variant, folder, slug in PILOT_VARIANTS:
        pilot_dir = experiments_dir / folder
        selected.extend(load_selection_from_analysis(pilot_dir, slug))
    selected = dedupe_selection(selected)

    copy_selected_runs(experiments_dir, bundle_dir, selected, file_manifest)

    metadata = build_metadata(
        paper_root=paper_root,
        bundle_root=bundle_dir,
        selected=selected,
        file_manifest=file_manifest,
        study_repo=study_repo,
    )
    metadata["packaging"] = {"manifest": manifest}
    (bundle_dir / METADATA_JSON).write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    build_readme(bundle_dir, metadata)

    create_zip(bundle_dir, zip_path)
    return bundle_dir, zip_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paper-root", type=Path, default=None)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Bundle directory (default: <paper-root>/replication_package)",
    )
    parser.add_argument(
        "--zip-path",
        type=Path,
        default=None,
        help="Zip output (default: <paper-root>/replication_package.zip)",
    )
    parser.add_argument(
        "--study-repo",
        type=Path,
        default=REPO_ROOT,
        help="Path to fsm-repairability-study for revision metadata",
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Do not remove existing bundle directory before packaging",
    )
    args = parser.parse_args(argv)

    paper_root = (args.paper_root or default_paper_root()).resolve()
    bundle_dir = (args.output_dir or paper_root / "replication_package").resolve()
    zip_path = (args.zip_path or paper_root / ZIP_NAME).resolve()

    try:
        bundle, zpath = package_replication_bundle(
            paper_root=paper_root,
            bundle_dir=bundle_dir,
            zip_path=zip_path,
            study_repo=args.study_repo.resolve(),
            clean=not args.no_clean,
        )
    except PackageError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"wrote {bundle}")
    print(f"wrote {zpath}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
