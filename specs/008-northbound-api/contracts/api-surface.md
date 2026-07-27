# Contract: The API surface and its description

**Feature**: `specs/008-northbound-api`
**Status**: Planned
**Depends on**: ADR-0033; ADR-0047; Principle II

## What the surface exposes

Five operations. The list is short on purpose: this is a way to **start and observe** work,
not a way to perform it.

| Operation | Purpose | Requirement |
| --- | --- | --- |
| `POST /runs` | Start a governed run. Returns a `RunHandle`; never blocks | FR-007a |
| `GET /runs/{run_id}` | Query run state through the handle | FR-007a |
| `GET /evidence` | Governed audit read, bounded by the caller's own scope | FR-008 |
| `POST /claim-mappings` | Request a claim-to-role mapping change. Returns pending | FR-013 |
| `GET /openapi.json` | The generated operation description | FR-012 |

## What the surface does not expose, and why

**There is no operation that invokes a tool.** A caller reaching a tool directly through the
API would be acting *beside* the agent rather than through it — a second path to the governed
core, which is the shape Principle II exists to prevent. Tools are reached by an agent within
a run. The API starts runs and reads what happened.

This is asserted, not reviewed (FR-007). The check **walks the application's registered
routes** and inspects what each reaches, rather than searching text. A text search passes a
file that mentions `invoke_tool` in a docstring and misses one reaching a tool through an
alias — a distinction this repository has now got wrong twice, in 006's boundary checker and
007's run-reference check, both times by matching prose instead of code.

## Response dispositions

Three, and the distinctions between them are load-bearing.

| Disposition | Meaning | Wrong alternative |
| --- | --- | --- |
| Success | The operation was performed | — |
| Refused | Denied: absent, expired, or unverifiable identity; unmapped claim; out of scope | — |
| **Pending** | Queued for quorum. **This is not a denial** (FR-013) | Returning a refusal teaches clients to stop asking, so a change approved minutes later is never collected |

The pending/refused distinction is 007's, carried to the surface. Its docstring already
says it: *"The operation is queued for approval. This is not a denial."* At an HTTP surface
that becomes a status code, and the wrong choice is sticky.

## Authentication

| Caller | Mechanism | Requirement |
| --- | --- | --- |
| Human | The organization's own OIDC provider | FR-001 |
| Machine | Workload identity federation | FR-002 |
| — | **Nothing else. No static credential, no exception, no supported configuration that creates one** | FR-003 |

FR-003 is a negative requirement, so it is asserted the way 007 asserted its own: enumerate
every authentication path and assert what is **absent**, matching against code with comments
stripped — because prose about API keys is not an API key.

## The description, and what it is for

FastAPI generates the OpenAPI document from the same signatures and Pydantic models that
validate requests, so the description cannot drift from the surface: there is one thing to
maintain, not two (FR-012).

Generation alone does not satisfy SC-010, because a new route would simply appear in the
document — silently. **A committed snapshot of the operation set is diffed by a check**, in
the shape `make enclave-digest-diff` already uses. Adding an operation without updating the
snapshot fails, which makes the addition a visible diff in review.

## Parity: this feature does not claim it

**The four-transport parity row stays owed** (FR-014). Parity is a property *between*
transports, and there is one. A green row here would be exactly the stub ADR-0047 forbids —
a check asserting a comparison it cannot perform.

What this feature owes instead is making that comparison possible when the second transport
lands. The committed snapshot is that: the operation set and its dispositions, recorded, so
the CLI's parity claim is asserted against something written down rather than against
whatever this surface happens to do by then.

Recorded in `ROADMAP.md` as it already stands: *Four-transport surface parity — 008 —
Deferred, ADR-0033.* That entry should be updated when the second transport lands, not now.
