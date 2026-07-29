# Contract: The Qualified Model Matrix

**Feature**: `specs/013-capability-packs` | **Date**: 2026-07-29 | **Status**: Planned

Principle VIII's central rule, made mechanical: **a definition may only use a model that
evaluation has demonstrated, for the role it is being used in.**

---

## A cell

`(pack × model × role)`, where role is the closed vocabulary `ask | plan | write | judge |
summarize`. Green only by demonstrated evaluation. Lives in the control-plane trust fabric
beside the ceilings 010 put there — operator-authored, read-only to runs.

Each cell records **which scorer qualified it** (`fixture` or `live`). A cell qualified by
the fixture scorer is qualified against a recording, and the record says so per cell rather
than per matrix, because the two lanes will not stay in step.

## Validation, twice

**At definition registration**: a binding map entry that does not resolve to a qualified
cell refuses `unqualified_cell`, **naming the cell**, before anything executes.

**At run start**: the same check, again. Not redundant — a cell can be *withdrawn* after a
definition pinned it (a model deprecated, a suite regressed, a bad result acted on), and
validating only at registration would let a withdrawn cell keep running because nothing
re-asked. Refuses `cell_withdrawn`. This is the reasoning that makes 010 resolve a ceiling
per run rather than caching it.

## Fallback

When a pinned cell is unavailable at run time:

1. Search the matrix for another qualified cell for the same `(pack, role)`.
2. If one exists: use it and **record `MATRIX_FALLBACK`** with pinned and used models.
3. If none exists: **stop the run, reason recorded** (`no_qualified_fallback`).

Never to an unqualified model. Never silently. The recording is the load-bearing half — a
fallback nobody can see is a definition that does not describe what ran.

## No auto-tracking, anywhere

A model version bump is a new cell requiring qualification. There is no "latest", no alias
that resolves to a moving target, and no configuration that would make one. **Asserted as
an absence**, the way this repository asserts its other absences.

## The judge, and where the chain ends

`judge` is a role like any other, so a judge model occupies a cell and must be qualified.
That is a regress: qualifying a judge requires a judge.

**It terminates at `evals/seed/`** — human-labelled verdicts, checked in, reviewed like
code (ADR-0052). The first judge is qualified by scoring it against the seed; every later
judge by a judge already qualified. A cell's `judge` field names which one, and is absent
only for the seed-qualified first.

The alternatives were bounded by the spec and rejected in research D1: **external
attestation** terminates by importing trust from something this platform cannot inspect,
which is what Principle IX is written against; a **declared floor** is honest about being
arbitrary, and that is its problem — it makes the root of the whole gate chain something
nobody can argue with.

## A model verdict is not an approval

A `judge` verdict may gate a step. It **never** satisfies an approval requirement policy
assigns to a human (FR-015, Principle IX), and the trail distinguishes them: `MODEL_GATE`
is its own event, added knowing there is no approval event yet to be confused with — so the
distinction is established rather than repaired.
