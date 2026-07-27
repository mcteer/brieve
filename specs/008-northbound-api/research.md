# Phase 0 Research: Northbound API

**Feature**: `specs/008-northbound-api` | **Date**: 2026-07-27

Nine decisions. The first three are dependency choices, the rest are design questions the
spec raises without answering — which is correct, because they are implementation.

---

## D1 — HTTP transport: FastAPI

**Decision**: FastAPI (MIT), on Starlette (BSD-3-Clause), served by uvicorn (BSD-3-Clause).
Pinned exactly, as `pg8000` and `pydantic-ai-slim` are.

**Rationale**: FR-012 requires a machine-readable operation description **generated from the
implementation rather than maintained beside it**. FastAPI produces its OpenAPI document
from the same function signatures and Pydantic models that validate incoming requests.
That makes the description structurally unable to drift from the surface — not because
anyone maintains it, but because there is only one thing to maintain. Every other option
leaves FR-012 as a document someone updates by hand, which is the failure FR-012 names.

Pydantic is already a base dependency, so the validation layer is not new — only the routing
and the ASGI server.

**Alternatives considered**:

- **Stdlib `http.server`.** No ASGI, no request validation, no generated description. Zero
  new dependencies, which is genuinely attractive under Principle VI — but it buys that by
  hand-writing routing, content negotiation, and the FR-012 document. Trading a maintained
  library for hand-written HTTP is not lean, it is just uncounted.
- **Starlette alone.** Gives ASGI and routing without the Pydantic-derived OpenAPI, so
  FR-012 becomes manual again. FastAPI *is* Starlette plus exactly the part FR-012 needs.
- **Django REST Framework / Flask.** Heavier, and neither derives a description from the
  types it validates against.

**Licensing**: MIT and BSD-3-Clause, both on `licenses/allowlist.txt`.

**Base dependency or extra**: an **extra** named `surfaces`, with the Makefile naming it
in `UV_RUN`, following the `adapters` precedent. The `pg8000` comment in `pyproject.toml`
explains why *that* one is a base dependency — its rows are merge-blocking and an extra CI
might not install would green the wrong thing. The distinction that decides this case:
`pg8000` is imported by **core**, so it cannot be optional without making core optional. A
web framework is imported only by `src/surfaces`, which is precisely what an extra is for,
and Principle I's "the core never imports an agent framework" generalises — the core should
not acquire a web framework in its install either.

---

## D2 — OIDC token verification: PyJWT

**Decision**: `PyJWT[crypto]` (MIT), which pulls `cryptography` (Apache-2.0 OR
BSD-2-Clause). Use `PyJWKClient` for JWKS retrieval and caching.

**Rationale**: verifying an OIDC ID token means checking an RS256/ES256 signature against a
key fetched from the provider's JWKS endpoint, then checking issuer, audience, expiry, and
not-before. The signature check is the part that must not be written here. PyJWT is narrow,
widely deployed, and does exactly this and nothing else.

**Alternatives considered**:

- **Hand-rolled verification.** Rejected without much deliberation. A JWT verifier that is
  subtly wrong — accepting `alg: none`, not pinning the algorithm, comparing signatures
  non-constant-time — fails open and looks fine in every test anyone thinks to write.
- **Authlib (BSD-3-Clause).** A full OAuth client stack. More than needed; the platform is
  a resource server verifying tokens, not a client obtaining them.
- **python-jose.** Less actively maintained, and has had CVEs in exactly the algorithm-
  confusion class this decision exists to avoid.

**Licensing**: `Apache-2.0 OR BSD-2-Clause` already appears in `licenses/allowlist.txt`,
which is `cryptography`'s reported string.

---

## D3 — What "fail closed when the IdP is unreachable" means for JWKS caching

**Decision**: **JWKS signing keys may be cached within a bounded TTL; identities may never
be honoured past their own expiry.** With a cold or TTL-expired key cache and an unreachable
provider, authentication fails closed.

**Rationale**: this looks like a contradiction with FR-016 and is not, because two different
things are being cached. A JWKS document is *public verification material* — the provider
publishes it for anyone to fetch, and it is not a credential. A token is an *identity claim*
with its own expiry. Caching the first is how every OIDC resource server on earth works;
honouring the second past its expiry is what FR-016 forbids, and this design never does it.

Refusing to verify a valid unexpired token merely because the provider is momentarily
unreachable would halt every authenticated caller during any IdP blip. That is precisely the
failure the dependency-monitoring reasoning behind ADR-0049 rejects: a shared dependency
going down should be visible in observability, not converted into thousands of individual
failures at the surface.

The line this draws: no fallback credential exists, no cached *identity* is honoured, no
token outlives its own `exp`, and a cold cache against an unreachable provider refuses.

**Alternatives considered**:

- **No JWKS cache at all.** Every request becomes a call to the IdP. Slower, and it makes
  the IdP a hard dependency on the request path rather than the key-rotation path.
- **Unbounded key cache.** Key rotation would never take effect, so a compromised and
  rotated-out key would keep verifying indefinitely.

---

## D4 — The durable audit store, and why it lands here

**Decision**: a `PostgresAuditSink` implementing the existing `AuditSink` protocol, plus a
separate read-only `EvidenceQuery` protocol, against new tables in `src/core/audit/`. Sink
and query live in **separate modules** (`postgres_sink.py`, `postgres_query.py`) so that
"the query cannot reach the sink" holds in the import graph rather than by convention.

**Rationale**: this is not an enhancement, it is the missing prerequisite. `AuditSink` today
has one implementation, `InMemoryAuditSink`, which loses everything when its process exits,
and one query method, `list_by_correlation_id`, which requires already knowing the answer's
correlation ID. FR-008 asks the API to expose the audit trail as a read path. There is no
trail to read.

It lands in `src/core/audit/` rather than under `src/surfaces/` because the evidence store
belongs to the platform whether or not anyone reads it through HTTP. Putting persistence
behind a transport would mean the trail exists only when that transport is deployed.

**Hash chaining across storage**: the chain is per-correlation-ID. The Postgres sink verifies
the same invariants `InMemoryAuditSink` does — sequence, `prev_hash` linkage, and `entry_hash`
recomputation — so integrity is a property of the entry rather than of the store that holds it,
and both implementations reject the same malformed entry.

**It cannot use `build_next_entry`, and that means the seam changes.** The helper reads the
chain, computes the next position, and hands back an entry to append separately. `AuditSink`'s
`append(entry)` is shaped around that: `seq`, `prev_hash`, and `entry_hash` are required fields
the caller supplies. A store that assigns position inside a transaction cannot honour that
interface — it can only verify what it was handed, which is the race again, or overwrite it,
which strands the caller's hash. So `append_event` replaces both, and they are removed rather
than kept alongside: leaving the older, more familiar function in place leaves the defect
reachable.

**Why it cannot use `build_next_entry`.** That helper reads the chain, computes the next position,
and returns an entry to append separately — a read-then-write that is safe only when there is
exactly one writer. Run chains satisfy that through 005's single-writer lease, which was an
undocumented coupling rather than a property of the audit layer. The evidence-access stream is
shared by every reader in a tenant and does not satisfy it, so the Postgres sink computes
position and link **inside the insert transaction** under a row lock. This also avoids
`list_by_correlation_id`, which returns every prior entry — bounded for a run, unbounded for a
stream that only ever grows.

**Alternatives considered**:

- **Defer to a later feature and read in-memory audit for now.** Would ship a read path that
  works only for runs still executing, which is close to the opposite of an audit trail.
- **A separate audit database.** A second operated component needing a named trigger under
  Principle VI, with no benefit at this scale. The SELECT-only role gets the isolation that
  matters without the component.

---

## D5 — "Cannot mutate," enforced twice

**Decision**: the read path is defended by two independent mechanisms.

1. **A distinct Protocol with no write methods.** `EvidenceQuery` has no `append`. Mutation
   is not unimplemented, it is unnamed — there is no method to call.
2. **A Vault dynamic database role holding `SELECT` and nothing else.** Even if the first
   defence were bypassed by a future refactor handing the evidence path a writable
   connection, Postgres refuses the write.

**Rationale**: ADR-0035 is explicit that this must be "an implementation property to prove
rather than assert." A single defence in application code is a convention that survives
exactly until someone passes the wrong object. The database grant is the one that holds
regardless of what the Python does, and it is testable directly: attempt a write on the
evidence connection and assert Postgres refuses it.

Two mechanisms rather than one because the first is the one that gets refactored away, and
the failure would be silent.

**Alternatives considered**:

- **Application-layer check only.** Rejected per the above.
- **A Postgres view with `WITH CHECK OPTION` / a read replica.** More machinery for the same
  guarantee the role grant already gives.

---

## D6 — The tenant dimension

**Decision**: a single `tenant_id` on the authenticated subject, sourced from an IdP claim,
enforced as the outermost dimension of every evidence query. One tenant is configured.

**Rationale**: `tenant` currently appears nowhere in `src/` or `tests/`, but ADR-0035 says
the read path is tenant-scoped and FR-011 requires a cross-tenant query to return nothing,
distinguishably. Something has to carry that dimension.

**Every audit entry needs one, including entries from runs no surface started.**
`start_governed_run` is reached from `src/adapters/pydantic_ai/agent.py` and from the 002–007
suites, none of which has an identity provider to read a claim from. So tenant resolves from
the subject's claim where a surface established one, and from a **configured default tenant**
in core otherwise. Making the field required without that source would stop the adapter
starting a run at all — a requirement whose only supplier is the newest component is a
requirement the rest of the system cannot meet.

**And it has to be inside the hash chain.** `AuditEntry` gains `tenant_id` and
`compute_entry_hash` takes it as an input. A column beside the chain would leave the field
that decides who may see a record alterable without detection — the one field in an audit
record where that is least acceptable. This changes the shape of a sealed seam and is
recorded as such rather than filed under "additive"; no migration is needed only because
audit has never been persisted.

The choice is when to introduce it, not whether. Introducing the dimension **now, with the
check enforced against one configured value**, means multi-tenancy later populates a check
that already runs. Introducing it later means retrofitting a scope boundary across an
evidence store that was built without one — and doing so retroactively for records already
written, which is the part that does not work.

**What this deliberately is not**: multi-tenancy. No per-tenant isolation of runs, storage,
policy, or credentials. 006 put that out of scope and it stays out of scope. This is one
dimension of the evidence read scope, which FR-011 requires by name.

**Alternatives considered**:

- **Reinterpret "tenant" as the existing subject scope.** Would satisfy FR-011's wording by
  redefining its terms, and would leave ADR-0035's tenant-scoping unimplemented while
  appearing implemented.
- **Introduce full multi-tenancy.** Materially larger than this feature, and out of scope by
  a prior decision.

---

## D7 — Starting a run: the `RunDispatcher` seam

**Decision**: a `RunDispatcher` protocol with two implementations — in-process for hermetic
tests, and Nomad for the enclave. The API depends on the protocol.

**Rationale**: FR-007a requires run start to return a handle rather than block. Under
ADR-0048 a run is a Nomad allocation, so the real dispatcher submits a job. But an API that
imported a Nomad client would make Principle VII false at the layer customers touch first —
"the substrate is the only permitted delta" cannot hold if the surface names the substrate.
This is the same seam shape ADR-0024 established for durability, for the same reason.

**Both implementations are in scope, and the Nomad one is not optional.** Nomad is inside
our boundary — we deploy it — so faking it would violate the standing rule that we fake only
what is outside the boundary. An API whose run-start path is proven only against an
in-process double has not been proven.

**What the handle contains**: `run_id` and `correlation_id`, which are the two identifiers
every other subsystem already keys on. Nothing about allocations, because the caller must
not learn the substrate either.

**Alternatives considered**:

- **The API calls `start_governed_run` directly in its own process.** Ties a run's lifetime
  to the API server's, which contradicts 005 entirely — a run must outlive the process that
  started it.
- **The API submits a Nomad jobspec directly.** Rejected per Principle VII above.

---

## D8 — FR-012's description, and detecting an undescribed operation

**Decision**: FastAPI generates the OpenAPI document; a **committed snapshot** of the
operation set is diffed by a check, in the shape `make enclave-digest-diff` already uses.

**Rationale**: generation alone does not satisfy SC-010's "an operation added without one is
detected," because FastAPI describes every route automatically — a new operation would
simply appear, silently. The detection has to be against a recorded baseline. The snapshot
makes adding an operation a visible diff in review, and gives the second transport something
committed to compare against rather than whatever the first surface happens to expose by
then.

**Alternatives considered**:

- **Generation with no snapshot.** Satisfies FR-012 and not SC-010.
- **A hand-maintained description.** Exactly what FR-012 forbids.

---

## D9 — FR-013: a claim-to-role mapping change is not a denial

**Decision**: route mapping changes through 007's existing `core.authority.changes` seam.
A change awaiting quorum returns a **pending** response carrying the change reference —
distinct from a refusal, and distinct from success.

**Rationale**: 007 already built this and named the trap in the docstring of
`BlockedPendingApprovalError`: *"The operation is queued for approval. This is not a
denial."* At an HTTP surface that distinction becomes a status-code choice, and the wrong
one is sticky — a client that sees `403` will treat a pending authority change as a
permanent refusal and stop asking, so a change that was in fact approved minutes later never
gets collected. `202 Accepted` with the change reference is the accurate answer.

The API surfaces the request and reports the disposition. It does not decide it, and it has
no path that could.

**Alternatives considered**:

- **`403 Forbidden`.** Wrong, per the above.
- **Block until quorum resolves.** Would hold an HTTP connection open for hours, and is
  forbidden by FR-015 in spirit and by every proxy in the path in practice.
