# Formal definitions: behavioural repairability

This document provides operational definitions for behavioural repairability and related concepts used in the empirical study. Notation is case-local unless stated otherwise. Definitions are written for reuse in peer-reviewed reporting; they deliberately avoid naming specific generators, models, or comparative leaderboards.

## Prerequisites

Let a **repair case** be a tuple \(c = (M_0, \mathcal{O}_{\mathrm{validation}}, \mathcal{O}_{\mathrm{feedback}}, \Sigma_c)\) where:

- \(M_0\) is the **initial candidate** finite state machine (FSM), structurally valid under \(\Sigma_c\) but not behaviourally correct;
- \(\mathcal{O}_{\mathrm{validation}}\) is the **validation** oracle suite used for BPR and published outcomes;
- \(\mathcal{O}_{\mathrm{feedback}} \subseteq \mathcal{O}_{\mathrm{validation}}\) (typically) is the suite used to construct repair-time feedback;
- \(\Sigma_c\) denotes structural constraints (schema and any study-specific rules).

For an FSM \(M\) and oracle \(o \in \mathcal{O}_c\), let \(\mathrm{pass}(o, M) \in \{\top, \bot\}\) denote the outcome of executing \(o\) against \(M\) under the fixed semantics of the case.

### Behavioural Pass Rate (BPR)

The **behavioural pass rate** of machine \(M\) on suite \(\mathcal{O}_c\) is

\[
\mathrm{BPR}(M, \mathcal{O}_c) = \frac{1}{|\mathcal{O}_c|} \sum_{j=1}^{|\mathcal{O}_c|} \mathbf{1}[\mathrm{pass}(o_j, M) = \top] \in [0, 1].
\]

**Behavioural correctness** (for case \(c\)) holds iff \(\mathrm{BPR}(M, \mathcal{O}_c) = 1\).

Eligible repair cases satisfy \(\mathrm{BPR}(M_0, \mathcal{O}_c) < 1\). Cases with \(\mathrm{BPR}(M_0, \mathcal{O}_c) = 0\) are fully failing; cases with \(0 < \mathrm{BPR}(M_0, \mathcal{O}_c) < 1\) are **partially failing** at entry.

---

## 1. Behavioural Repairability

**Behavioural repairability** is the capacity of a repair protocol to increase behavioural conformance of a structurally valid candidate FSM when guided by feedback derived from \(\mathcal{O}_c\).

For a fixed **repair condition** \(\kappa\) (protocol, feedback form, attempt budget \(B \in \mathbb{N}\)), define the **post-repair** machine \(M_{\kappa,c}\) as the candidate produced by the documented procedure after up to \(B\) repair attempts (or the baseline outcome defined for \(\kappa\)). The **repairability gain** for case \(c\) under \(\kappa\) is

\[
\Delta_{\kappa}(c) = \mathrm{BPR}(M_{\kappa,c}, \mathcal{O}_c) - \mathrm{BPR}(M_0, \mathcal{O}_c).
\]

A case is **repairable under \(\kappa\)** (operational success) iff

\[
\mathrm{BPR}(M_{\kappa,c}, \mathcal{O}_c) = 1
\quad\text{within budget } B.
\]

At population level, for a finite set of eligible cases \(\mathcal{C}\),

\[
\mathrm{RR}_\kappa = \frac{1}{|\mathcal{C}|} \sum_{c \in \mathcal{C}} \mathbf{1}[\mathrm{BPR}(M_{\kappa,c}, \mathcal{O}_c) = 1]
\]

is the **repair rate** (proportion achieving full behavioural correctness), and

\[
\overline{\Delta}_\kappa = \frac{1}{|\mathcal{C}|} \sum_{c \in \mathcal{C}} \Delta_{\kappa}(c)
\]

is the **mean BPR gain**. Behavioural repairability is assessed primarily through contrasts of \(\mathrm{RR}_\kappa\) and \(\overline{\Delta}_\kappa\) across repair conditions, not through ranking of alternative text generators.

**Example.** Suppose \(|\mathcal{O}_c| = 4\) and \(\mathrm{BPR}(M_0, \mathcal{O}_c) = 0.25\) (one check passes). After patch repair with trace feedback, \(M_{\kappa,c}\) passes all four checks; then \(\Delta_{\kappa}(c) = 0.75\) and the case is repairable under \(\kappa\).

---

## 2. Repair Attempt

A **repair attempt** is one atomic application of the repair procedure for condition \(\kappa\) on case \(c\):

1. Evaluate the current candidate \(M^{(t)}\) against \(\mathcal{O}_c\) (or a protocol-defined subset used for feedback);
2. Construct **feedback** from failing checks (form determined by \(\kappa\));
3. Produce a **candidate transition** \(M^{(t)} \rightarrow M^{(t+1)}\) (e.g. via a structured patch, or full replacement in a regeneration baseline).

The attempt index \(t \in \{0, \ldots, B-1\}\) counts completed transitions. Attempt \(0\) may be defined as evaluation-only in baseline conditions that do not mutate \(M_0\).

**Example.** In a patch condition with \(B = 5\), attempt \(t = 2\) applies one patch to \(M^{(2)}\) after oracle feedback from scoring \(M^{(2)}\); scoring the patched machine begins attempt \(t = 3\).

---

## 3. Successful Repair

**Successful repair** for \((c, \kappa)\) occurs when the final candidate \(M_{\kappa,c}\) produced within budget satisfies

\[
\mathrm{BPR}(M_{\kappa,c}, \mathcal{O}_c) = 1.
\]

This is equivalent to **repairable under \(\kappa\)** above. Success is **binary at the suite level**; partial improvement without full correctness is not classified as successful repair.

**Example.** After three attempts, \(\mathrm{BPR}(M^{(3)}, \mathcal{O}_c) = 1\); the run outcome is *success* even if earlier attempts failed some checks.

---

## 4. Partial Repair

**Partial repair** occurs when behavioural conformance improves but full correctness is not achieved within \(B\):

\[
\mathrm{BPR}(M_0, \mathcal{O}_c) < \mathrm{BPR}(M_{\kappa,c}, \mathcal{O}_c) < 1.
\]

Partial repair is material for characterizing **residual failure modes** and the limits of a feedback condition. It is distinct from successful repair.

**Example.** \(\mathrm{BPR}(M_0, \mathcal{O}_c) = 0.25 \rightarrow \mathrm{BPR}(M_{\kappa,c}, \mathcal{O}_c) = 0.75\): two additional checks pass, but one trace oracle still fails.

---

## 5. Failed Repair

**Failed repair** for \((c, \kappa)\) occurs when the attempt budget is exhausted without successful repair:

\[
\mathrm{BPR}(M_{\kappa,c}, \mathcal{O}_c) < 1
\quad\text{and no further attempts remain.}
\]

A common subcase is **no improvement**:

\[
\mathrm{BPR}(M_{\kappa,c}, \mathcal{O}_c) = \mathrm{BPR}(M_0, \mathcal{O}_c) < 1.
\]

Failed repair includes partial repair unless the study protocol reports them separately.

**Example.** After \(B = 5\) patch attempts, \(\mathrm{BPR}\) remains \(0.25\); outcome *budget exhausted*, failed repair.

---

## 6. Regression

**Regression** occurs at attempt \(t\) when a candidate transition decreases behavioural conformance:

\[
\mathrm{BPR}(M^{(t+1)}, \mathcal{O}_c) < \mathrm{BPR}(M^{(t)}, \mathcal{O}_c).
\]

A run may exhibit regression on one attempt yet later achieve successful repair. **Terminal regression** means the final candidate satisfies \(\mathrm{BPR}(M_{\kappa,c}, \mathcal{O}_c) < \mathrm{BPR}(M_0, \mathcal{O}_c)\).

**Example.** \(M^{(1)}\) passes two of four checks (\(\mathrm{BPR} = 0.5\)); an incorrect patch yields \(M^{(2)}\) with \(\mathrm{BPR} = 0.25\). Regression is recorded at \(t = 1\) even if \(M^{(3)}\) later recovers.

---

## 7. Behavioural Overfitting

**Behavioural overfitting** arises when a candidate appears to improve on **feedback exposed to the repair procedure** while not improving—or worsening—on the **authoritative** suite used for study conclusions.

Let \(\mathcal{O}_c^{\mathrm{fb}} \subseteq \mathcal{O}_c\) be checks used to construct feedback in condition \(\kappa\), and \(\mathcal{O}_c^{\mathrm{auth}} = \mathcal{O}_c\) the full suite (or a held-out \(\mathcal{O}_c^{\mathrm{hold}}\) if the protocol defines one). Overfitting is indicated when, at some attempt or at termination,

\[
\mathrm{BPR}(M^{(t)}, \mathcal{O}_c^{\mathrm{fb}}) > \mathrm{BPR}(M_0, \mathcal{O}_c^{\mathrm{fb}})
\quad\text{but}\quad
\mathrm{BPR}(M^{(t)}, \mathcal{O}_c^{\mathrm{auth}}) \leq \mathrm{BPR}(M_0, \mathcal{O}_c^{\mathrm{auth}}),
\]

or when gains on \(\mathcal{O}_c^{\mathrm{fb}}\) do not generalize to withheld checks. The study may treat \(\mathcal{O}_c^{\mathrm{fb}} = \mathcal{O}_c\) when feedback is derived from all failing checks; overfitting then concerns **spurious pass** on previously failing checks without stable conformance on re-execution or alternative witnesses (see Open Questions).

**Example.** Feedback cites a single failing trace; the patch fixes that trace’s events but breaks a different oracle check not surfaced in localized feedback—BPR on the full suite does not increase.

---

## 8. Non-Convergence

**Non-convergence** describes a repair run that does not exhibit stable progress toward \(\mathrm{BPR} = 1\) within \(B\) attempts. Operational criteria (any may be declared in the analysis plan):

- **Oscillation:** \(\mathrm{BPR}(M^{(t+k)}, \mathcal{O}_c) = \mathrm{BPR}(M^{(t)}, \mathcal{O}_c)\) for some \(k > 0\) with intervening strict increases and decreases;
- **Plateau:** \(\mathrm{BPR}(M^{(t)}, \mathcal{O}_c) = \mathrm{BPR}(M^{(t+1)}, \mathcal{O}_c) = \cdots\) for all remaining attempts with value strictly less than 1;
- **Unbounded churn:** patch size or structural edit count does not decrease while \(\mathrm{BPR}\) remains constant.

Non-convergence is a **process** descriptor; failed repair may result from non-convergence or from regression cycles.

**Example.** BPR alternates \(0.5 \rightarrow 0.75 \rightarrow 0.5 \rightarrow 0.75\) across four attempts; the run does not converge and terminates at \(0.75\).

---

## 9. Repair Cost

**Repair cost** quantifies resources consumed by a repair run for \((c, \kappa)\). Primary measures:

- **Attempt cost:** \(C_{\mathrm{att}} = t^\*\), the number of repair attempts executed (\(t^\* \leq B\));
- **Edit cost:** \(C_{\mathrm{edit}} = \sum_{t} |\mathrm{ops}(P^{(t)})|\), where \(\mathrm{ops}(P^{(t)})\) is the set of patch operations in attempt \(t\) (zero for no-repair baseline);
- **Oracle cost:** \(C_{\mathrm{orc}} = \sum_{t} |\mathcal{O}_c^{(t)}|\), the number of oracle checks evaluated across attempts (protocol-defined).

Composite cost may be reported as a weighted sum \(\alpha C_{\mathrm{att}} + \beta C_{\mathrm{edit}} + \gamma C_{\mathrm{orc}}\) with weights fixed **a priori**. Repair cost is interpreted conditional on \(\kappa\); lower cost at equal \(\Delta_{\kappa}\) indicates a more efficient condition.

**Example.** Successful repair in \(t^\* = 2\) attempts with patch sizes 3 and 1 yields \(C_{\mathrm{att}} = 2\), \(C_{\mathrm{edit}} = 4\).

---

## 10. Repair Iteration

A **repair iteration** is one complete cycle of the repair loop:

\[
\text{score } M^{(t)} \;\rightarrow\; \text{derive feedback } \;\rightarrow\; \text{propose transition } \;\rightarrow\; M^{(t+1)}.
\]

Thus one repair iteration corresponds to one **repair attempt** (Section 2) when scoring precedes each transition. Baselines may define degenerate iterations: e.g. **no iteration** (single score of \(M_0\)) or **single regeneration iteration** (one full replacement, then score).

Iteration index \(t\) orders the sequence \(\{M^{(t)}\}_{t=0}^{t^\*}\) and supports analysis of convergence and regression along the trajectory.

**Example.** A patch condition with \(B = 5\) allows at most five repair iterations; iteration \(t = 0\) starts from \(M^{(0)} = M_0\).

---

## Summary relations

| Outcome | Condition on \(\mathrm{BPR}\) |
|--------|-------------------------------|
| Successful repair | \(\mathrm{BPR}(M_{\kappa,c}, \mathcal{O}_c) = 1\) |
| Partial repair | \(\mathrm{BPR}(M_0) < \mathrm{BPR}(M_{\kappa,c}) < 1\) |
| Failed repair (no success) | \(\mathrm{BPR}(M_{\kappa,c}) < 1\) at budget end |
| Regression (step) | \(\mathrm{BPR}(M^{(t+1)}) < \mathrm{BPR}(M^{(t)})\) |

Repairability is summarized by **before/after** comparison of BPR on \(\mathcal{O}_c\), with \(\mathrm{RR}_\kappa\) and \(\overline{\Delta}_\kappa\) as population-level estimands.

---

## Open Questions

The following design decisions remain unresolved and will be fixed before analysis freeze:

1. **Authoritative vs feedback oracles.** Should \(\mathcal{O}_c^{\mathrm{fb}}\) be a strict subset of \(\mathcal{O}_c\), and should a held-out \(\mathcal{O}_c^{\mathrm{hold}}\) be mandatory to detect behavioural overfitting?

2. **BPR at case entry.** Are cases with \(0 < \mathrm{BPR}(M_0, \mathcal{O}_c) < 1\) in scope, or only \(\mathrm{BPR} = 0\)? How are baselines compared when entry BPR varies?

3. **Regeneration baselines.** For full replacement protocols, is \(M_{\kappa,c}\) the last generated machine only, or the best-scoring candidate across multiple regeneration draws within one attempt?

4. **Regression handling.** Should regression on an intermediate attempt be a secondary metric, or should runs with any regression be flagged separately from failed repair?

5. **Non-convergence detection.** Which operational criterion (oscillation, plateau, churn) will be reported as primary, and are thresholds (e.g. minimum plateau length) fixed a priori?

6. **Repair cost weighting.** Are \(\alpha, \beta, \gamma\) for composite cost pre-registered, or will only unweighted \(C_{\mathrm{att}}\) and \(C_{\mathrm{edit}}\) be reported?

7. **Structural drift.** Does a candidate that remains structurally valid but increases edit distance without BPR gain count toward non-convergence or toward a separate *structural churn* measure?

8. **Stochastic repair procedures.** If the repair procedure is stochastic, is repairability defined on a single run per case, on the best of \(n\) runs, or on expectation over runs—and how is that recorded in frozen run artifacts?

9. **Equivalence of iteration and attempt.** Do evaluation-only steps (re-score without mutation) count toward \(B\) and toward \(C_{\mathrm{att}}\)?

10. **Link to repair conditions.** How are \(\Delta_{\kappa}\) contrasts adjusted for baseline_no_repair (\(\Delta = 0\) by definition) and baseline_full_regeneration (replacement rather than patch trajectory)?

---

## See also

- [`study_design.md`](study_design.md) — research questions and repair conditions
- [`terminology.md`](terminology.md) — concise glossary
- [`experimental_setup.md`](experimental_setup.md) — protocol execution
