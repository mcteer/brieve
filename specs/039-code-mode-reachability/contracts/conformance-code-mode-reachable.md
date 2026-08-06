# Conformance contract: code mode is reachable, and still governed

**Feature**: 039 | **Lane**: merge-blocking (`tests/conformance/adapter/`), plus one enclave row | **Runs on**: every PR

**Who runs it**: CI's fast lane for every row except **K7**, which is enclave-marked and runs in
the enclave lane. SC-001 says *"in the environment where dispatched work actually happens"*, and
no hermetic row can assert that — so K7 is automated and enclave-gated rather than nominated to a
person. If the enclave lane cannot run, the row **fails**; it is never skipped.

**These rows live beside 036's parity rows deliberately.** 036 owns *the seam is governed*; this
owns *the seam is reachable*. Splitting them across two directories would let one be read without
the other, which is the exact mistake that produced this feature: parity rows passing green for
months while the capability they describe could not be reached.

**The stub most available here** is a row that asserts the tool is registered and never drives a
program through the registered path. K1 and K2 exist to make that shape fail — registration is
necessary and proves nothing on its own.

## Reachability (US1)

### K1 — A definition whose ceiling names it can submit a program, through the registry (FR-001)
Resolve the tool **from the registry** and invoke it through `invoke_tool`; assert the program
ran and returned its value. Not by calling the handler — a row that called the implementation
directly would assert what 036 already asserts and would have passed for the last month.

### K2 — A definition whose ceiling omits it cannot (FR-002)
Attempt submission from a definition without the tool in its ceiling: refused
`authority_insufficient`, exactly as for any other capability outside a ceiling. **The registry
knows the name and the ceiling still decides** — that is the opt-in property, and this row is
what makes it true rather than claimed.

### K3 — The program is recoverable as the cause of what followed (FR-006)
Read the trail: `PROGRAM_SUBMITTED` carries the program **verbatim** and its digest, and each
inner call appears as its own governed step. Assert the ordering — the program is recorded
*before* it runs, because a program that fails partway still caused whatever it caused.

**Verbatim here and never in 038.** `PROGRAM_SUBMITTED` is on `TURN_RECORDED`'s precedent — a
model's own words, recorded as said. 038's `ARTIFACT_AUTHORED` carries digests only, because its
subject is a derivative of somebody else's private repository. The two members carry opposite
rules and the reason is the subject, not the format.

## The honest refusal (US2)

### K4 — Where the runtime is absent, the refusal names what is missing (FR-007)
With the runtime uninstalled, submit a program: refused with a reason naming the absent
capability. Assert it is **not** an import failure surfacing from three frames down, and **not**
a partial success.

### K5 — Three situations, three refusals (FR-008)
Assert that an unavailable-runtime refusal, a policy denial, and a program that failed on its own
terms are distinguishable in the record. Three situations calling for three different responses
must not read alike — an operator told the wrong one fixes the wrong thing.

## Still governed (US3)

### K6 — Every call a program makes is governed identically to a direct call (FR-004, SC-002)
Drive a program **through the registered path** that calls a permitted tool, a denied tool, and a
name that does not exist. Assert all three produce the same records the same calls issued
directly would, and that the invented name refuses as `tool is not registered` rather than
through any blocklist.

**This is 036's parity property re-asserted from the production caller.** 036 proves the seam has
one exit; this proves the thing with one exit is the thing a definition actually reaches.

### K6a — Governance is terminal at the toolset layer (Principle II)
Assert the model-facing toolset routes through `GovernedToolset` and that the framework's own
execution path is never taken. **This feature is that mapping's first production caller** — it
has existed since 004 with its central claim unexercised outside a test.

Assert also that the toolset is built from the run's **effective scope**: a run whose ceiling
omits the program tool sees no new capability. That is the bound on this change's blast radius,
since giving the agent a toolset affects *every* model-driven run rather than only code-mode ones.

### K6b — A run without the capability sees no change (Principle II, blast radius)
Assert that a run whose ceiling omits the program tool behaves identically before and after the
agent gains a toolset — same reachable set, same refusals.

**The bound asserted from the other side.** K6a checks the toolset is built from the run's
effective scope; this checks an unrelated run is unaffected by that change. Giving the chooser's
agent a toolset touches *every* model-driven run, which is a wider blast radius than "register a
tool", and one row checking the mechanism is not the same as one checking the consequence.

## The budget (US4)

### K7 — A program runs in the environment where dispatched work happens (SC-001) — *enclave lane*
Dispatch a run whose definition carries the program tool, submit a program, and assert it ran —
in the allocation, not the test process. **This is the row the whole feature exists for**: every
other row here could pass while the capability remained unreachable in production, which is
precisely the state 036 left and nobody noticed for a month.

### K8 — The budget consumed is N+1, measured rather than asserted (FR-009, SC-005)
Run a program making N calls and **measure** the steps consumed. An assertion that the arithmetic
holds would pass against an implementation where the bound never fires; this counts.

### K9 — A program that exhausts the budget ends the RUN (FR-010, SC-006)
Run a program whose calls exceed the run's bounds. Assert the **run** ends — the program does not
merely receive a refusal it could catch and continue past. **A bound a program can route around
is not a bound**, and the seam's docstring names getting this backwards as the most plausible way
code mode ships a hole.

### K10 — The exhausted outcome is distinguishable from completion and from denial (FR-011)
Assert three distinct records: a program that finished, a program whose calls were denied and
which completed having done nothing, and a program stopped by the bound. The middle one is not a
platform failure and must not be recorded as one.

## The guard that must be inverted (FR-013, SC-007)

### K11 — The 038 row now asserts reachability
`tests/conformance/authoring/test_producing.py` currently asserts the program tool is registered
**nowhere**, with a message asking for exactly this promotion: *"run_program is now registered;
W3's caveat is stale and this row should be promoted to drive the production path rather than the
seam."* Rewrite it to drive the production path.

**Inverted, never deleted**, and FR-013 makes that a requirement rather than a preference. The
obvious move when a guard fails is to remove it. The property it watches — *code mode's
reachability is a deliberate state rather than an accident* — is the one whose absence created
this feature, and 036's parity rows passing while the capability was unreachable is what that
absence looks like.

## Scope held (FR-012)

### K12 — No shipped definition gains code mode
Assert that the demonstration definition is the only one whose ceiling names the program tool,
and that it lives in the dev estate.

**Registration forces that a ceiling CAN name it; it does not force which ceilings do.** 036
deferred that as configuration design and it stays deferred. The line between "one definition
exists so the capability can be proven" and "code mode is part of the offering" is a sentence in
a variables file, which is why it gets a row.
