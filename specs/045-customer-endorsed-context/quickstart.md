# Quickstart: Customer-supplied context

How to see it working, cheapest first. Row IDs refer to
[contracts/conformance-endorsed-context.md](contracts/conformance-endorsed-context.md).

## Prerequisites

- Hermetic: nothing beyond the repo.
- Enclave legs: `make dev-up`, then a trust-fabric apply — which **clobbers the model
  credential**, so re-seed `harness-authority/data/model-credentials/anthropic` afterwards. The
  apply also needs `TF_VAR_vault_license` (the variable is `VAULT_ENT_LICENSE` in `.env`, and
  passing an empty value recreates the trust store into a crash loop).
- Live console legs: additionally a person mapped to `admin` and an interactive sign-in — the
  API admits human subjects only, so a machine credential is refused `subject_kind_mismatch`.
- A Git repository holding a few Markdown documents to play the customer's standards. A local
  bare repository works and exercises the same code path: `git init`, commit some `.md`, then
  `git clone --bare`.

## 1 — Hermetic proof (every PR)

```sh
make check                 # record parser, version pinning, provenance fields, the four-place scan
make conformance-hermetic  # E1–E25: the gate, the pin, detect/review/adopt, run isolation
make a11y                  # EL3 — the administrator's console and the review page are walked
```

The enclave legs are split across two lanes by what each environment can do, and `make
conformance` runs both:

```sh
make conformance           # the allocation lane (the store, under a workload identity)
                           # AND the host lane (the transport, where `git` exists)
```

Failures worth causing on purpose: rig out the endorsement check and watch E4 fail — content
becoming citable without an endorsement is the one thing this feature must make impossible;
adopt mid-run in E15 and watch the run hold its version.

## 2 — Endorse and cite (live; named runner: Dan)

The **mechanism** below can be driven without a browser and was — see the contract's "What
actually ran". What needs the named runner is the console: reaching `/settings` requires an
interactive sign-in against the estate's real identity provider.

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
  asserted as a diff (E22). With **nothing endorsed the pinned corpus is passed unchanged** —
  an estate that has endorsed nothing runs the code it ran before this feature, rather than a
  new path that happens to be empty.
- 043's relevance gate: judges claims from customer material exactly as any other — where a
  claim came from is not whether it answers the question.
- 044's console mechanism: one more record in the closed set, same three outcomes, same
  provenance stamping, same CAS.
