# Conformance contract: a model says what to do, and the platform stays exactly as governed

**Feature**: 040 | **Lane**: merge-blocking (hermetic), plus one enclave row | **Runs on**: every PR

**Who runs it**: CI's fast lane for every row except **M18**, which is enclave-marked and runs in
the enclave lane. If the enclave lane cannot run, the row **fails**; it is never skipped.

**The stub most available here** is a resume row proven against the in-memory provider only —
which stores the record object and round-trips a new field for free, so it passes whether or not
the SQL was ever widened (`memory.py:29`: *"a row proven against one says nothing about the
other"*). M7 exists to make that shape fail.

## The act is the model's (US1)

### M1 — Two models, two requests, two different acts (FR-001, SC-001)
Drive two runs whose recordings state different targets for the same capability; assert the two
acts differ accordingly. **Two, because one proves nothing**: a single run's act matching a
single request is indistinguishable from a constant that happens to match.

### M2 — The same authority decides, on the same facts it sees today (FR-002, FR-003, SC-002)
Assert a model-directed act traverses the identical pipeline — same entry, same hooks, same
bracket, same records — and that a denied capability refuses identically whether its request came
from a model or the platform. **Argument provenance is the only difference, and the row says so.**

### M3 — A capability that takes nothing is untouched (FR-012)
Byte-compare the records of a no-argument step before and after the widening.

## Meaning it later (US2)

### M7 — A revived step re-invokes with the model's request — against BOTH providers (FR-004, SC-003)
Interrupt a run at a step with non-trivial model-supplied arguments; revive; assert the re-invoke
carries the same request. **Parameterised over both durability providers, and that clause is the
row** — the in-memory one passes for free, so only the pair proves the SQL.

**Prove it can fail**: revert the field in-memory and assert the Postgres leg fails with an empty
request rather than passing on a default.

### M8 — Revival consults no model (FR-005, SC-004)
Count asks across the revival. Zero for the revived step — `already_chosen` now carries the
request beside the name, so honouring it costs no provider call.

### M12 — A pre-feature record revives as it first ran (FR-011, SC-008)
Build an intent with NULL arguments (the pre-feature shape); revive; assert the re-invoke carries
the **legacy constant** — the values its first attempt actually used — and that NULL and `{}` are
distinguishable end to end. **Repeating a different act than the one attempted is the defect,
even when the different act is emptier.**

## The one durable home (US3)

### M9 — The request rests in exactly one durable place (FR-006, SC-005) — *no-secret-leak*
After a step with model-supplied arguments, read **every** durable record: the request is in
`intents` and nowhere else. Pin `TOOL_CHOSEN` to its exact six keys; pin `PRE_DECISION` to
argument keys and hashes; assert `RUN_RESUMED` carries counts and the observer received only the
key. **The closures are asserted, not inherited** — each holds today because of somebody else's
decision, and a claim that holds by inheritance stops holding when they revisit it.

### M10 — Removing a finished act's request breaks nothing (FR-007a, SC-005a)
Clear `arguments` on a **closed** bracket; assert resume decisions, accounting and re-observation
are all unchanged. **And name the unsafe removal in the same row**: clearing an **open** bracket's
request makes its revival re-invoke with nothing — this feature's defect, reintroduced by policy.
The row is the constraint a future retention control inherits.

### M11 — Nothing expires it, which is the stated retention being true (FR-007b)
Assert an intent's arguments survive with no platform action across arbitrary elapsed time — the
behaviour, never the prose. The statement lives in the schema comment and field docstring; six
checks in this repository have matched comments instead of code, and this row is not the seventh.

## Getting it wrong (US4)

### M4 — A malformed answer is re-asked, never acted on (FR-008, SC-006)
Feed a recording whose entry does not parse as name-plus-arguments; assert re-ask, then assert
exhausting the bound ends the run in a recorded terminal state. **Both halves** — a bound never
reached is not demonstrated by the path that does not reach it.

### M5 — An oversized request is refused with its size, never its content (FR-007c, FR-007d, SC-006a)
Send a request over its capability's bound: refused, re-asked, never truncated; the refusal
record carries the byte count and the bound and none of the content. **Truncation is the
fail-open shape** — it performs a different act from the one described.

### M6 — A raised bound is honoured; the default holds elsewhere (SC-006b)
Register two fixture capabilities, one with a raised `max_request_bytes`; send the same large
request to both; assert one accepts and one refuses. **The same request to both is the row** —
two different requests would prove nothing about the bound.

### M17 — Malformed, refused, and failed are three records (FR-009)
One run exercising all three: a malformed answer (re-asked), a governance denial (refused), and a
request the capability itself rejects (performed and failed, `tool_error`). Assert the three are
distinguishable in the record — an operator told the wrong one fixes the wrong thing.

## Nothing that worked moves (US5)

### M13 — Every existing recording means what it meant (FR-010, SC-007)
Run the four recording-driven suites **unedited** and assert `"plan,apply,-"` parses to exactly
today's three choices — a bare name is a choice with **no arguments**. The suites are the rows
that prove model-driven runs work at all; editing them to pass would be the blast radius arriving
anyway.

### M14 — A recording can carry a structured choice (FR-001)
First non-space character `[` → JSON list of `{"tool": ..., "arguments": {...}}`; assert the
`"-"` terminal sentinel works in both grammars — one rule, and *"the run ended"* is never
inferred from punctuation.

### M15 — The same capability twice, two requests, two acts (edge case)
One run naming one capability at two steps with different requests: two intents, two acts, and
the second is not mistaken for a repeat of the first. **No programs means steps key distinctly
already (R2)** — this row is what keeps that claim measured rather than remembered.

## The guard (FR-013)

### M16 — Every defined capability is reachable or deliberately not (SC-009)
The ledger row: every capability name `core` defines is registered, or in
`DELIBERATELY_UNREACHABLE` with a reason and a record — `run_program` citing ADR-0065, the
authoring trio citing the successor feature by name. The AST sweep keeps the ledger itself
honest: a constant the ledger never heard of fails the row.

**Prove it can fail**: the companion removes a name from the ledger in-memory and asserts the
check trips. Two features shipped unreachable capabilities behind green rows; a guard that cannot
lose is the same defect wearing a checkmark.

## The production caller (SC-001's second half)

### M18 — A dispatched run acts on what the model named — *enclave lane*
Dispatch a run whose recording carries a structured choice through the real path — Nomad meta →
environment → `build_chooser` → the allocation — and assert the act happened against the
model-named target. **`verify-the-production-caller` is this repository's own recorded lesson**:
every other row here could pass while the capability stayed unreachable where dispatched work
actually happens.
