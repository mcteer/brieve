# Quickstart: Customer-supplied context

How to see it working, cheapest first. Row IDs refer to
[contracts/conformance-endorsed-context.md](contracts/conformance-endorsed-context.md).

## Prerequisites

- Hermetic: nothing beyond the repo.
- Live legs: `make dev-up`; the trust-fabric apply that ships the `endorsed-sources` record in
  the console's writable set; a person mapped to `admin`; a reachable Git repository holding a
  few Markdown documents to play the customer's standards.

## 1 — Hermetic proof (every PR)

```sh
make check                 # record parser, version pinning, provenance fields, the four-place scan
make conformance-hermetic  # E1–E24: the gate, the pin, detect/review/adopt, run isolation
make a11y                  # EL3 — the endorsed-sources page is walked
```

Failures worth causing on purpose: rig out the endorsement check and watch E4 fail — content
becoming citable without an endorsement is the one thing this feature must make impossible;
adopt mid-run in E15 and watch the run hold its version.

## 2 — Endorse and cite (live; named runner: Dan)

EL1: from `/settings`, endorse the test repository. Expected: the change rides the
three-outcome path (applied-and-disclosed-as-ungated in dev); the sync records what it took
and its identity; a question only that content answers is **answered**, with citations under
`/endorsed/<source>/…` that resolve, `provenance: customer-endorsed` on each, and the age of
the material disclosed.

Then ask something the validated designs answer: the citations carry
`provenance: validated-design`, and a mixed answer names both.

## 3 — Drift, review, adopt (live)

EL2: push a change to the test repository. Expected, in order:

1. The health checker flags drift; the console shows the source has changed. **Nothing about
   answers changes** — the flag is a notification, not an adoption.
2. Review shows which documents were added, removed, altered — against what is currently
   upstream.
3. Adopt. The next question answers from the new content; the adoption is recorded with who
   and when.
4. A run started before the adoption finishes on the version it started with; its record names
   that version, and only that version.

## 4 — What an administrator cannot do, and what a run cannot do

- A non-admin cannot endorse (E3); an administrator cannot make content citable without the
  fabric deciding (E1).
- A dispatched run cannot endorse, adopt, or withdraw — in any wording, including planted in a
  subject (E24).
- Nobody can make the answering path fetch: zero outbound requests during answering, asserted
  by instrumentation (E23).

## 5 — What did not change

- The pinned corpus: loads, verifies, declines exactly as before; its rows pass unedited,
  asserted as a diff (E22).
- 043's relevance gate: judges claims from customer material exactly as any other — where a
  claim came from is not whether it answers the question.
- 044's console mechanism: one more record in the closed set, same three outcomes, same
  provenance stamping, same CAS.
