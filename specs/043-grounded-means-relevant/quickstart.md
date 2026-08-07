# Quickstart: Grounded means relevant, not merely resolvable

How to see the gate working, cheapest first. Row IDs refer to
[contracts/conformance-relevance.md](contracts/conformance-relevance.md).

## Prerequisites

- Hermetic: nothing beyond the repo.
- Live legs: `ANTHROPIC_API_KEY` in `.env`; the relevance seed set present
  (`evals/relevance-seed/seed.toml`).
- Estate demo: `make dev-up`, the fixture judge cell and `relevance_cell` binding applied
  (ships with the trust-fabric defaults this feature adds).

## 1 — Hermetic proof (every PR)

```sh
make check                 # unit rows: seed loader floor (R13–R14), qualification scoring (R15), parser refusals
make conformance-hermetic  # R1–R12: the gate, its refusals, the record, the rig-off and caller rows
```

Expected: all green, with **zero edits** to existing answering cases (R9). The interesting
failures to try on purpose: delete the `relevance_cell` from a test binding (R6's refusal),
feed the parser a verdict with no leading token (R4's malformed leg).

## 2 — The defect, reproduced and then closed (live; named runner: Dan)

```sh
make evals-smoke
```

Before this feature: FAILS — `vault-must-decline-001` answers from Terraform and Boundary
retention docs, every citation resolving. After: the relevance leg shows the same case
**declining, "the corpus does not cover what was asked"**, and smoke exits 0 (L1, L2). The
response is printed either way — one call before reaching for anything bigger.

## 3 — Qualify the judge (live; the cell is bound by a person, not by the lane)

```sh
make evals-relevance-qualify   # target added by this feature
```

Expected: per-case verdicts at majority-of-three, two numbers printed separately — overall
(≥90% floor) and supported-but-irrelevant (must be all correct). A rigged always-affirm
candidate fails the second number while clearing the first (R15). On pass, add the live cell
and repoint `relevance_cell` in the trust fabric — a deliberate human act, with the dated
evidence in the record's comment, per the estate's promotion precedent.

## 4 — What did not change

- The corpus: untouched (ADR-0004).
- The failing case: unedited (FR-008) — it caught a real regression and keeps its teeth.
- Citation resolution: still required; the gate only narrows.
- A cross-product architecture question: still answered (R10) — ask one and check the
  citations span products.
