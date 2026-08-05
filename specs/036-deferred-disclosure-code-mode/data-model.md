# Data Model: Deferred disclosure and code mode

**Feature**: 036 | **Date**: 2026-08-05

No new store. Every record below lands in the existing hash-chained audit trail and is
read through the existing governed read path — this feature adds vocabulary, not
infrastructure.

## Audit events (additive to `AuditEventType`, sealed core, Principle V review)

### `DISCOVERY_OBSERVED = "discovery_observed"`

What a model went looking for, and what that search matched. An **observation, never a
decision** (FR-006a): there is no allow/deny, no reason code, and nothing upstream of it
can refuse. Written by the adapter's disclosure layer at the moment the search resolves.

| Field | Type | Notes |
| --- | --- | --- |
| `queries` | list[str] | the search terms, verbatim |
| `matched` | list[str] | registered tool names disclosed by this search — **may be empty**, and an empty match is exactly the intent signal worth keeping (a model repeatedly searching for capability it was never granted) |
| `undisclosed_remaining` | int | how many deferred tools remain hidden after this search — lets a reader see disclosure progress without enumerating what was *not* disclosed |

Constraints: `matched` ⊆ the run's registered tool set by construction (a search ranges
over the corpus the disclosure layer holds, which is built from the registry). Carries no
schemas — names only. Distinguishable from a tool call by event type alone (FR-006c);
renders in evidence reads as "looked for", never "attempted".

### `PROGRAM_SUBMITTED = "program_submitted"`

The model-written program, verbatim — the recorded *cause* of the calls that follow
(US3, FR-012). Written when the `run_program` tool call is **allowed**; a denied
submission leaves only the ordinary `PRE_DECISION` denial, because a program that never
ran caused nothing.

| Field | Type | Notes |
| --- | --- | --- |
| `program` | str | verbatim, following `TURN_RECORDED`'s argued divergence from `redact_arguments`: this is the only durable copy of the cause |
| `program_sha256` | str | joins the submission to every inner call's record |
| `declared_calls` | list[str] \| null | null — reserved; the platform does not parse intent out of programs, it observes what they do |

## Run-scoped state (in-memory, adapter/seam; never persisted outside the trail)

### Disclosure posture

A property **of a run**, decided at agent build, recorded on the run's `RUN_START`
payload as `disclosure_posture`.

| Value | Meaning |
| --- | --- |
| `eager` | every tool's schema presented up front (today's behaviour; the default) |
| `deferred` | tools carry catalog lines; schemas load on discovery |
| `eager_fallback` | deferral was requested and the composition cannot support it for this model — **stated, never silent** (FR-004, SC-006) |

Transitions: none. Posture is fixed at build; a mid-run change would make the parity
comparison meaningless.

### Discovery set

The names disclosed so far, held by the framework's search layer (measured:
`ctx.discovered_tool_names`), consulted by the disclosure view, never by governance.
Monotonically grows; resets with the run. **Not in any checkpoint the platform writes** —
on resume the model re-discovers, which costs a search and preserves the invariant that
what a model knows about is derivable from the trail.

### Sandbox execution state

| Item | Shape | Rules |
| --- | --- | --- |
| Call request | `(name, args, kwargs, call_id)` from the runtime's snapshot | every one routes to `invoke_tool`; an unregistered `name` refuses on the existing path — one shape for tool, `open`, `eval`, and invented names alike (R5) |
| Resume value | governed result, or the refusal converted to an in-sandbox exception | a denied call MUST NOT be resumable with a fabricated value — the seam owns the conversion |
| Suspended state | opaque bytes from the runtime, plus the seam's own scannable ledger of what entered the sandbox | flows through `DurabilityProvider` under `_reject_credentials` (FR-011, R9); the ledger exists so the credential discipline never parses a `0.0.x` serialization format |
| Bounds | the run's existing `bounds` | checked and counted per inner call by `invoke_tool` itself — the seam adds no second bound and may not raise any (FR-010). The `run_program` submission is one governed step, so a program of N inner calls spends **N+1** of `max_steps` (default 100). A bound reached mid-program raises `ExecutionBoundExceeded` and **terminates the run** — the seam does NOT convert it to an in-sandbox failure the way it does a policy deny (FR-010a) |

## Relationships

```text
RUN_START {disclosure_posture}
   │
   ├─ DISCOVERY_OBSERVED*          (0..n, disclosure runs only)
   │
   ├─ PRE_DECISION "run_program"   (code mode runs; the submission is itself governed)
   │     └─ PROGRAM_SUBMITTED {program_sha256}
   │           ├─ PRE_DECISION tool-A ─ TOOL_OUTCOME ─ POST_DECISION   (inner call 1)
   │           ├─ PRE_DECISION tool-B ─ … denied — and the program cannot proceed past it
   │           └─ …                                                    (inner call N)
   └─ …
```

One correlation ID joins all of it, both directions (Principle IX). The parity property
in one sentence: **between `PRE_DECISION` and `POST_DECISION`, nothing in any record
reveals which invocation path issued the call.**
