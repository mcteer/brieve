<!-- SPDX-License-Identifier: Apache-2.0 -->
# Data model: 019 — the MCP surface gets a server

Three entities, none of them stored. Everything here lives for the length of a connection or a
call; the only thing that persists is the audit record, and it belongs to the core.

**What this feature adds no model for**: operations, their arguments, and their results. Those
belong to `McpTransport` and are unchanged. Introducing a parallel model of them here is how
two surfaces drift, which is the thing ADR-0033 exists to prevent.

---

## Session

A client's connection, established once and used for many operations.

| Field | What it is | Rules |
| --- | --- | --- |
| `subject` | The authenticated calling user | Resolved **once**, when the session is established. **Immutable for the session's life** (FR-013a). A different caller means a different session. |
| `credential` | What that caller presented | Retained so validity can be re-evaluated. Never treated as authority in its own right. |
| `established_at` | When the handshake completed | Diagnostic only. **Not** an expiry basis — the credential carries that. |

**A session is not a grant.** It carries *who*; it never carries *may*.

### The state transition that matters

```
        handshake                    operation                operation
   ─────────────────▶ ESTABLISHED ──────────────▶ SERVED ─────────────────▶ REFUSED
                          │         credential      │      credential no
                          │         still valid     │      longer valid
                          │                         │
                          └── subject fixed here, and only here ──┘
```

**Both arrows leave the same state and the subject never changes on either.** This is the whole
of FR-013a's interaction with FR-013, drawn because prose invites the wrong reading:

- *Who* the session belongs to is settled at the handshake and never revisited.
- *Whether they may still act* is settled on every single operation.

The defect this diagram exists to prevent is a session that authorizes operations after the
credential that opened it has lapsed — which is what "fixed at the handshake" produces if it is
read as "verified at the handshake." A lapsed credential moves the *operation* to REFUSED; it
does not change, reassign, or clear the subject.

### Invariants

1. Exactly one subject per session, for the session's life.
2. No operation is served without the credential being valid **at that moment**.
3. A session with no acceptable credential never reaches ESTABLISHED (FR-012).
4. Two concurrent sessions share nothing — not subject, not results, not state (edge case).

---

## Subject

The calling user. **Not a new entity** — it is `core.identity.types.AuthenticatedSubject`,
the same type the API carries, resolved by the same verification.

Recorded here only to fix what must not happen to it:

- It MUST NOT be the served process's own identity (FR-010).
- It MUST NOT be a shared account standing in for callers (FR-010).
- It MUST reach the audit record intact, so two callers performing the same operation are
  **distinguishable** in the trail (FR-011).

**Why the third is stated as distinguishability rather than presence.** A check that a subject
was recorded passes perfectly against a shared account. The property with teeth is that two
different callers produce two different records, and it is the only one that fails when the
defect is present.

---

## Operation envelope

What crosses the protocol boundary on a single call, before the transport is entered.

| Field | What it is | Rules |
| --- | --- | --- |
| `operation` | Which operation the client asked for | Must be one the transport defines. An unknown name is refused **as unknown**, distinguishably from a known operation that was denied (edge case) — collapsing the two tells a caller which operations exist by which error they receive. |
| `arguments` | What the client supplied | Validated at the boundary against what the operation accepts. A rejection names what was wrong and happens **before** the governed operation is entered. |
| `subject` | From the session, never from the request | A client-supplied subject would be an impersonation surface. It is taken from the session by construction, not by convention. |

### Outcome

The transport already answers with `McpResult` — `ok`, the status the API would have returned,
and a payload. This feature adds no outcome vocabulary; it frames what exists.

**The four failures a client must be able to tell apart** (FR-007), because they call for
four different responses and would otherwise share a shape:

| | Means | Client should |
| --- | --- | --- |
| **Refused** | The governed core said no | Stop, and tell the user why |
| **Unknown operation** | No such operation exists | Fix the call |
| **Malformed request** | The operation exists; the arguments do not fit it | Fix the arguments |
| **Transport failure** | The surface is unreachable or broke | Retry, or report the platform down |

A surface that returned one shape for all four would be indistinguishable from a broken
platform on every denial — and, in the other direction, would let a genuine outage read as a
policy decision.

**This table listed three, and FR-007 names four.** Malformed request was missing, and the
tasks derived from the table rather than from the requirement — so a requirement with an edge
case of its own would have gone unimplemented behind a task that read as complete. Analysis
pass 1 found it. The omission is recorded rather than quietly corrected because the mechanism
is worth remembering: a downstream artifact that is *nearly* right is harder to catch than one
that is missing.
