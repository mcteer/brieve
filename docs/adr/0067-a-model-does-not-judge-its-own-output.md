# ADR-0067: A model does not judge its own output

- **Status**: Proposed
- **Date**: 2026-08-07
- **Amends**: [ADR-0052](0052-the-first-judge-is-qualified-by-a-human-labeled-seed-set.md) (adds a constraint on *which* model may judge; the seed-rooted regress is unchanged)
- **Relates to**: [ADR-0022](0022-qualified-model-matrix.md), [ADR-0039](0039-per-role-model-bindings.md), [ADR-0063](0063-a-mechanical-scorer-may-qualify-a-cell.md)
- **Requirements**: R6

## Context

ADR-0052 terminates the judge regress at a human-labelled seed set and says every subsequent
judge is qualified by a judge that was itself qualified. It constrains **how a judge earns its
place**. It says nothing about **which model may judge which output**, and the gap is not
theoretical — measured in the dev estate today:

| Cell | Model | Judge |
| --- | --- | --- |
| `vault:anthropic/claude-opus@5:ask` | Opus 5 | **Opus 5** |
| `terraform:anthropic/claude-opus@5:ask` | Opus 5 | **Opus 5** |
| `vault:anthropic/claude-sonnet@5:ask` | Sonnet 5 | **Sonnet 5** |
| `terraform:anthropic/claude-sonnet@5:ask` | Sonnet 5 | **Sonnet 5** |

Every live cell this platform has ever promoted was qualified by the model it qualifies. The
records are honest about it — 031's comment says plainly that the same run qualified Opus as the
first judge — and nothing forbade it, so nothing stopped it.

**The failure mode is correlated blindness, not dishonesty.** A judge does not need to be
lenient to be useless; it needs only to share the generator's misconceptions. When the two are
the same model, every systematic error the generator makes is an error the judge is least
equipped to see, because seeing it would require disagreeing with its own reasoning about the
same material. The gate then measures fluency and returns a high score, and the score is
evidence of nothing.

**This platform has already paid for a near miss of exactly this shape.** 032 found that the
same scorer served subject and judge, so the judge inherited *"your response MUST begin with
'Denied:'"* — and a judge whose whole output is a verdict word qualified above 90% before that
instruction and at **55%** under it. That was protocol bleed rather than judgement bleed, and it
was visible only because a number moved. Judgement bleed moves no number: a self-judging cell
that agrees with itself looks exactly like a cell that is right.

043 makes the question urgent rather than academic. Its relevance gate puts a model verdict
**in the answering path**, deciding whether a person is shown an answer at all. A generator
judging its own relevance is asking the model that just produced three claims whether those
three claims were worth producing.

## Decision

**A model MUST NOT judge output it produced. The judging cell's model MUST differ from the
generating cell's model.**

This binds in two places:

1. **Qualification** — a cell's `judge` may not name that cell's own model. `promote_model_version`
   refuses, in the same place and the same way it already refuses a cell naming neither judge nor
   scorer.
2. **Runtime** — where a model judges another model's output in a live path (043's relevance
   gate is the first), the binding record's judging cell may not name the generating cell's
   model. The surface refuses rather than answering under a self-judgement.

**Scope: model identity, not vendor or family.** Sonnet judging Opus satisfies this; Opus
judging Opus does not. A stronger rule — different vendor, or a non-model scorer — is
available and is not taken, because the property being bought is *uncorrelated failure modes*
and different models already deliver most of that at a fraction of the cost. If evidence ever
shows same-vendor models failing together in a way that matters, this record is where that
argument belongs.

**Mechanical scorers are unaffected.** ADR-0063 permits a mechanical comparison against a
human-authored reference, and a scorer that is not a model cannot share a model's blind spots.
`scorer` remains a complete answer to "what qualified this".

## Consequences

**Four existing cells become non-conforming**, and that is the point of writing this down. They
are not withdrawn by this record — the evidence they carry is real, and it was gathered under a
rule that did not exist. What changes is that the next promotion cannot repeat it, and the
existing four are visible as debt rather than as precedent.

**Qualification gets more expensive.** Qualifying a model now requires a *second* qualified
model, and the first judge in any new chain still roots at the seed set. That is the cost of
the guarantee, and it is smaller than it looks: a judge qualified once serves many cells.

**A one-model deployment cannot qualify a live cell.** An air-gapped estate with a single
approved model can still run fixture-qualified cells and mechanical scorers, and cannot promote
a live cell qualified by a model verdict. That is a real constraint on a real deployment shape,
and it is the honest consequence of the rule rather than an oversight — Principle VIII already
says no air-gapped claim ships without a passing eval matrix on the target models.

**It does not make a judge correct.** Two different models can be wrong together, and this
record buys only that they are not wrong *identically by construction*. The seed set remains
the thing that measures whether a judge can tell the cases apart at all.
