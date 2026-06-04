"""Tests for the private paper LaTeX skeleton under ../paper."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PAPER_ROOT = REPO_ROOT.parent / "paper"

SECTION_FILES = [
    "sections/01_introduction.tex",
    "sections/02_background.tex",
    "sections/03_research_questions.tex",
    "sections/04_methodology.tex",
    "sections/05_results.tex",
    "sections/06_discussion.tex",
    "sections/07_threats_to_validity.tex",
    "sections/08_related_work.tex",
    "sections/09_conclusion.tex",
]

TABLE_FILES = [
    "tables/main_results.tex",
    "tables/repair_outcomes.tex",
    "tables/failure_analysis.tex",
]

FIGURE_FILES = [
    "figures/repair_success_rate.pdf",
    "figures/patch_failure_breakdown.pdf",
    "figures/evaluated_cases_by_variant.pdf",
]


@pytest.mark.skipif(not PAPER_ROOT.is_dir(), reason="paper workspace not present")
def test_paper_skeleton_files_exist() -> None:
    assert (PAPER_ROOT / "main.tex").is_file()
    assert (PAPER_ROOT / "macros.tex").is_file()
    assert (PAPER_ROOT / "references.bib").is_file()
    for rel in SECTION_FILES:
        assert (PAPER_ROOT / rel).is_file(), rel
    for rel in TABLE_FILES:
        assert (PAPER_ROOT / rel).is_file(), rel
    for rel in FIGURE_FILES:
        assert (PAPER_ROOT / rel).is_file(), rel


@pytest.mark.skipif(not PAPER_ROOT.is_dir(), reason="paper workspace not present")
def test_sections_contain_todo_markers() -> None:
    combined = "\n".join(
        (PAPER_ROOT / rel).read_text(encoding="utf-8") for rel in SECTION_FILES
    )
    assert r"\pTODO{" in combined
    assert combined.count(r"\pTODO{") >= 20


@pytest.mark.skipif(not PAPER_ROOT.is_dir(), reason="paper workspace not present")
def test_main_inputs_all_sections() -> None:
    main = (PAPER_ROOT / "main.tex").read_text(encoding="utf-8")
    for rel in SECTION_FILES:
        assert rel.replace(".tex", "") in main or rel in main


@pytest.mark.skipif(shutil.which("pdflatex") is None, reason="pdflatex not installed")
@pytest.mark.skipif(not PAPER_ROOT.is_dir(), reason="paper workspace not present")
def test_main_tex_compiles_to_pdf(tmp_path: Path) -> None:
    work = tmp_path / "paper_build"
    work.mkdir()
    for name in ("main.tex", "macros.tex", "references.bib", "Makefile"):
        src = PAPER_ROOT / name
        if src.is_file():
            (work / name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    for folder in ("sections", "tables", "figures"):
        src_dir = PAPER_ROOT / folder
        if src_dir.is_dir():
            dest = work / folder
            dest.mkdir()
            for path in src_dir.iterdir():
                if path.is_file():
                    (dest / path.name).write_bytes(path.read_bytes())

    for cmd in (
        ["pdflatex", "-interaction=nonstopmode", "main.tex"],
        ["bibtex", "main"],
        ["pdflatex", "-interaction=nonstopmode", "main.tex"],
        ["pdflatex", "-interaction=nonstopmode", "main.tex"],
    ):
        subprocess.run(
            cmd,
            cwd=work,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    pdf = work / "main.pdf"
    assert pdf.is_file(), "main.pdf was not produced"
    assert pdf.stat().st_size > 10_000
    assert pdf.read_bytes()[:4] == b"%PDF"

    tex = (work / "sections" / "05_results.tex").read_text(encoding="utf-8")
    assert r"\input{tables/main_results}" in tex
    assert "evaluated_cases_by_variant" in tex
