# Contract: The evidence read path

**Feature**: `specs/008-northbound-api`
**Status**: Planned
**Depends on**: ADR-0035; Principle IX; Principle V

## Why this is a new class of access

Before this feature, evidence was **written and never read** through the platform. There is
no read path to extend — there is a read path to create, into the one store whose integrity
every other guarantee is reconciled against.

Two things follow from that. It must be impossible to mutate, proven rather than asserted.
And reading it must itself be recorded, because in an investigation who looked at what is
material.

## The prerequisite nobody built

Audit today is `InMemoryAuditSink` and `list_by_correlation_id`. It vanishes when the
process exits, and it can only answer questions whose answer you already know the
correlation ID of. **A durable, queryable audit store is in scope here**, in
`src/core/audit/`, because the evidence store belongs to the platform whether or not
anyone reads it over HTTP.

Chain integrity is unchanged: the Postgres sink verifies the same sequence, `prev_hash`,
and `entry_hash` invariants `InMemoryAuditSink` verifies, so integrity is a property of the
entry rather than of the store holding it, and both reject the same malformed entry.

## Cannot mutate — two independent defences

| # | Mechanism | Holds when |
| --- | --- | --- |
| 1 | `EvidenceQuery` is a **separate Protocol with no `append`** | Application code is correct. Mutation is not unimplemented — there is no method to call |
| 2 | The evidence Vault dynamic role holds **`SELECT` only** | Always. Postgres refuses the write regardless of what the Python does |

Two rather than one because the first is the one a future refactor removes, by handing the
evidence path a writable connection — and that failure would be silent. The second is
directly testable: attempt a write on the evidence connection and assert Postgres refuses.

ADR-0035 requires this to be "an implementation property to prove rather than assert." One
application-layer check is a convention that survives exactly until someone passes the
wrong object.

## Scope: every parameter narrows, none widens

The bounding dimensions come from the **authenticated subject**, never from the request:

- `tenant_id` — from the subject's IdP claim. A caller-supplied tenant would be a request
  to widen scope, so the field does not exist on the request.
- Entitlements — the existing scope algebra, not a parallel ACL. ADR-0035's "scope algebra
  rather than per-persona interfaces" is the same intersection machinery Principle IV
  already uses: *a team's developer asks about their team's estate; a compliance analyst
  asks across the tenant*, and they ask in the same place.

Everything a caller *can* supply — correlation ID, run ID, time range, event types — only
narrows. FR-011's cross-tenant case then resolves to zero rows structurally, rather than to
a permission check that could be written wrong.

## Zero rows means two different things

| Case | Rows | `disposition` | What an investigator concludes |
| --- | --- | --- | --- |
| Legitimately empty | 0 | `SCOPED` | Nothing happened in that window |
| Out of scope | 0 | `OUT_OF_SCOPE` | Something may have happened; this caller may not see it |

FR-011 requires these to be distinguishable **in the audit trail**, not in the response. The
caller sees zero rows either way — telling them which would leak the existence of what they
may not see. The distinction is recorded for whoever reads the trail later, which is the
only place it is useful and the only place it is safe.

## Evidence access is itself audited

One `EvidenceAccessRecord` per read (FR-010), in the same chained trail — a separate store
would be a second trail with its own integrity question.

It records **who, when, the query shape, the result count, and the disposition**. It does
**not** record the rows returned: that would copy evidence into the record describing it,
growing the trail proportionally to reads and duplicating what it points at.

**This terminates.** A read writes one record regardless of how many rows matched. Reading
the meta-audit records is itself a read and writes one more. Stated because it is obvious
once said and expensive once shipped wrong.

## No verdicts

ADR-0035: *compliance answers surface evidence with citations, never verdicts.* The read
path returns records. It does not conclude that anything is compliant, and there is no
field in which it could — the platform lacks both the standing and the context, and a
confident wrong verdict is worse than a well-cited set of facts.
