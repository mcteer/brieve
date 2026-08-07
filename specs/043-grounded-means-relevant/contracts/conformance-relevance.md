# Conformance contract: grounded means relevant, and the gate can lose

**Feature**: 043 | **Lane**: merge-blocking (hermetic) plus live legs | **Runs on**: every PR
(hermetic); live legs per their runner

**Who runs what**: CI's fast lane runs every R-row. The L-rows call a vendor and run outside
CI. **Named runner: the agent harness, driven by the maintainer (Dan McTeer), before the cell
is bound** (constitution v1.1.0). They fail rather than skip when the credential is absent.

**The stub most available here**: a fixture judge that affirms everything, letting every
existing case pass while the gate proves nothing. The fixture judge *does* affirm by default —
that is what keeps SC-003 true by construction — so the rows below are deliberately split:
R1–R4 drive the gate's refusing branches with their own claims, R7 rigs it off and must fail,
and the L-rows are where a real judge meets the real defect. A reviewer should read the fixture
judge's default as *scaffolding*, and this paragraph as the record that nobody mistook it for
coverage.

## The gate (US1)

### R1 — An all-irrelevant answer declines "not covered" (FR-001, FR-002)
Claims with resolving citations, a judge affirming none: disposition declined, reason is the
third vocabulary entry, distinguishable in the record from "did not resolve".

### R2 — The two decline grounds are distinguishable end to end (FR-002, SC-006)
One ask declining by resolution, one by relevance: the records differ in `declined_reason`, and
the irrelevant statements appear under `irrelevant`, never under `dropped`.

### R3 — Partial keep (edge case)
Judge affirms one claim of three: answered; the kept claim ships; two statements disclosed as
`irrelevant`; the relevance note present.

### R4 — Fail closed, three ways (FR-017)
Judge unreachable · cell unqualified/withdrawn · malformed verdict (no leading token): each
declines naming its cause; none answers as though the check passed; the three causes are
distinguishable.

### R5 — Cost bound (FR-018)
An ask whose claims all fail resolution never invokes the judge — asserted by a counting
fixture judge, not by reading the code.

### R6 — Unbound refuses before unavailable (FR-017; 026's rule)
No `relevance_cell` in the binding record: `relevance_unbound`, distinguishable from a
provider outage — "nobody decided" surfaces first.

## The gate can lose (US1, FR-009)

### R7 — Rig-off row
With no judge supplied to `answer_question`, R1's assertion FAILS. A suite that cannot lose
proves nothing.

### R8 — The production caller supplies the judge (`verify-the-production-caller`)
Driven against `surfaces/api/ask.py`, not against `answer_question`: the surface constructs and
passes a judge. If it stops, this row fails while every R-row above stays green — which is
exactly the gap 041 closed for registration, kept closed here.

## Nothing regresses (US2)

### R9 — Answering suites unedited and green (FR-004, SC-003)
Zero edits to existing answering eval cases; the recorded suites pass with the fixture judge
wired.

### R10 — Cross-product survives (FR-005, SC-004)
A question whose claims span two products' documents, all affirmed: answered. **This row would
fail if the fix were product-scoping**, which is its reason to exist.

## The record (US3)

### R11 — MODEL_GATE, first production writer (FR-016, SC-010)
Every relevance judgement writes `MODEL_GATE` with the cell identity, before the ask outcome
record; the payload carries counts and verdict, never statements; nothing else writes the gate
as anything but a model judgement.

### R12 — The decline is inspectable (FR-006, SC-007)
From a declined answer's records alone: what was considered, what was dropped on which ground,
and which model judged.

## The seed set (FR-014/FR-015)

### R13 — Loader floor
<10 cases, missing author, open-vocabulary verdict, or zero supported-but-irrelevant cases:
each refuses at load, never warns.

### R14 — Seeds cite the real pin
Every seed claim's citation resolves against the actual corpus; a seed citing an invented
anchor is refused — the judge must be qualified on the world the path produces.

### R15 — Qualification can lose
A rigged always-affirm candidate fails qualification on the supported-but-irrelevant cases
despite clearing the majority floor. Both numbers reported separately (038's two-gates rule).

## Live legs (named runner above; fail, never skip)

### L1 — The motivating case declines, live (SC-001, FR-008)
`vault-must-decline-001`, unedited, through the real path with the live judge: declined,
"not covered". One call, response printed (the before-180 rule).

### L2 — Smoke is green end to end (SC-002)
`make evals-smoke` exit 0, with the relevance leg included.

### L3 — The judge qualifies at majority-of-three (SC-008; the sampling lesson)
Seed qualification at majority-of-three per case: ≥90% overall AND every
supported-but-irrelevant case correct, both counts printed. The cell is bound only after this
passes — and the binding is a separate human act, not this row's side effect.
