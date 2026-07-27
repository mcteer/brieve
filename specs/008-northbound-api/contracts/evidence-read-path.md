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

Chain integrity is verified identically in both sinks — sequence, `prev_hash`, and
`entry_hash` — so integrity is a property of the entry rather than of the store holding it,
and both reject the same malformed entry.

The chain's *inputs* do change: `tenant_id` joins them, because the dimension bounding every
read must sit inside the guarantee rather than beside it. A tenant column outside the hash
could be altered without breaking the chain, which would make the scoping decision the one
field in the record nobody could prove.

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

**Which makes the reachable attempt worth naming**, because the row that tests it must
construct something a caller can actually do: narrowing by a `correlation_id` or `run_id`
that belongs to another tenant. A check written against a tenant parameter would assert
something this surface does not expose, and pass regardless of behaviour.

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

**It goes on a dedicated evidence-access stream**, `evidence-access:{tenant_id}`, and names
the correlation IDs it read (FR-010a). Two properties must hold at once, and each obvious fix
destroys the other:

- **Append to the queried run's chain** and reading evidence writes into the evidence being
  read — a later read of that run returns a record the earlier read created. Harmless-looking
  until an investigator asks why the trail grew while nobody was running anything.
- **Mint a fresh correlation ID per read** and every record becomes a chain of one. Chains
  are per-correlation-ID and `seq == 0` takes `GENESIS_PREV_HASH`, so the record links to
  nothing and **can be removed without detection** — which is exactly what a record of who
  read what must not permit.

A stable per-tenant stream gives both: records chain to each other and no run's chain is
touched. It also brings two costs that the per-run chains never had, because a shared stream
is **contended** where a run chain is not:

- **Concurrency.** `build_next_entry` reads the chain, takes the next position, then appends —
  safe for a run only because 005's single-writer lease guarantees one writer, which nothing
  had written down. This stream has one writer per reader. Position and link are therefore
  computed **inside the insert transaction**, under a row lock (FR-010c).
- **Unbounded reads.** `list_by_correlation_id` returns every prior entry. For a run that is
  tens of rows; for a tenant's evidence stream it is every read ever performed, fetched again
  on every write. The same transactional append fixes it — the last row is what is needed, not
  the list.

**This terminates.** A read writes one record regardless of how many rows matched. Reading
the meta-audit records is itself a read and writes one more. Stated because it is obvious
once said and expensive once shipped wrong.

**And if the record cannot be written, the read fails** (FR-010b) — returning nothing rather
than returning evidence unrecorded. `start_governed_run` already behaves this way when its own
audit write fails. An access that succeeded while its record did not is the precise case this
whole section exists to prevent.

## What the chain proves, and what it does not

A hash chain proves that no record was modified and that none was removed from the middle: both
break the `seq` sequence or the `prev_hash` link.

**It does not prove the newest records still exist.** Truncate the last three and `seq 0..N-4`
verifies perfectly — which is unfortunate, because deleting the most recent entries is the
obvious move against a log of who read what. So each stream's highest position is recorded in
`audit_stream_heads`, updated in the same transaction as the append, and the evidence role
holds **no grant on that table at all** — not even `SELECT`, so the read path cannot learn what
it would need to forge.

## No verdicts

ADR-0035: *compliance answers surface evidence with citations, never verdicts.* The read
path returns records. It does not conclude that anything is compliant, and there is no
field in which it could — the platform lacks both the standing and the context, and a
confident wrong verdict is worse than a well-cited set of facts.
