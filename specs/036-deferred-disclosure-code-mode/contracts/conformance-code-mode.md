# Conformance contract: code mode per-call parity

**Feature**: 036 | **Lane**: merge-blocking (`tests/conformance/adapter/`) | **Runs on**: every PR; requires the `sandbox` extra, which CI installs

These rows **are** ADR-0041's verification. The gate is unconditional: *"if it cannot be
independently demonstrated that every tool call issued from sandboxed code round-trips
the full hook pipeline … code mode does not ship in the governed path."* If any row here
cannot be made to pass honestly, the outcome is not a weaker row — it is FR-013: code
mode absent or refusing with the reason stated. ADR-0047 forbids the middle state.

**Who runs it**: CI's fast lane, automatically. No human-executed row in this contract.

## Rows

### C1 — N calls, N+1 decisions (FR-007, SC-003)

A program issuing N tool calls produces exactly N+1 governed decisions: one for the
`run_program` submission, one per inner call. Assert by counting `PRE_DECISION` events on
the correlation ID — none unaccounted for, at every N tested, including N=0 (a program
that computes and calls nothing: one decision, zero effects, not an error).

### C2 — Inner-call records are indistinguishable from structured-call records (FR-007, US3)

The same tool with the same arguments, called once structurally and once from a program:
between `PRE_DECISION` and `POST_DECISION` the records are field-for-field
indistinguishable. The code-mode trail additionally carries `PROGRAM_SUBMITTED` — the
cause — outside the compared span.

### C3 — A denied call fails inside the program and cannot be ridden past (FR-007, US2)

A program whose second call is policy-denied: the denial is recorded, the sandbox
receives the refusal as a failure (never a fabricated return value), and no subsequent
effect in the program occurs from the denied capability. The program cannot obtain by
continuing what it was refused at the call. **A deny is not a bound**: the program keeps
running and may make further (permitted) calls after a denial, where an exhausted bound
would have terminated it (C7c). The two must not be conflated in the seam — a bound
converted to an in-sandbox failure would let a program run past its own budget.

### C4 — An invented name refuses on the existing path (FR-008)

Programs calling `open(...)`, `eval(...)`, `__import__(...)`, and a name declared
nowhere: each arrives at the seam, routes to `invoke_tool`, refuses as an unregistered
tool, and **is recorded as that refusal**. No special-case handling by name anywhere in
the seam — the row asserts the refusal comes from the registry lookup, not from a
blocklist that would invite the question of what it forgot.

### C5 — The break fixture: a bypass turns the suite red (FR-009, SC-004)

The row ADR-0054 demands as an assertion rather than a review note. A test-local seam
handler that returns a value **without** calling `invoke_tool` must cause the parity
assertions to fail — demonstrated by running C1's assertion body against the rigged seam
and asserting it *fails*. This is the row that proves the other rows can lose; a suite
that cannot lose asserts nothing (the vacuous-mutation lesson 030 recorded).

### C6 — Suspended state is a checkpoint under the credential discipline (FR-011)

Seed a credential-shaped value through the seam (as an input, and as a resume value),
suspend, and assert the checkpoint write raises `CredentialInCheckpointError`. Asserted
against the seam's scannable ledger, not by parsing the runtime's serialization format
(R9) — the discipline must survive a runtime format change.

### C7 — Bounds apply per inner call, and the submission is one step (FR-010, FR-010a)

Two assertions, because the arithmetic is the trap. **(a)** Each inner call is checked and
counted once by `invoke_tool` on the existing path — the seam owns no bound and none is
settable from inside a program. **(b)** A program making N inner calls consumes **N+1**
steps of the run's budget (the `run_program` submission is the +1), so a program is stopped
by `max_steps` one inner call *before* an equivalent structured run — asserted with the
exact counts, **not** a "same total" claim, which the N+1 model makes false. And **(c)** a
bound reached mid-program surfaces as `ExecutionBoundExceeded` that **terminates the run**,
distinct from a policy deny (C3), which the program sees as an in-sandbox failure.

### C8 — Absent runtime, stated refusal (FR-013, SC-007)

Without the `sandbox` extra installed, a `run_program` call refuses with a stated reason
code naming the missing runtime. Asserted in an environment without the extra (a
subprocess with a filtered path is acceptable); silence or import error is a failure.

### C9 — The program is recoverable through the governed read path (FR-012, SC-005)

After a code-mode run: read its evidence through the platform's own governed read
operation and recover the program text and the ordered calls it caused, joined by
`program_sha256` and the correlation ID. Nothing outside the platform's records needed.

### C10 — Parity holds across a kill (FR-011a, US2 scenario 4)

The row pass 1 and the first draft both missed: parity is asserted only for runs that never
stop. Interrupt a program mid-execution, resume it (a new allocation / new attested identity,
014's dispatched-resume path), and assert **(a)** the calls made *after* resume each
round-trip `invoke_tool` under the **surviving grant** — same decision/reason/record shape as
the pre-kill calls (ADR-0026); **(b)** the inner calls made *before* the kill are **not**
re-executed — the sandbox snapshot resumes past them, so no side effect fires twice
(re-observe, never re-execute); **(c)** the N+1 step count and the bracket resolution survive
the boundary coherently, which is the concrete exercise of R11's nested-bracket question. If
this row cannot be made green, code mode does not ship for interruptible runs — the same
FR-013 fork the per-call rows face, applied to durability.

## Structural gates (unit lane, same change)

- **U1** — `pydantic_monty` is imported by exactly one module in `src/`
  (`adapters/pydantic_ai/sandbox_runtime.py`), asserted by grep-shaped gate with a
  positive control (FR-014a; Principle I).
- **U2** — `core/sandbox/` imports no framework and no runtime — the seam is a protocol
  plus a loop over `invoke_tool` (FR-014c).
- **U3** — the dependency line reads `pydantic-monty==<exact>`; the name `monty` appears
  in no dependency group (R7 — the wrong-project trap, asserted so it cannot regress).
