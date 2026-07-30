# The seed set

**This is the root of the judge chain** (ADR-0052).

Every eval-time judge in this platform is a pinned, eval-promoted artifact — a judge that
auto-tracked would be an ungated input to every gate. Which raises the question the
constitution does not answer: *what qualified the first one?*

It is qualified here. The files in this directory are **verdicts a person labelled**. The
first judge is qualified by scoring against them; every judge after that is qualified by a
judge that was itself qualified, chaining back to this directory. A judge pointed at itself
is refused rather than closing the loop.

## Why a human-labeled seed set and not something else

Three options were bounded, and the other two both terminate:

- **External attestation** terminates by importing trust from something this platform
  cannot inspect — precisely the move Principle IX is written against ("a claim that cannot
  be reconciled to a record is a liability").
- **A declared floor** is honest about being arbitrary, and that is its problem: it makes
  the root of the entire gate chain a thing nobody can argue with, which is how a
  governance control becomes a formality.

A seed set terminates *inside* this repository. The authority is a person's judgement,
visible in a diff, reviewable, and revisable through the same process as anything else.
**The regress terminates at a human, which is where it should terminate.**

## These labels are reviewed like code

They are not fixtures and not test data. They are the thing every gate above them inherits
its authority from, so a change here is a change to what "qualified" means platform-wide.
Review a diff to this directory the way you would review a change to the constitution.

## The obligation, stated because it is easy to let slide

**A seed set that stops being representative silently weakens every gate above it.**

It must grow as the suites grow. The failure is quiet by construction: nothing breaks, no
row goes red, and the judges keep returning verdicts — they are simply qualified against a
narrower slice of reality than the one they are now judging. There is no automated check
that can catch this, because "representative" is exactly the judgement being delegated.

The floor is mechanical and enforced: **at least 20 cases spanning all four suites,
including at least three the judge should REJECT.** A set below the floor **fails the
gate** rather than warning — a floor nothing enforces is a suggestion, and a seed set of
two happy paths would qualify a judge that has never seen a wrong answer.

The floor is a floor. Clearing it is not the same as being representative.
