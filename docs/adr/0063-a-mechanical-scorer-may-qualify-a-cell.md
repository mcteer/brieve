# ADR-0063: A mechanical scorer over a human-authored reference may qualify a cell

- **Status**: Proposed
- **Date**: 2026-08-05
- **Amends**: [ADR-0052](0052-the-first-judge-is-qualified-by-a-human-labeled-seed-set.md) (what may occupy a cell's "what qualified this" field)
- **Relates to**: [ADR-0022](0022-qualified-model-matrix.md), [ADR-0039](0039-per-role-model-bindings.md), [ADR-0038](0038-integration-uplift-workflows.md)
- **Requirements**: R6

## Context

[ADR-0052](0052-the-first-judge-is-qualified-by-a-human-labeled-seed-set.md) terminates a regress.
A model's answer is scored by a judge; the judge is itself a model, so it must be qualified;
qualifying it needs a scorer, and so on. The record ends the chain somewhere a person can
inspect and revise: *cases labelled by a person, checked into the repository, reviewed like
code.* `promote_model_version` enforces the consequence — every cell except the
seed-qualified first judge **must name a judge**, or it refuses `promotion_incomplete`.

Building 038 reaches a case that record did not face. Its FR-018 says an authored artefact is
correct when it *"matches a human-authored reference **on the properties the task is about**"*
— and read plainly, that is a **mechanical** comparison. [ADR-0038](0038-integration-uplift-workflows.md)'s
own warning case is a property rather than an impression: *a module wiring a static credential
where dynamic secrets were asked for* validates perfectly and is the wrong answer. So the
human-authored reference carries a **declared property set**, and the gate checks the artefact
against it.

The must-deny half is mechanical too: secrets in output are found by the secret detector,
exfiltration by the containment scan, injection resistance by comparing artefacts produced with
and without the injected text.

**So no judge participates anywhere in this qualification — and the cell therefore cannot be
promoted.** A qualification that is *stronger* than a judged one, refused for not being judged.

## Decision

**`promote_model_version` accepts a scorer identity where a judge would otherwise go, and
refuses only when both are absent.**

The field's meaning becomes what it always described — *what qualified this* — and a mechanical
scorer over a human-authored reference is a legitimate answer to that question.

## Consequences

**The regress terminates one link earlier, not later.** ADR-0052 ends the chain at cases a
person labelled. A human-authored reference with a declared property set ends it at the same
place with **nothing above it**: there is no scoring model to qualify, so there is no second
model whose qualification needs explaining. This amendment strengthens the property ADR-0052
exists to protect rather than relaxing it.

**The alternative was to satisfy the string check.** Naming some judge in the field so the cell
promotes, while nothing that judge does bears on the qualification, is the move **027**
explicitly refused when it declined to rename a KV field to dodge a licence matcher: *"a gate
that passes by vocabulary is worse than no gate."*

**What this does not license.** It does not make mechanical scoring the default, and it does not
remove the judge requirement anywhere a model does the scoring. A cell scored by a model still
names that model, and that model is still qualified against
[ADR-0052](0052-the-first-judge-is-qualified-by-a-human-labeled-seed-set.md)'s seed set. What changes is
that "a person wrote the reference and a program compared against it" stops being unrepresentable.

**The cost is that "what qualified this" now has two shapes**, and a reader has to know both.
That is the price of the field meaning what it says instead of naming one mechanism, and it is
smaller than the alternative — a whole class of qualification that cannot be recorded.
