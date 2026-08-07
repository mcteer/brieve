# Quickstart: Grounded means relevant, not merely resolvable

How to see the gate working, cheapest first. Row IDs refer to
[contracts/conformance-relevance.md](contracts/conformance-relevance.md).

## Prerequisites

- Hermetic: nothing beyond the repo.
- Live legs: `ANTHROPIC_API_KEY` in `.env`; the relevance seed set present
  (`evals/relevance-seed/seed.toml`).
- Estate demo: `make dev-up`, the judge cells and `relevance_cell` binding applied (they ship
  with the trust-fabric defaults this feature adds). The dev binding answers with Sonnet and
  judges with **Opus** — ADR-0067, not a ranking. Binding the same model to both is refused at
  resolution (`self_judged_relevance`), which is the check working.

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
make evals-relevance-qualify                              # the judge at LIVE_MODEL
make evals-relevance-qualify ARGS=anthropic/claude-opus@5  # a named candidate
make evals-relevance-qualify ARGS=--rubber-stamp           # must FAIL
```

Expected: per-case verdicts at majority-of-three, two numbers printed separately — overall
(≥90% floor) and supported-but-irrelevant (must be all correct).

**The candidate is an argument because ADR-0067 makes it one**: the judge may not be the model
that answered, so the estate needs a judge qualified for some *other* model than the one the
binding names.

**On the rigged candidate, corrected against what it actually does.** The plan predicted it
would clear the overall floor and fail only the second number. Measured: it scores **40%** and
fails *both*, because this seed set is balanced enough that affirming everything also gets
every mixed case wrong. The two-number design is justified instead by a candidate that misses
ONE supported-but-irrelevant case — it clears the floor comfortably and a single-number gate
would promote it (`test_a_nearly_right_candidate_clears_the_floor_and_still_fails`).

On pass, add the live cell and repoint `relevance_cell` in the trust fabric — a deliberate
human act, with the dated evidence in the record's comment, per the estate's promotion
precedent.

## 4 — The served surface (live; the one path no test covers)

```sh
make dev-up && DEV_IDP=1 make mcp-surface-up
```

Then ask a guidance-routed question through the served surface and read the trail:

```sh
psql -c "select payload->>'gate', payload->>'model', payload->>'kept_count',
         payload->>'irrelevant_count' from audit_entries
         where event_type='model_gate' order by timestamp desc limit 5;"
```

Expected: one `MODEL_GATE` per answered ask, `gate=relevance`, and `model` naming the **judge**
— which must not be the model in `ASK_MODEL`. Observed 2026-08-07:
`relevance | anthropic/claude-opus@5 | 9 | 1` while `ASK_MODEL=anthropic/claude-sonnet@5`.

**Two limits this step will show you, and both are real.** `vault-must-decline-001` ROUTES TO
ESTATE on the deployed surface — the router sees "audit log" — so it declines through estate
visibility rather than through this gate. The gate's decline on that case is proven on the
answering path (`make evals-smoke`) and in R1–R12. And the deixis handling is not uniform:
*"what is the recommended upgrade path for this platform?"* answers rather than declines.

## 5 — What did not change

- The corpus: untouched (ADR-0004).
- The failing case: unedited (FR-008) — it caught a real regression and keeps its teeth.
- Citation resolution: still required; the gate only narrows.
- A cross-product architecture question: still answered (R10) — ask one and check the
  citations span products.
