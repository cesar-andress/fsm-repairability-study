# Study design

> **Placeholder.** Section headings and brief guidance are fixed; content will be completed as the study is finalized. Wording is intentionally conservative.

## Research Objective

To empirically characterize **behavioural repairability** of LLM-generated finite state machines: the extent to which structurally valid but behaviourally incorrect machines can be corrected when repair is guided by feedback from behavioural oracles, and how outcomes depend on stated repair conditions.

*Not in scope as primary objective:* ranking LLM models, expanding benchmark coverage, or re-demonstrating structural–behavioural divergence alone.

## Research Questions

<!-- Replace TODO items with finalized RQs before publication. -->

- **RQ1 (repair success):** Under each defined repair condition, what proportion of cases reaches behavioural correctness within a fixed attempt budget?
- **RQ2 (repair cost):** How many repair attempts (and what kinds of patch operations) are required before success or budget exhaustion?
- **RQ3 (feedback effect):** How do repair outcomes differ across **repair conditions** (baselines vs patch repair with binary, trace, or localized feedback), holding the experimental engine and attempt budget constant where possible?
- **RQ3b (sensitivity, secondary):** Are condition-level patterns stable across a small set of local Ollama models? *(Supplementary; not a model leaderboard.)*
- **RQ4 (residual failure):** When repair fails, what behavioural failure modes remain observable against the oracle suite?

*Additional RQs may be added; avoid RQs that only compare additional LLM models without a repairability framing.*

## Repairability Definition

**Behavioural correctness:** An FSM satisfies the behavioural specification for a case if it passes all tests in the associated oracle suite under the execution semantics defined in `docs/terminology.md`.

**Structural validity (precondition):** An FSM meets the structural schema and any stated structural constraints before it enters the repair study. Cases that fail structural checks are excluded from the repairability sample.

**Repair attempt:** One application of a repair procedure that consumes oracle feedback and produces a candidate FSM (typically via a structured patch). Attempts are counted up to a predefined maximum per case and condition.

**Repair success:** Behavioural correctness achieved within the attempt budget for that case and condition.

**Repairability (operational):** A case–condition pair is *repairable* in the study if repair success is observed under the documented protocol; population-level **repair rate** is the proportion of eligible cases that succeed per condition.

*Formal statistical definitions (e.g. estimands, CIs) to be added in the analysis plan.*

## Experimental Units

| Unit | Description |
|------|-------------|
| **Repair case** | One structurally valid, behaviourally incorrect FSM plus metadata and linked oracle suite(s). Schema: `schemas/repair_case.schema.json`. |
| **Repair condition** | **Primary independent variable:** repair protocol (baselines or patch repair with a feedback type). Schema: `schemas/repair_condition.schema.json`. |
| **Model run** | Same case and condition executed with a specific Ollama model (engine); used for sensitivity, not as the main IV. |
| **Repair run** | One conditioned sequence of repair attempts on one case. Schema: `schemas/repair_run.schema.json`. |

*Eligibility criteria for cases (task types, size bounds) to be specified.*

## Repair Conditions

**Primary independent variable:** repair condition (`condition_id`). Canonical definitions live in `environment/conditions.yaml`.

**Experimental engine (control / sensitivity):** local Ollama model on the study workstation (e.g. RTX 4090). Models implement the protocol; they are **not** the main contribution. See `docs/experimental_setup.md` and `environment/ollama_models.yaml`.

| `condition_id` | Role | LLM? | Prompt | Summary |
|----------------|------|------|--------|---------|
| `baseline_no_repair` | Baseline | No | — | Score initial FSM only; establishes behavioural incorrectness at entry |
| `baseline_full_regeneration` | Baseline | Yes | `baseline_full_regeneration.md` | Regenerate full FSM from task spec; no patch loop or oracle feedback between attempts |
| `patch_binary_feedback` | Patch repair | Yes | `repair_binary_feedback.md` | Patch repair with pass/fail oracle feedback |
| `patch_trace_feedback` | Patch repair | Yes | `repair_trace_feedback.md` | Patch repair with failing execution trace |
| `patch_localized_feedback` | Patch repair | Yes | `repair_localized_feedback.md` | Patch repair with localized diagnostic feedback |

**Analysis priority:** contrasts across `condition_id` with one primary Ollama model. **Sensitivity:** repeat selected contrasts across `sensitivity_models` in `ollama_models.yaml`; report as robustness checks, not a leaderboard.

*Other controls (temperature, attempt budget, patch grammar) are frozen in environment config and run metadata.*

## Metrics

Primary and secondary metrics (to be tied to paper tables):

- **Repair rate** — proportion of cases with repair success per condition
- **Attempts to success** — count among successful cases
- **Attempt budget exhaustion rate** — failures at max attempts
- **Patch size / operation count** — structural edit cost per attempt
- **Oracle failure diversity** — categories of remaining failures after exhaustion

*No leaderboard metric across open-ended model sets.*

## Validity Threats

| Threat | Mitigation (planned) |
|--------|----------------------|
| Construct validity | Oracle suites aligned to stated behavioural specs; independent review of oracles |
| Internal validity | Frozen prompts and schemas; deterministic scoring scripts |
| External validity | Explicit case sampling frame; no claim to all possible FSM tasks |
| Conclusion validity | Predefined RQs and attempt budgets; appropriate aggregation per unit |
| Novelty / framing | Focus on repairability, not replication of structural-only benchmarks |

*Threat-specific responses will be expanded in the manuscript.*

## Artifact Scope

This repository includes only materials needed to:

1. Understand the repairability operationalization
2. Validate FSM and patch structure
3. Re-score reported FSMs against frozen oracles
4. Reproduce aggregated results tied to published claims

It includes optional **local Ollama** scripts for re-execution on a compatible workstation, but audit replication uses **frozen runs** and does not require the original GPU.

It excludes generation campaigns, private notes, and exploratory model-comparison benchmarks.

See also: [`repository_scope.md`](repository_scope.md), [`../DATA_STATEMENT.md`](../DATA_STATEMENT.md).
