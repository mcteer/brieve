# Quickstart: The intake gauntlet

**Feature**: 037 | **Date**: 2026-08-05

How to prove each stage works — and, for the two rows that matter most, how to prove they can
fail. Every scenario has a conformance row behind it; see [contracts/](contracts/).

## Prerequisites

- `uv sync --extra adapters --extra surfaces --extra portal` — no new extra. The poller uses
  `urllib`, the analyzer binds an existing matrix cell.
- The range posture scenarios (E, F) need the enclave: `make dev-up` then the range job.
  Everything else runs hermetically.

## Scenario A — Upstream moves, and nothing is adopted

```sh
uv run --extra adapters --extra surfaces pytest tests/conformance/intake -q -k detection
```

Expected: I1–I5 pass. A moved pin produces a proposal carrying the delta and both
provenances; an unmoved pin records that it was checked; an unreachable upstream reports
failure rather than stability. **Confirm the skill on disk is byte-identical throughout** —
detection adopts nothing.

## Scenario B — The analyzer is talked to, and does not listen

```sh
uv run --extra adapters --extra surfaces pytest tests/conformance/intake -q -k containment
```

Expected: A1–A5 pass. The interesting one to read rather than just run is **A2**: it inspects
what the analysis ceiling *contains* rather than how the analyzer behaved, so it holds for
redirections nobody thought to write.

## Scenario C — The gate has a gate

```sh
uv run --extra adapters --extra surfaces pytest tests/conformance/intake -q -k qualification
```

Expected: Q1–Q5 pass, with the must-flag rate and false-positive budget printed. **Q4 is the
row to watch**: it weakens the analyzer deliberately and requires qualification to fail. If
Q4 ever passes trivially, Q1–Q3 have stopped meaning anything.

## Scenario D — Detonation, and the separation

```sh
uv run --extra adapters --extra surfaces pytest tests/conformance/intake -q -k detonation
```

Expected: D1–D5, D8–D10 pass. **D5 is the load-bearing one** — a marker seeded into candidate
output must appear nowhere in the observer's context or report. Every other row here can pass
while D5 fails, and that combination is the vulnerability the feature exists to prevent.

## Scenario E — The range has no authority (enclave)

```sh
make dev-up
nomad job run infra/jobs/detonation-range.nomad.hcl
uv run --extra adapters --extra surfaces pytest tests/conformance/intake -q -m enclave
```

Expected: D6–D7 pass. The range reaches no real authority source and no real estate, and is
**not** the test-only fake. If a future change swaps the fake in for convenience, D6 fails
here rather than being noticed in review.

## Scenario F — The honest bypass

```sh
uv run --extra adapters --extra surfaces pytest tests/conformance/intake -q -k human_gate
```

Expected: H1–H5 pass. **H4** adopts a skill with the pipeline unavailable and asserts
`INTAKE_BYPASSED` names who, when, which skill and why — and that the record is no quieter
than a gauntlet promotion. A permitted bypass that leaves a faint trace becomes the normal
route.

## Scenario G — Read the package as a reviewer would

After Scenario A produces a proposal, open the evidence package and confirm it answers three
questions without you opening the upstream diff: *what changed*, *what the analyzer found*,
*how it behaved against the corpus versus the version in production*. Then confirm it answers
a fourth: **what none of this establishes** (H5). A package that reads clean without stating
its limits is the reassurance failure this feature is most able to cause.

## What done looks like

- Both contracts green, including Q4 and D5 — the two rows that prove the others can lose.
- `make check` and `make conformance-hermetic` green; `OWED` still empty (the analyzer suite
  lands with the analyzer, per research R9).
- ADR-0053 Accepted, carrying its three clarification amendments.
- The Principle V review recorded on the PR.
- The range's named trigger present in the ADR (Principle VI).
