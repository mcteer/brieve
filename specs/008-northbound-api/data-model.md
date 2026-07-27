# Phase 1 Data Model: Northbound API

**Feature**: `specs/008-northbound-api` | **Date**: 2026-07-27

Six entities, plus the sealed-core changes they require. This document names exactly what
changes shape and what does not — including one change that is **not** additive, which an
earlier draft got wrong and the analyze pass caught.

**Where these types live** (Principle V): the constitution names *identity flows* as sealed
core, so `AuthenticatedSubject`, `SubjectKind`, and claim-to-role mapping belong in
`src/core/identity/`, not in a transport module. The plan already argues this for the
dispatch seam — the CLI and portal must not import the API to reach a shared type — and the
same argument applies here. What stays in `src/surfaces/api/` is the part that needs a JWT
library: token verification, which *produces* an `AuthenticatedSubject` but does not define
it.

---

## AuthenticatedSubject

**Lives in** `src/core/identity/types.py`.

The identity established at the surface, and the root of the delegation chain. Everything
downstream — authority manufacture, tool calls, every audit record — names this subject.
Core defines it; each transport produces one. A type this central defined inside the first
transport would make transport two either import transport one or duplicate it.

| Field | Type | Notes |
| --- | --- | --- |
| `subject_user_id` | `str` | The IdP's stable subject claim. Becomes `GovernedRun.subject_user_id` unchanged |
| `tenant_id` | `str` | From an IdP claim. The outermost dimension of every evidence query (D6) |
| `roles` | `frozenset[str]` | Result of claim-to-role mapping. **Empty means refuse** — not a default role (FR-006) |
| `subject_kind` | `SubjectKind` | `HUMAN` (OIDC) or `WORKLOAD` (federated workload identity) |
| `expires_at` | `datetime` | The token's own expiry. Never extended, never honoured past (FR-016) |

**Validation**

- Absent, expired, or unverifiable → refuse, nothing executed (FR-005).
- `roles` empty → refuse. An unmapped claim is not permission (FR-006).
- `tenant_id` absent → refuse. A subject with no tenant cannot be scoped, and defaulting
  it would default it to something.

**What it is not**: a session. Nothing is stored server-side, because storing it would be
the credential store FR-001 says the platform does not operate.

---

## ClaimMapping

**Lives in** `src/core/identity/claims.py` — the mapping itself is pure data-to-roles logic
with no dependency on how a token arrived, so it is shared by every transport.

Governed configuration translating IdP claims into platform roles. Changing it is an
authority change (FR-013, ADR-0016), not an administrative edit.

| Field | Type | Notes |
| --- | --- | --- |
| `claim_name` | `str` | Which claim is read |
| `claim_value` | `str` | The value matched |
| `role` | `str` | The platform role granted |

**State transitions**: `requested → approved | denied | expired`, reusing 007's
`ChangeDisposition` verbatim rather than defining a parallel vocabulary. A mapping change
takes effect only on `approved`.

**The escalation path this closes** (ADR-0033): without gating, anyone with configuration
access grants themselves a role rather than being granted one.

---

## RunHandle

What starting a run returns. The thing a caller holds to ask what happened, rather than a
connection held open while it happens (FR-007a).

| Field | Type | Notes |
| --- | --- | --- |
| `run_id` | `str` | Stable identity across resumes — 005's `run_id`, unchanged |
| `correlation_id` | `str` | Joins prompt → hooks → tool call → audit (Principle IX) |
| `state` | `RunState` | Existing enum; the API adds no state of its own |

**Deliberately absent**: anything naming an allocation, a container, or a scheduler. The
caller must not learn the substrate any more than the surface does (D7, Principle VII).

---

## EvidenceQuery *(request)*

A read against the evidence plane, bounded by the querying subject.

| Field | Type | Notes |
| --- | --- | --- |
| `tenant_id` | `str` | **Not caller-supplied.** Taken from the subject; a caller-supplied value would be a request to widen scope |
| `correlation_id` | `str \| None` | Optional narrowing |
| `run_id` | `str \| None` | Optional narrowing |
| `time_range` | `(datetime, datetime) \| None` | Optional narrowing |
| `event_types` | `frozenset[AuditEventType] \| None` | Optional narrowing |

**The load-bearing rule**: every field a caller supplies can only *narrow*. The bounding
dimensions come from the subject. There is no parameter that widens scope, which is why
FR-011's cross-tenant case resolves to zero rows rather than to a permission check that
could be got wrong.

**What a cross-tenant attempt therefore looks like** (FR-011): since no tenant parameter
exists, the reachable attempt is narrowing by a `correlation_id` or `run_id` that belongs to
another tenant. That is the case the conformance row must construct. A row written against a
tenant parameter would assert something the surface does not expose and pass regardless of
behaviour.

---

## EvidenceAccessRecord

The meta-audit entry: who read which evidence, and when (FR-010). Written to the same
chained audit trail, because a separate store would be a second trail with its own
integrity question.

| Field | Type | Notes |
| --- | --- | --- |
| `subject_user_id` | `str` | Who read |
| `tenant_id` | `str` | The scope the read was bounded to |
| `query_shape` | `dict` | The narrowing supplied — **never the rows returned** |
| `result_count` | `int` | How many records matched |
| `disposition` | `EvidenceDisposition` | `SCOPED` or `OUT_OF_SCOPE` |
| `correlation_id` | `str` | **Its own, freshly minted.** Not the correlation ID of the run it read |
| `read_correlation_ids` | `list[str]` | What it read, so the record is still discoverable by run |

**Why `disposition` exists rather than inferring from `result_count`**: FR-011 requires a
cross-tenant query to be distinguishable from one that legitimately found nothing. Both
return zero rows. Only an explicit disposition tells an investigator which happened, and
that distinction is the whole point of the requirement.

**Why `query_shape` and not the results**: recording what was returned would copy evidence
into the meta-audit record, growing the trail proportionally to reads and duplicating the
records it describes.

**Why its own correlation ID** (FR-010a): appending the record to the chain of the run it
queried would mean **reading evidence writes into the evidence being read** — a later read
of that run would return something the earlier read created. FR-009 exists to keep the read
path from altering what it reads, and this is the subtlest way to violate it. Naming the
correlation IDs read preserves discoverability without the entanglement.

**Termination**: one record per read, regardless of how many rows matched. Reading the
meta-audit records is itself a read and produces one more record. This terminates; it is
noted because it is obvious once stated and expensive once shipped wrong.

---

## Sealed-core changes: two additive, one that changes shape

An earlier draft of this document claimed all sealed-core changes here were additive. That
was wrong, and the analyze pass caught it: the evidence table declared `tenant_id NOT NULL`
while `AuditEntry` had no such field and forbids extras, so nothing could have written the
column.

Fixing it properly means `AuditEntry` gains `tenant_id` **and the hash covers it**. The
alternative — a column outside the chain — would put the field that decides who may see a
record outside the integrity guarantee it depends on, so tenant could be altered without
breaking the chain. That is the one place this must not be true.

Changing `compute_entry_hash`'s inputs changes the shape of a sealed seam, which is a
Principle V matter and is stated plainly rather than filed under "additive". **No migration
is required**: audit has only ever existed in memory, so no persisted entry has a hash
computed the old way. That is a one-time property of doing this now, and it will not hold
for the next such change.

### `AuditEntry` — one new field, inside the hash

```python
tenant_id: str          # bounding dimension; covered by compute_entry_hash
```

`compute_entry_hash` in `src/core/audit/chain.py` takes `tenant_id` as an input alongside
`correlation_id`, `seq`, `event_type`, `timestamp`, `payload`, and `prev_hash`.

### `AuditEventType` — two new members

```python
EVIDENCE_READ = "evidence_read"
EVIDENCE_READ_REFUSED = "evidence_read_refused"
```

Adding members to a `StrEnum` does not break existing readers. Nothing is renamed or
removed.

### `EvidenceDisposition` — a new enum, in `src/core/audit/schema.py`

Beside the audit schema, not in a surface module. It types a field on a record written to
the core audit trail; defining it in `src/surfaces/` would leave core either importing a
transport or holding a record it cannot name.

### `EvidenceQuery` — a new Protocol, deliberately separate from `AuditSink`

```python
class EvidenceQuery(Protocol):
    def search(self, request: EvidenceQueryRequest) -> list[AuditEntry]: ...
```

**No `append`.** Not "append raises" — no append. `AuditSink` keeps `append` and
`list_by_correlation_id` exactly as they are; the read path is a different protocol
implemented by a different object holding a different database role (D5).

---

## Evidence schema

New tables in `src/core/audit/evidence_schema.sql`, separate from
`src/core/durability/schema.sql` because they are owned by a different subsystem and
granted to a different role.

```sql
CREATE TABLE IF NOT EXISTS audit_entries (
    tenant_id      TEXT        NOT NULL,
    correlation_id TEXT        NOT NULL,
    seq            INTEGER     NOT NULL,
    event_type     TEXT        NOT NULL,
    timestamp      TIMESTAMPTZ NOT NULL,
    payload        JSONB       NOT NULL,
    prev_hash      TEXT        NOT NULL,
    entry_hash     TEXT        NOT NULL,
    PRIMARY KEY (correlation_id, seq)
);

-- Every query is tenant-bounded first, so the index leads with it.
CREATE INDEX IF NOT EXISTS audit_by_tenant_time
    ON audit_entries (tenant_id, timestamp);
```

**No `UPDATE` or `DELETE` path exists in application code, and the evidence role is granted
`SELECT` only.** Append-only is enforced by the grant, not by everyone remembering — which
is the distinction ADR-0035 draws between a property proven and a property asserted.

**Grant timing and breadth, both of which bite if left implicit.** The existing dynamic role
grants `ON ALL TABLES IN SCHEMA public`, evaluated when a credential is issued. Naming
`audit_entries` explicitly means credential issuance **fails** if the table does not exist
yet, so the schema must be applied before the evidence role issues its first credential.
Granting `ON ALL TABLES` instead would avoid that ordering but would also let the evidence
role read durability's checkpoints, which is wider than intended. The resolution is
`ALTER DEFAULT PRIVILEGES` plus an explicit grant on `audit_entries`, with the schema
applied as part of bring-up rather than on first write.

**`tenant_id` on the row rather than joined**: the bounding dimension must be present on
the record being filtered. A join would make the boundary depend on another table being
correct.
