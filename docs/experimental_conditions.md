# Experimental conditions

This document defines the **repair conditions** for the behavioural repairability study. Each condition is a controlled repair protocol applied to the same eligible repair cases. Conditions are the **primary independent variable**; contrasts between conditions support inference about how **oracle feedback shape** affects repair outcomes, not about which text generator performs best.

Canonical identifiers and attempt budgets are listed in [`environment/conditions.yaml`](../environment/conditions.yaml). Frozen prompts live under [`prompts/`](../prompts/). Run records use [`repair_condition`](../schemas/repair_run.schema.json) in [`docs/repair_run_format.md`](repair_run_format.md).

## Shared experimental context

All conditions share the following **controls** unless noted otherwise:

| Control | Specification |
|---------|----------------|
| **Unit of analysis** | One repair case: structurally valid, behaviourally incorrect candidate FSM + frozen requirement + oracle suite |
| **Entry gate** | \(\mathrm{BPR}(M_0) < 1\) on the authoritative oracle suite |
| **Edit mechanism (patch conditions)** | Constrained patch language only ([`patch_language.md`](patch_language.md)); no free-form graph replacement within an iteration |
| **Evaluation** | Behavioural Pass Rate (BPR) recomputed after each iteration on the same authoritative suite |
| **Engine** | One primary experimental engine per main analysis; additional engines used only for sensitivity (see [`experimental_setup.md`](experimental_setup.md)) |
| **Confounds held constant** | Case set, oracle suites, patch schema, decoding parameters, iteration caps per condition family |

**Baselines (A–B)** establish floors for repairability claims. **Patch-repair conditions (C–E)** manipulate only the **information content of oracle-derived feedback** presented between iterations, holding the patch grammar and scoring procedure fixed.

---

## Condition A — No repair baseline

**Identifier:** `baseline_no_repair`

### Scientific motivation

Establishes the **entry behavioural deficit** for each case without any repair intervention. Separates “how wrong is the initial candidate?” from “can feedback-guided repair improve it?”. Required to interpret \(\mathrm{BPR}(M_0)\), residual failure prevalence, and gains in Conditions C–E relative to a true no-treatment counterfactual.

### Information provided to the model

None. No generative repair step is invoked.

### Information withheld

All repair-time information: current candidate FSM edits, oracle feedback, patch grammar, and task prompts used in other conditions.

### Expected advantages

- **Validity:** Pure observational baseline; no risk of repair-induced side effects.
- **Cost:** Minimal execution cost (oracle scoring only).
- **Interpretation:** Anchors \(\mathrm{input\_bpr} = \mathrm{output\_bpr}\) for downstream \(\Delta\)BPR comparisons.

### Expected risks

- Does not, by itself, test any repair hypothesis; must be paired with active conditions.
- Cannot reveal whether failures are due to structural omissions vs. behavioural mis-wiring unless oracles and structural diagnostics are analysed separately on the frozen case.

---

## Condition B — Full FSM regeneration

**Identifier:** `baseline_full_regeneration`

### Scientific motivation

Tests whether **discarding the candidate and regenerating a complete FSM** from the requirement alone achieves behavioural correctness without incremental oracle guidance. Contrasts **global replacement** (B) with **local, auditable patches** (C–E). Addresses whether repairability requires feedback at all, or only a fresh synthesis pass.

### Information provided to the model

- Frozen **requirement text** (and any documented structural constraints) for the case.
- Instructions to output a **complete new FSM** conforming to the project schema.
- No oracle pass/fail or trace data between attempts (single-shot or fixed small number of regenerations per protocol).

### Information withheld

- The initial candidate FSM (or its explicit deltas), by design, so the procedure cannot perform targeted patch repair.
- Per-check oracle feedback, failing traces, and localized diagnostics used in C–E.
- Patch operation vocabulary for iterative edit loops.

### Expected advantages

- **Simplicity:** Avoids patch application and iteration bookkeeping.
- **Exploration:** May escape local errors that patch repair cannot undo without many iterations.
- **Baseline for “re-synthesize” strategies** common in practice.

### Expected risks

- **Loss of structural proximity:** May discard partially correct structure present in \(M_0\).
- **Variance:** Full regeneration may be unstable across stochastic engines (handled via sensitivity analysis, not as primary IV).
- **Confound with feedback:** Any success is attributable to regeneration plus requirement, not to oracle-guided repair; must not be equated with Conditions C–E.

---

## Condition C — Binary oracle feedback

**Identifier:** `patch_binary_feedback`

### Scientific motivation

Minimal **feedback channel**: the repair procedure learns only whether the candidate fails behavioural checks, not why. Tests repairability under **low-information guidance** and establishes a lower bound on feedback usefulness before adding diagnostic detail (D, E).

### Information provided to the model

- Current candidate FSM (structured JSON).
- Frozen requirement reference.
- **Binary oracle outcome:** overall pass/fail on the authoritative suite (or on the protocol-defined feedback subset).
- Identifiers of **failed checks** without execution traces or localized hints.
- Patch grammar instructions and attempt index / budget.

### Information withheld

- Expected vs. observed execution traces.
- Localized state/transition suspects.
- Gold FSM or full oracle specifications beyond what is needed to list failed check ids.
- Free-form natural-language critique not derived from frozen oracle output.

### Expected advantages

- **Parsimony:** Smallest feedback payload; easy to freeze and audit.
- **Realism:** Matches settings where only test pass/fail is available in CI.
- **Clear contrast:** Any improvement over C isolates value of richer feedback (D, E).

### Expected risks

- **Ambiguity:** Many structurally distinct patches may satisfy “fail” without progressing toward correctness.
- **Higher iteration cost** or **plateau** at partial BPR.
- **Behavioural overfitting risk** lower than D/E for trace-specific fixes, but **no improvement** risk remains if failed-check ids are insufficient.

---

## Condition D — Failing trace feedback

**Identifier:** `patch_trace_feedback`

### Scientific motivation

Supplies **observable evidence** of failure: input sequences and expected vs. observed state traces for at least one failing check. Tests whether repairability improves when the model receives **dynamic behaviour** of the defect, not only a pass/fail label. Central to claims that **execution-aligned feedback** matters for FSM repair.

### Information provided to the model

- Everything in Condition C, plus for failing checks (typically one per iteration):
  - **Input event sequence** exercised by the oracle.
  - **Expected state trace** (or equivalent witness).
  - **Observed state trace** produced by the candidate.
- Patch grammar and iteration metadata.

### Information withheld

- Localized ranking of “most likely” states/transitions (reserved for E).
- Full gold FSM graph.
- Passing checks’ traces unless protocol explicitly includes them as context (default: **withhold** to limit leakage).
- Unrelated failing checks beyond protocol cap per iteration (if any cap is imposed for fairness).

### Expected advantages

- **Diagnostic power:** Reduces ambiguity vs. binary feedback; targets wrong transitions along observable paths.
- **Alignment with oracles:** Trace oracles are common in behavioural testing of state machines.
- **Expected higher** \(\Delta\)BPR and success rate than C, if feedback content drives repairability.

### Expected risks

- **Narrow fixes:** Risk of correcting one witnessed trace while breaking other checks ([`repairability_definition.md`](repairability_definition.md) — behavioural overfitting).
- **Prompt complexity:** Longer, structured feedback; serialization must remain frozen for replication.
- **Incomplete coverage:** If multiple failures exist, single-trace focus per iteration may slow convergence.

---

## Condition E — Localized diagnostic feedback

**Identifier:** `patch_localized_feedback`

### Scientific motivation

Provides **structural hints** without full traces: suspected states, transitions, or regions implicated by oracle analysis. Tests whether **localisation** accelerates repair when binary failure is known but exact execution witness is abbreviated or expensive. Contrasts **abstraction level** with D (dynamic trace vs. static localisation).

### Information provided to the model

- Everything in Condition C, plus:
  - **Suspected states** and/or **suspected transitions** (or equivalent localisation fields).
  - Short **failure summary** derived from oracle rules (frozen template).
- Current candidate FSM, requirement reference, patch grammar, iteration metadata.

### Information withheld

- Full expected vs. observed traces (unless protocol defines a hybrid; default E **withholds** traces to isolate localisation).
- Gold FSM.
- Complete enumeration of all failing checks beyond protocol limits per iteration.

### Expected advantages

- **Search reduction:** May shrink patch search space compared to C.
- **Scalability:** Shorter feedback than full traces for large machines.
- **Engineering relevance:** Mirrors IDE/static-analyser style hints.

### Expected risks

- **Incorrect localisation:** Wrong suspects may mislead repair worse than binary feedback.
- **Overfitting to hints:** Patches may chase suggested locations while ignoring global behaviour.
- **Construct validity:** Localisation quality depends on oracle implementation; must be frozen and versioned.

---

## Cross-condition comparison

| Aspect | A | B | C | D | E |
|--------|---|---|---|---|---|
| Generative repair | No | Yes (full FSM) | Yes (patch) | Yes (patch) | Yes (patch) |
| Uses initial candidate | Yes (score only) | No (replace) | Yes | Yes | Yes |
| Oracle feedback | No | No | Binary | Trace | Localized |
| Patch iterations | 0 | 0–1 (protocol) | ≤ budget | ≤ budget | ≤ budget |
| Primary contrast role | Entry floor | Regeneration floor | Minimal feedback | Dynamic evidence | Structural hints |

**Primary hypotheses (design-level, not results):**

1. \(\mathrm{RR}_\mathrm{D}, \mathrm{RR}_\mathrm{E} \geq \mathrm{RR}_\mathrm{C}\) (richer feedback improves repair rate vs. binary).
2. \(\mathrm{RR}_\mathrm{C}, \mathrm{RR}_\mathrm{D}, \mathrm{RR}_\mathrm{E}\) vs. \(\mathrm{RR}_\mathrm{B}\) separates **incremental repair** from **full regeneration**.
3. Condition A fixes \(\mathrm{input\_bpr}\); improvements in C–E are **causally attributed** to feedback-shaped repair, not to re-scoring alone.

## Fairness and reporting rules

1. **Same case set** for all conditions reported in main tables.
2. **Pre-registered attempt budgets** per condition family (`environment/conditions.yaml`).
3. **Do not compare engines** in the main condition-effect analysis; engine variation is sensitivity-only.
4. Report **convergence_status**, **regression_detected**, **patch_count**, and **patch_size** alongside BPR ([`repair_run_format.md`](repair_run_format.md)).
5. Freeze prompts, oracles, and example patches before Zenodo deposit.

## See also

- [`study_design.md`](study_design.md) — research questions and metrics
- [`repairability_definition.md`](repairability_definition.md) — BPR, convergence, regression
- [`experimental_setup.md`](experimental_setup.md) — execution and replication modes
- [`repair_case_format.md`](repair_case_format.md) — experimental units
