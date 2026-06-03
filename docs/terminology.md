# Terminology

Conservative definitions used across schemas, scripts, and documentation. Refinements will be versioned with the artifact.

## Finite state machine (FSM)

A labelled transition system represented as JSON conforming to `schemas/fsm.schema.json`: finite set of states, alphabet of events (or inputs), transition relation, and designated initial state. Outputs (if Moore/Mealy-style) are represented as defined in the schema.

## Structural validity

Conformance to `fsm.schema.json` plus any study-specific structural constraints (e.g. reachability, totality on declared alphabet) documented per repair case. Structural validity is a **gate** for inclusion, not the study outcome.

## Behavioural correctness

An FSM is behaviourally correct relative to a case if it passes every check in the linked **oracle suite** under the execution semantics below.

## Behavioural oracle

A machine-checkable specification of expected behaviour: traces, input–output sequences, forbidden behaviours, or equivalent tests. Stored under `datasets/oracle_suites/`. Oracles emit pass/fail and optional diagnostic detail for repair feedback.

## Behavioural repairability

The property studied empirically: whether and how often behaviourally incorrect but structurally valid FSMs can be brought to behavioural correctness via a bounded repair process using oracle-derived feedback.

## Patch

A structured edit to an FSM document conforming to `schemas/patch.schema.json`. Patches are applied deterministically by `scripts/apply_patch.py` (semantics to be fully specified).

## Repair case

A frozen study unit (fundamental observation): identity, inputs, baseline metrics, separated feedback/validation oracles, repair history, and final outcome. See `docs/experimental_unit.md` and `schemas/repair_case.schema.json`.

## Repair run

A record of repair attempts for one case under one condition. See `schemas/repair_run.schema.json`.

## Repair condition (primary independent variable)

A named repair protocol identified by `condition_id` (see `environment/conditions.yaml`): baselines (`baseline_no_repair`, `baseline_full_regeneration`) or patch-repair with a specific feedback type (`patch_binary_feedback`, `patch_trace_feedback`, `patch_localized_feedback`). Hypothesis tests and main tables compare **conditions**, not models.

## Experimental engine (LLM model)

A local Ollama model used to execute LLM-invoking conditions. Configured in `environment/ollama_models.yaml`. One **primary** model supports the main analysis; **sensitivity** models repeat subsets of conditions for robustness. The engine is not framed as the study's main independent variable.

## Feedback format

Within patch-repair conditions, the type and format of oracle information exposed to the repair procedure (binary, trace, localized). This is part of the repair condition definition, not a separate model comparison.

## Attempt budget

Maximum number of repair attempts per case per condition after which the case is classified as repair-failed for that condition.
