#!/usr/bin/env python3
"""
Build a publication-oriented taxonomy of LLM-generated FSM patch failures.

Reads patch-application failures from a diagnostic granularity pilot
(via analyze_patch_failures) and writes:
  analysis/patch_failure_taxonomy.json
  analysis/patch_failure_taxonomy.tex
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from analyze_patch_failures import (  # noqa: E402
    AnalysisError,
    FailureRecord,
    analyze_patch_failures,
)

ANALYSIS_DIR = "analysis"
JSON_NAME = "patch_failure_taxonomy.json"
TEX_NAME = "patch_failure_taxonomy.tex"

TAXONOMY_CLASSES: tuple[str, ...] = (
    "duplicate_transition",
    "missing_state",
    "transition_not_found",
    "invalid_operation_semantics",
)

CLASS_DEFINITIONS: dict[str, str] = {
    "duplicate_transition": (
        "Proposed add_transition on (from, event) already present in the candidate FSM."
    ),
    "missing_state": (
        "Referenced source or target state is not declared in the candidate FSM."
    ),
    "transition_not_found": (
        "remove_transition or update_transition targets a non-existent edge."
    ),
    "invalid_operation_semantics": (
        "Operation violates patch-engine rules (e.g. self-loop, unsupported op, schema)."
    ),
}

MAX_EXAMPLES_PER_CLASS = 2
MAX_ERROR_LEN = 120


def escape_latex(text: str) -> str:
    replacements = (
        ("\\", r"\textbackslash{}"),
        ("&", r"\&"),
        ("%", r"\%"),
        ("$", r"\$"),
        ("#", r"\#"),
        ("_", r"\_"),
        ("{", r"\{"),
        ("}", r"\}"),
    )
    out = text
    for old, new in replacements:
        out = out.replace(old, new)
    return out


def truncate_message(msg: str, limit: int = MAX_ERROR_LEN) -> str:
    msg = " ".join(msg.split())
    if len(msg) <= limit:
        return msg
    return msg[: limit - 3] + "..."


def example_signature(rec: FailureRecord) -> str:
    return rec.failure_class + "|" + rec.error_message[:80]


def select_examples(
    records: list[FailureRecord], *, max_per_class: int = MAX_EXAMPLES_PER_CLASS
) -> list[dict[str, Any]]:
    by_class: dict[str, list[FailureRecord]] = {c: [] for c in TAXONOMY_CLASSES}
    for rec in records:
        if rec.failure_class in by_class:
            by_class[rec.failure_class].append(rec)

    examples: list[dict[str, Any]] = []
    seen_sigs: set[str] = set()
    for failure_class in TAXONOMY_CLASSES:
        picked = 0
        for rec in by_class[failure_class]:
            sig = example_signature(rec)
            if sig in seen_sigs:
                continue
            seen_sigs.add(sig)
            examples.append(
                {
                    "failure_class": failure_class,
                    "case_id": rec.case_id,
                    "condition": rec.condition,
                    "system_id": rec.system_id,
                    "operation_type": rec.operation_type,
                    "source_state": rec.source_state,
                    "event": rec.event,
                    "target_state": rec.target_state,
                    "error_message": rec.error_message,
                }
            )
            picked += 1
            if picked >= max_per_class:
                break
    return examples


def build_taxonomy(
    records: list[FailureRecord], aggregates: dict[str, Any]
) -> dict[str, Any]:
    total = len(records)
    by_class = Counter(rec.failure_class for rec in records)
    unclassified = sum(
        by_class.get(k, 0) for k in by_class if k not in TAXONOMY_CLASSES
    )

    taxonomy: dict[str, Any] = {}
    for failure_class in TAXONOMY_CLASSES:
        count = by_class.get(failure_class, 0)
        share = count / total if total else 0.0
        by_condition: Counter[str] = Counter()
        by_operation: Counter[str] = Counter()
        for rec in records:
            if rec.failure_class != failure_class:
                continue
            by_condition[rec.condition] += 1
            op = rec.operation_type or "(unknown)"
            by_operation[op] += 1
        taxonomy[failure_class] = {
            "definition": CLASS_DEFINITIONS[failure_class],
            "count": count,
            "share": round(share, 4),
            "share_percent": round(100.0 * share, 1),
            "by_condition": dict(sorted(by_condition.items())),
            "by_operation_type": dict(sorted(by_operation.items())),
        }

    return {
        "total_failures": total,
        "taxonomy_classes": list(TAXONOMY_CLASSES),
        "classes": taxonomy,
        "unclassified_count": unclassified,
        "unclassified_by_class": {
            k: v for k, v in sorted(by_class.items()) if k not in TAXONOMY_CLASSES
        },
        "by_condition": aggregates.get("by_condition", {}),
        "by_operation_type": aggregates.get("by_operation_type", {}),
        "examples": select_examples(records),
    }


def render_statistics_table(taxonomy_body: dict[str, Any]) -> str:
    rows: list[str] = []
    total = taxonomy_body["total_failures"]
    for failure_class in TAXONOMY_CLASSES:
        info = taxonomy_body["classes"][failure_class]
        label = failure_class.replace("_", r"\_")
        defn = escape_latex(CLASS_DEFINITIONS[failure_class])
        rows.append(
            f"\\texttt{{{label}}} & {defn} & {info['count']} & "
            f"{info['share_percent']:.1f}\\% \\\\"
        )
    lines = [
        r"\begin{table}[t]",
        r"\centering",
        r"\caption{Taxonomy of LLM-generated FSM patch application failures "
        r"(pilot aggregate). Counts sum to "
        f"{total} rejected operations across conditions C--E.}}",
        r"\label{tab:patch_failure_taxonomy}",
        r"\begin{tabular}{@{}p{0.22\linewidth}p{0.46\linewidth}rr@{}}",
        r"\toprule",
        r"Class & Definition & Count & Share \\",
        r"\midrule",
        *rows,
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
    ]
    return "\n".join(lines) + "\n"


def render_examples_block(examples: list[dict[str, Any]]) -> str:
    if not examples:
        return ""
    lines = [
        r"\paragraph{Illustrative failure instances.}",
        r"\begin{itemize}",
    ]
    for ex in examples:
        cls = escape_latex(ex["failure_class"])
        case = escape_latex(ex["case_id"])
        cond = ex["condition"]
        op = escape_latex(ex.get("operation_type") or "unknown")
        msg = escape_latex(truncate_message(ex["error_message"]))
        edge = ""
        if ex.get("source_state") and ex.get("event"):
            edge = (
                f" ({escape_latex(ex['source_state'])}"
                f"--{escape_latex(ex['event'])}"
                f"--> {escape_latex(ex.get('target_state') or '?')})"
            )
        lines.append(
            f"  \\item \\textbf{{{cls}}} [{cond}]: "
            f"\\texttt{{{op}}}{edge} on \\texttt{{{case}}}. "
            f"\\emph{{{msg}}}"
        )
    lines.append(r"\end{itemize}")
    return "\n".join(lines) + "\n\n"


def render_taxonomy_tex(taxonomy_body: dict[str, Any]) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    header = (
        f"% Auto-generated by scripts/analyze_patch_failure_taxonomy.py\n"
        f"% Generated at {ts} (UTC)\n"
        f"% Requires \\usepackage{{booktabs}}\n\n"
    )
    stats = render_statistics_table(taxonomy_body)
    examples = render_examples_block(taxonomy_body["examples"])
    dominant = max(
        TAXONOMY_CLASSES,
        key=lambda c: taxonomy_body["classes"][c]["count"],
    )
    dom_share = taxonomy_body["classes"][dominant]["share_percent"]
    summary = (
        f"\\paragraph{{Summary.}}\n"
        f"Across {taxonomy_body['total_failures']} patch-application rejections, "
        f"\\texttt{{{dominant.replace('_', r'\_')}}} accounts for "
        f"{dom_share:.1f}\\% of failures. "
        f"\\texttt{{add\\_transition}} operations dominate the rejected patch mix "
        f"(see JSON aggregates).\n\n"
    )
    return header + summary + stats + "\n" + examples


def analyze_patch_failure_taxonomy(pilot_dir: Path) -> tuple[dict[str, Any], str]:
    records, patch_summary = analyze_patch_failures(pilot_dir)
    taxonomy_body = build_taxonomy(records, patch_summary["aggregates"])
    doc = {
        "schema_version": "1.0.0",
        "pilot_dir": str(pilot_dir.resolve()),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_patch_failure_summary": str(
            (pilot_dir / ANALYSIS_DIR / "patch_failure_summary.json").resolve()
        ),
        **taxonomy_body,
    }
    tex = render_taxonomy_tex(taxonomy_body)
    return doc, tex


def write_outputs(
    pilot_dir: Path,
    doc: dict[str, Any],
    tex: str,
    *,
    output_dir: Path | None = None,
) -> tuple[Path, Path]:
    out = (output_dir or pilot_dir / ANALYSIS_DIR).resolve()
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / JSON_NAME
    tex_path = out / TEX_NAME
    json_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    tex_path.write_text(tex, encoding="utf-8")
    return json_path, tex_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pilot-dir",
        required=True,
        type=Path,
        help="Diagnostic granularity pilot output root (read-only)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help=f"Write outputs here (default: <pilot-dir>/{ANALYSIS_DIR})",
    )
    args = parser.parse_args(argv)

    try:
        doc, tex = analyze_patch_failure_taxonomy(args.pilot_dir)
        json_path, tex_path = write_outputs(
            args.pilot_dir, doc, tex, output_dir=args.output_dir
        )
    except AnalysisError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(doc["classes"], indent=2))
    print(f"wrote {json_path}")
    print(f"wrote {tex_path}")
    print(f"classified {doc['total_failures']} failure(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
