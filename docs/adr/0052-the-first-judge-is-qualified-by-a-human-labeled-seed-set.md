# ADR-0052: The first judge is qualified by a human-labeled seed set

- **Status**: Accepted (2026-07-29, decided by `specs/013-capability-packs`)
- **Date**: 2026-07-29
- **Relates to**: [ADR-0022](0022-models-ship-as-a-qualified-model-matrix.md), [ADR-0039](0039-per-role-model-bindings.md), [ADR-0004](0004-skills-are-an-adopted-pinned-supply-chain.md)
- **Requirements**: R6 (eval-gated promotion), R4 (evidence over claims)

## Context

Eval-time judge models are pinned, eval-promoted artifacts — a judge that auto-tracked
would be an ungated input to every gate (FR-012). Qualifying a judge means a judge scored
the judge suite. So something qualified the *first* one, and that question does not answer
itself: the regress terminates somewhere, and wherever it terminates is the root of trust
for every gate above it.

013 made this binding rather than theoretical. Qualifying all five roles means qualifying
`judge`, and FR-012a requires the regress resolved **and recorded before any cell is
qualified** — explicitly forbidding the implicit answer, which is whichever judge happened
to run first becoming the root because nobody decided otherwise.

The spec bounded three options and left the choice to planning:

1. A **human-labeled seed set** that qualifies the first judge without a model in the loop.
2. An **externally attested** judge accepted as a root of trust and recorded as such.
3. A **declared floor**: one judge qualified by fiat, named in the record, everything else
   chaining from it.

## Decision

**The first judge is qualified by scoring it against `evals/seed/` — verdicts labelled by
a person, checked into the repository, reviewed like code.** Every subsequent judge is
qualified by a judge that was itself qualified, chaining back to the seed. A judge pointed
at itself refuses rather than closing the loop.

Of the three options, only this one terminates *inside* the repository:

- **External attestation** terminates too, but by importing trust from something this
  platform cannot inspect — precisely the move Principle IX ("a claim that cannot be
  reconciled to a record is a liability") is written against. An attestation is a claim;
  the seed set is a record.
- **A declared floor** is honest about being arbitrary, and that is its problem: it makes
  the root of the entire gate chain a thing nobody can argue with, which is how a
  governance control becomes a formality.

The seed set's authority is a person's judgement, visible in a diff, revisable through the
same review process as anything else. **The regress terminates at a human, which is where
it should terminate.** In this repository the labelling act is Dan's review: seed cases may
be drafted by anyone — including the harness — and become authoritative when the sole
maintainer reviews and merges them, which is the same act that makes anything else here
authoritative.

## The floor

**At least 20 cases spanning all four suites, including at least three the judge should
REJECT.** A seed set below the floor **fails the gate** rather than warning — a floor
nothing enforces is a suggestion, and this one is the root of the judge chain. A seed set
of two happy paths would qualify a judge that has never seen a wrong answer.

The floor is mechanical so "representative" is checkable at its edges. Clearing it is not
the same as being representative.

## The maintenance obligation

**A seed set that stops being representative silently weakens every gate above it.**

It must grow as the judge suite grows. The failure is quiet by construction: nothing
breaks, no row goes red, the judges keep returning verdicts — they are simply qualified
against a narrower slice of reality than the one they now judge. No automated check can
catch this, because "representative" is exactly the judgement being delegated. This ADR
records the obligation so it is owed rather than implied.

## Consequences

- `evals/seed/` is the one directory in this repository whose authority comes from a human
  having labelled it. It sits at the repository root, visible, not buried in a package.
- `core/evals/judge.py` implements the chain: first judge against the seed, every later
  judge by a qualified judge, self-qualification refused, below-floor seed sets refused.
- Every non-judge cell names the judge that scored it; only the seed-qualified first judge
  has nothing above it. A cell recorded without a judge is refused.
- Re-labelling the seed is a reviewed change with the same weight as a constitution edit,
  because it changes what "qualified" means platform-wide.

## Outcome

Recorded at implementation (T046 cross-references): the first judge cell is
`vault:anthropic/claude-opus@5:judge`, qualified against the seed set at its initial
20-case floor, in the fixture lane, with the live-lane qualification recorded per cell in
`specs/013-capability-packs/contracts/conformance-packs.md` by the named runner.
