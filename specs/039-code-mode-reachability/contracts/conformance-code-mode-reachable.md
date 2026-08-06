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

### K2 — A definition whose ceiling omits it cannot (FR-002, SC-003)
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

### K4 — Where the runtime is absent, the refusal names what is missing (FR-007, SC-004)
With the runtime uninstalled, submit a program: refused with a reason naming the absent
capability. Assert it is **not** an import failure surfacing from three frames down, and **not**
a partial success.

### K5 — Three situations, three refusals (FR-008, SC-004)
Assert that an unavailable-runtime refusal, a policy denial, and a program that failed on its own
terms are distinguishable in the record. Three situations calling for three different responses
must not read alike — an operator told the wrong one fixes the wrong thing.

## Still governed (US3)

### K6 — Every call a program makes traverses the same pipeline as a direct call (FR-004, FR-005, SC-002)
Drive a program **through the registered path** that calls a permitted tool, a denied tool, and a
name that does not exist. Assert all three produce the same records the same calls issued
directly would, and that the invented name refuses as `tool is not registered` rather than
through any blocklist.

**"Identically" means the pipeline, and the row says which (R9).** A direct call from the step loop
carries arguments the **platform** chose; an inner call carries arguments the **program** wrote.
Same entry, same hooks, same bracket — different provenance of arguments. Stating that keeps this
row from reading as a stronger claim than it makes.

**This is 036's parity property re-asserted from the production caller.** 036 proves the seam has
one exit; this proves the thing with one exit is the thing a definition actually reaches.

### K6a — The step's shape is unchanged when the answer widens (R7)
Assert that widening the model's answer to a structured choice leaves all four of 031's
properties intact: bounded retry still validates before invoking, `already_chosen` still governs a
resumed step, `TOOL_CHOSEN` is still recorded per step, and the **platform** still performs the
invoke.

**Chosen over giving the agent a toolset, and this row is why.** A toolset moves execution inside
`agent.run_sync` and bypasses every one of those. `GovernedToolset` therefore **still has no
production caller** — a real gap, recorded rather than closed here, because closing it means
deciding whether a model may call tools directly, which changes what a governed step *is*.

### K6b — A malformed structured answer is retried, not executed (R7, blast radius)
Assert `resolve_step_tool`'s bounded retry covers a **malformed object**, not only an unpermitted
**name**. Assert also that a run whose ceiling omits the program tool behaves identically before
and after the widening.

**The bound on this change.** Every model-driven run's model is now asked for a structured object
rather than a bare word, so a model that could produce a valid name can produce an invalid object
— a failure mode the existing retry was not written for. One row checking the mechanism is not
the same as one checking the consequence, so this checks both sides.

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

### K13 — A program calling one non-repeatable tool twice writes TWO intents (R8)
Run a program that calls the same non-repeatable tool twice. Assert **two** intent records, and
that a resume re-observes **twice**.

**A defect 036 shipped, reachable only now.** The idempotency key is
`run_id:step_index:tool_name` and the seam **never advances `step_index`**, so both calls key
identically; intents insert `ON CONFLICT (run_id, idempotency_key) DO NOTHING`, so the second is a
silent no-op while `bracket_call` executes the effect regardless. One intent, two effects, and
resume re-observes once — which is precisely the shape the non-repeatable/observer machinery
exists to prevent, and which the constitution names as an in-force durability gate.

**A loop is the whole point of code mode.** *"N inner calls cost N+1 steps"* presumes one, so this
fires on the first realistic program rather than on a contrived one.

### K13a — Every existing idempotency key is byte-identical, including AFTER a program (R8)
Assert that a call made outside a program produces exactly the key it produces today — the
ordinal is folded in **only when non-zero** — and assert it **at a step that follows a program
which made several calls**.

**That second clause is the row.** The ordinal is scoped to the submission and cleared on exit; a
run-scoped counter would leave it elevated, so the next direct call would key `run:1:tool:3` and
the guarantee would hold right up until a program ran. **A property that fails only after the
feature is used is not caught by testing the feature's absence.**

**Not a nicety.** Changing every key would invalidate 014's durability rows and break resume for
any run in flight; the suffix must appear only in a situation that could not previously arise.

### K13b — A resumed DETERMINISTIC program's ordinals line up with the recorded intents (R8, R12)
Interrupt a program partway, resume, and assert the re-issued ordinals match the intents from the
first attempt — so re-observation resolves the right calls rather than a shifted set.

**This is what submission-scoping buys beyond the key.** A run-scoped counter would start the
resumed program at whatever the run had reached, and every ordinal would be offset — the intents
would be unmatchable and re-observation would resolve nothing.

**Depends on K16, which is what makes resume reach the program at all** (R13): until the intent
carries the arguments, a resumed submission re-invokes with no program and this row has nothing to
assert.

**Scoped to a deterministic program, and the row says why.** Resume re-runs the program **from the
start**; there is no mid-program checkpoint. A program that branches on a tool result may issue a
different second call, and then the recorded intent is for a call the re-run never makes — its
effect happened, re-observation establishes that it did, and the program's control flow has moved
on regardless. **Asserting alignment unconditionally would claim something the design cannot
deliver**; solving it means checkpointing inside a program, which is a different and much larger
feature.

### K14a — Every existing recording parses exactly as it does today (R11)
Assert `"plan,apply,-"` parses to the same three choices it does now — a bare name is a choice
with **no arguments**.

**Four suites already depend on this.** `conformance/choice/harness.py`,
`conformance/choice/test_a_model_chooses.py`, `conformance/durability/test_model_driven_resume.py`
and `conformance/reports/test_the_run_observes.py` all supply recordings through a
`recording(*answers)` helper taking bare names — and they are the rows that prove model-driven
runs work at all. **The same byte-identical discipline K13a applies to keys**: a format change
requiring every caller to move is a blast radius nobody measured.

### K15 — A program cannot submit a program (R10)
Assert that a call to the program tool **from inside a program** is refused with a stated reason.

**Refused because nobody decided it, not because it is obviously wrong.** The seam routes every
request to `invoke_tool` with *"no blocklist, no allowlist, and no special case"* — which is the
property that makes governance airtight, and which means a definition whose ceiling names the
program tool can recurse. The demonstration definition does. Nesting is absent from 036's Deferred
list, so it is permitted by **omission**; shipping reachability would turn that into a live
capability, unbounded except by the step budget.

It also breaks the ordinal: an inner submission clears it on exit, zeroing the outer program's
counter mid-flight so its remaining calls re-key from 1 and collide with intents already written.

**A refusal is reversible by a later record. An unbounded recursion that shipped is not.**

**Refused by a HOOK, and the row asserts where.** A name check inside the seam would be the
blocklist the seam's own docstring says it does not have — *"no blocklist, no allowlist, and no
special case… there is one decision maker, and it is the one that already decides"* — and it would
sit **before** `invoke_tool`, so the refusal would never be recorded, which FR-005 requires of
every call to something a definition may not use. A governance hook reading `call_ordinal > 0`
routes through `run_pipeline`, produces an ordinary recorded denial with a reason code, and the
program sees it as a deny it can route around: the seam's existing three-way distinction rather
than a fourth. **The row asserts the denial is recorded**, because a refusal nobody can find is
how this becomes a second decision-maker again later.

### K16 — A resumed step re-invokes with the arguments the model chose (R13)
Interrupt a run at a step whose model-supplied arguments are non-trivial, resume, and assert the
re-invoke carries **the same arguments** — not an empty map, and without a second provider call.

**The defect this row exists for is not about code mode.** Measured: `intents` carries
`tool_name` and no arguments (`schema.sql:93`), `already_chosen` is `{step: tool_name}`
(`entrypoint.py:814`), and a pending step **runs again** — the entrypoint says so in as many
words. Resume is honest today only because arguments are `_PROBE_ARGUMENTS`, a platform constant:
re-invoking reproduces them for free. The moment they come from the model, they are gone.

**So this row fails before the fix and passes after**, and it fails for **every** model-driven
run rather than only for a code-mode one. Same shape as K13: correct-looking, dormant, reachable
only once the feature that needs it ships.

### K16a — The trail still carries no arguments (R13) — *no-secret-leak*
Assert `TOOL_CHOSEN`'s payload is unchanged: `run_id`, `step_index`, `attempt`, `model`, `named`,
`outcome`, and **nothing else**.

**Because the two stores have opposite rules and this feature must not erode either.**
`record_choice`'s docstring argues the trail's: *"What is absent is load-bearing: no reasoning, no
prompt, no model output beyond the name. The model may have read a secret out of a tool result,
and an append-only trail is the one place that must never be written to."* K16 puts the model's
arguments in the **control plane**, which only resume reads. The obvious wrong move while fixing
K16 is to put them where they are easiest to see, and an append-only trail is the one place a
leaked secret can never be taken back from.

### K16b — The intent is the ONLY durable store of raw arguments (R16) — *no-secret-leak*
Assert that after a step with model-supplied arguments, the raw values appear in `intents` and
**nowhere else**: not in `PRE_DECISION`, not in the hook-decision span, not in `TOOL_CHOSEN`.

**Assert it at `RUN_RESUMED` too, which is where the arguments now travel.** Measured, two paths
that could have carried them are already closed and the reasons are recorded: an observer receives
`idempotency_key` **only** (`bracket.py:88`), never the intent; and `RUN_RESUMED` carries
`completed_steps` / `pending_steps` as *"COUNTS rather than contents — enough for an investigator
to see 'it skipped 3 and ran 2' without the trail carrying step payloads."* Those are the reasons
this row's claim holds today, so the row asserts them rather than inheriting them.

**Because the platform's implemented rule is stronger than K16a states.** `redact_arguments`
returns *"argument keys and content hashes — never raw values"* and `engine.py:101` applies it to
every invoke, so today raw values rest **nowhere**. R13 has to break that — a hash cannot be
re-invoked with — and this row is what keeps the break to exactly one store. **The obvious
regression is the cheap one**: someone widens the redaction to "pass through what resume needs"
and the trail starts carrying it too.

### K17 — An absent recording cannot vacuously satisfy a code-mode row (R15)
Assert that a dispatched run with **no recording** against the demonstration definition does not
count as a code-mode proof: either the ceiling's ordering makes the program tool unreachable by
the no-recording default, or the row asserts the submitted program is non-empty.

**`RecordedChooser` with nothing recorded answers `sorted(permitted)[0]` with no arguments**
(`recorded.py:82`) — a deliberate behaviour every pre-020 dispatched row depends on. Combined with
model-supplied arguments it can name the program tool and submit an **empty** program, which runs,
does nothing, and completes green. That is the stub shape ADR-0047 names and that this contract
already says is the one most available here.

### K14 — A fixture recording can carry a structured choice (SC-001)
Assert `parse_recording` accepts a recording carrying a tool **and its arguments**, and that
`RecordedChooser` returns it.

**Measured, this is on the dispatched path and not in a harness**: `build_chooser` in
`src/adapters/model_chooser.py` returns `RecordedChooser(parse_recording(recording))` for the
fixture provider, and every dispatched conformance row goes through it. Widening the model's
answer changes what a recording must contain, so the recording format is part of this feature
whether or not anyone planned it.

**And it decides what K7 proves.** If a recording carries only a bare name, the enclave row shows
the allocation carries the runtime and **not** that a model can reach it — a weaker claim than
SC-001 makes, wearing the stronger one's clothes.

## The guard that must be inverted (FR-013, SC-007)

### K11 — The 038 row now asserts reachability (R5)
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

### K12 — No shipped definition gains code mode (R6)
Assert that the demonstration definition is the only one whose ceiling names the program tool,
and that it lives in the dev estate.

**Registration forces that a ceiling CAN name it; it does not force which ceilings do.** 036
deferred that as configuration design and it stays deferred. The line between "one definition
exists so the capability can be proven" and "code mode is part of the offering" is a sentence in
a variables file, which is why it gets a row.
