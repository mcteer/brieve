# ADR-0043: Judge-screened precedent reuse, fail-closed on uncertainty

- **Status**: Accepted
- **Date**: 2026-07-21
- **Extends**: [ADR-0042](0042-duplicate-detection-and-precedent-cache.md)
- **Relates to**: [ADR-0022](0022-qualified-model-matrix.md), [ADR-0039](0039-per-role-model-bindings.md)

## Context

[ADR-0042](0042-duplicate-detection-and-precedent-cache.md) staleness-checks precedent
entries mechanically: has the commit moved, has the guidance been updated. That filter is
cheap and correct at the extremes — clearly-fresh and clearly-stale entries are decided
without judgment.

It leaves a middle. An entry whose commit has moved by a change that does not affect the
design; guidance updated in a section the design does not touch; a target that has drifted
in ways that may or may not matter. A purely mechanical filter must treat all of these as
misses, which discards most of the value, or as hits, which risks offering a design that no
longer fits.

Assessing "does this delta invalidate this design" is a judgment task, and the platform now
has a qualified role for judgment tasks
([ADR-0039](0039-per-role-model-bindings.md)).

The subtlety worth stating: the saving does not come from the judge being cheaper than a
model. It comes from the judge reading **the cached design and the delta** and making **no
tool calls of its own** — no repository analysis, no guidance retrieval, no estate queries.
Full resynthesis is expensive because of the tool calls, not the tokens.

## Decision

**Two-stage staleness checking.**

1. **The mechanical filter first** — cheap, decisive at the extremes.
2. **A judge-bound model on ambiguous survivors only** — reading the cached design and the
   delta, **making no tool calls of its own.**

**Fail closed on uncertainty.** A low-confidence or negative verdict defaults to **full
resynthesis**, never to offering a possibly-stale design. This guards the same self-review
blind spot named in [ADR-0039](0039-per-role-model-bindings.md): a model assessing whether
its own kind of output is still valid is exactly the position where over-confidence is most
likely.

**The judge decides only whether a precedent is offered.** It is never a substitute for the
requester's own approval gate — the governance rule from
[ADR-0042](0042-duplicate-detection-and-precedent-cache.md) is untouched.

**The judge is a pinned, qualified artifact** per [ADR-0039](0039-per-role-model-bindings.md).

**Labeled outcomes — valid, revised, discarded — are a third flywheel feed** alongside
traces and retrieval telemetry, toward the tuned-model roadmap
([ADR-0022](0022-qualified-model-matrix.md)). **Training use is opt-in per tenant,
default-off**, governed by the model matrix's no-training flags.

## Consequences

The ambiguous middle becomes usable, which is where most of a precedent cache's value
actually sits — the clearly-fresh cases are rare and the clearly-stale ones are worthless.
Constraining the judge to no tool calls is what preserves the saving; a judge permitted to
investigate would cost what resynthesis costs.

Failing closed to resynthesis means the worst outcome of a wrong judgment is wasted
computation, never a stale design presented as current. That asymmetry is the right one:
the platform's reputation survives redundant work and does not survive confidently offering
architecture that no longer fits.

The labeled outcomes are a quietly valuable byproduct — human-adjudicated judgments about
design validity are exactly the training signal a domain-tuned model needs, and they are
produced as a side effect of ordinary use. Making training opt-in and default-off is
non-negotiable given what the underlying designs contain.

The costs are calibration-shaped. Judge quality is now load-bearing for a user-visible
behavior, which is why judge-role qualification measures calibration and deny-rate
stability rather than only accuracy. A judge that drifts conservative quietly turns the
cache off; one that drifts permissive starts offering stale designs. Both are detectable
only by measurement, so the judge suite is not optional for this feature to remain
trustworthy.
