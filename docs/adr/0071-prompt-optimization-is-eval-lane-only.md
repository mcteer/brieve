# ADR-0071: Prompt-optimization libraries are eval-lane only

- **Status**: Accepted
- **Date**: 2026-08-19
- **Relates to**: [ADR-0001](0001-framework-agnostic-core.md), [ADR-0004](0004-adopt-skills-as-governed-supply-chain.md), [ADR-0030](0030-executed-artifacts-are-pinned-consulted-ones-are-fresh.md), [ADR-0058](0058-model-credential-brokering.md)
- **Requirements**: R12

## Context

Build phases need product-and-phase instructions that can be refined against measures
that lose. The named methods are GEPA per file, then a five-predictor DSPy program
jointly. Those libraries exist to *compile* prompts offline. They are not how a
person's Build is steered.

Putting `dspy` on the served path would teach the core or an adapter an optimizer.
Principle I forbids an agent framework in core; Principle VIII forbids executing
unpinned optimizer output mid-run; Principle IV forbids a new standing vendor key
for a compiler that should never run in an allocation. The tempting shortcut is to
treat prompt-opt as "just another model call" and import it beside `ModelChooser`.
That would make every authoring-tier job install a compiler it must never invoke,
and it would make a missing extra look like a reason to skip refinement and ship
the seed text as promoted.

The existing eval-lane broker (ADR-0058) already vends a model credential per task
for scoring. Refinement is the same class of work as corpus-sync: an operator
machine, not a served egress class.

## Decision

Prompt-optimization libraries (`dspy`, `dspy.GEPA`, and anything they pull in) are
eval-lane and operator-machine only. Served `src/core`, `src/adapters`, and
`src/surfaces` never import them. Model calls during refinement use the existing
eval broker (ADR-0058). This is not a new served egress class.

The optional extra is named `prompt-tune`. It depends on `harness[evals]` and pins
`dspy==3.3.0`. Install the PyPI package `dspy`, not the `dspy-ai` compatibility
alias. A GPL-family transitive refuses the extra rather than the license allowlist.

`promote_phase_agents` refuses `refinement_unavailable` when `dspy` cannot be
imported. Missing extra does not stamp seed files promoted. Production Builds
execute digest-pinned `AGENTS.md` bytes; they do not run GEPA or DSPy.

## Consequences

Served allocations stay free of an optimizer they must never run, and air-gapped
profiles execute the same pinned files. The cost is an extra that the named runner
must install before live promotion, and a unit gate that fails the change if served
packages import `dspy` or `gepa`. Seed pins in `pack.toml` are a different writer:
they are not evidence that GEPA or DSPy ran.
