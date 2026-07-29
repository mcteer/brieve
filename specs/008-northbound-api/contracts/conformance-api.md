# Contract: Northbound API conformance lane

**Feature**: `specs/008-northbound-api`
**Status**: In force (008 landed)
**Depends on**: Constitution Quality Gates (v1.1.0); ADR-0033; ADR-0035; ADR-0047

## Purpose

Record the rows this feature puts **in force** from the moment it lands, the row it
**refuses to claim**, and — per constitution v1.1.0 — **who runs the rows no automated
check executes**.

## Command

```text
make conformance
```

Gains `tests/conformance/api`, which runs in **two places** and the split is structural:

- Most rows run **inside a Nomad allocation**, holding their own attested workload
  identity. That is what makes them exercise the attestation chain rather than sit beside
  it.
- Two run on the **host**, marked `host_enclave`. One drives the scheduler, so it cannot
  run inside something the scheduler placed; the other sets up a Control Group with an
  admin token, which the allocation deliberately does not have — no token in that jobspec
  is the property it exists to demonstrate. Rows marked *enclave* below need `make dev-up`: they run
against the real Vault, the real Postgres, and a real allocation, and **fail loudly when
the enclave is absent rather than skipping**. A test that skips itself reports the same
green as one that ran.

## Rows in force

| Row | Asserts | Spec | Enclave |
| --- | --- | --- | --- |
| Identity is the subject | The authenticated identity is the subject of manufactured authority and of every audit record for that correlation ID | FR-004, SC-001 | no |
| Fail closed on identity | Absent, expired, and unverifiable identities each refuse with zero executions | FR-005, SC-003 | no |
| Unmapped claim refuses | A valid token whose claims map to no role refuses; zero resolve to a default | FR-006, SC-004 | no |
| No static credential | No authentication path accepts or issues a platform-issued long-lived credential, and no supported configuration creates one | FR-003, SC-002 | no |
| No tool route | No registered route reaches a tool body; the API exposes no direct tool invocation | FR-007, SC-005 | no |
| Run start does not block | Dispatch returns a handle in under a second while the allocation is still being placed; Nomad places it; the allocation obtains its own credentials by presenting its own attested identity and starts the run | FR-007a, SC-005a | **yes** |
| Evidence is scope-bounded | Two identities with differing entitlements each see only their own scope; neither can widen it | FR-008, SC-006 | **yes** |
| Read path cannot mutate | A write attempted on the evidence connection is refused **by Postgres**, not by application code | FR-009, SC-007 | **yes** |
| Evidence access is audited | Every read produces exactly one meta-audit record naming who and when | FR-010, SC-008 | **yes** |
| Evidence-access records chain | Records land on the per-tenant evidence-access stream and chain to their predecessor; a modified or middle-removed record breaks the chain, a **truncated tail** is caught by the recorded head, and no run's chain is touched | FR-010a / FR-010d, SC-009a | **yes** |
| Stream integrity is checked | `verify_stream_integrity` detects a truncated stream and a modified record, and reports clean on an untampered store | FR-010e, SC-009c | **yes** |
| Concurrent reads are all recorded | Concurrent readers in one tenant each produce a record; zero lost, zero collided, and zero reads succeed whose record failed | FR-010b / FR-010c, SC-009b | **yes** |
| Zero rows are distinguishable | A cross-tenant *attempt* — narrowing by another tenant's correlation or run ID, since no tenant parameter exists — and a legitimately empty query both return zero rows and are distinguishable in the trail | FR-011, SC-009 | **yes** |
| Description is complete | Every exposed operation appears in the generated description; an operation added without updating the snapshot is detected | FR-012, SC-010 | no |
| Mapping change is gated | Against a **real** Control Group under a non-root token: the change is queued, the value is absent until quorum, and an ungated path applies instead of queueing — the control proving the submitter is not simply reporting pending for everything | FR-013 | **yes** |
| Nothing pauses a run | No path in this feature pauses, interrupts, or blocks a run | FR-015, SC-011 | no |
| IdP unreachable fails closed | With a cold key cache and an unreachable provider, authentications succeed in zero cases | FR-016, SC-012 | no |

## The row this feature refuses

**Four-transport surface parity — not claimed** (FR-014).

Parity is a property *between* transports, and there is one. A green row would assert a
comparison it cannot perform, which is precisely the passing stub ADR-0047 forbids. The row
stays **Deferred** in `ROADMAP.md` until a second transport exists.

What lands instead is the thing that makes the row *satisfiable*: a committed snapshot of
the operation set and its dispositions, so the second transport compares against something
recorded rather than against whatever this surface happens to do by then.

## Break fixtures

Each row ships a fixture demonstrating it **fails** when its guarantee is weakened,
following 004's pattern: fixtures are **self-verifying** — they construct the weakened
arrangement and assert the check raises, so they pass on a clean tree. A row whose failure
nobody has observed is a row nobody knows works.

Three are worth naming because they are the ones most likely to be written to pass rather
than to check:

- **Read path cannot mutate** — the break fixture hands the evidence path a *writable*
  connection and asserts the check still catches the mutation. A fixture that only removes
  the Protocol's type hint proves nothing; the database grant is the defence being tested.
- **No tool route** — the break fixture registers a route that reaches a tool through an
  alias, not one that literally names `invoke_tool`. A checker satisfied by the literal name
  passes the wrong thing, which is how this repository got it wrong twice before.
- **Zero rows are distinguishable** — the break fixture makes both cases return the same
  disposition and asserts detection. Both already return zero rows, so a fixture comparing
  row counts would pass against a broken implementation.
- **Evidence-access records chain** — the break fixture writes each record under a freshly
  minted correlation ID and asserts the check catches the unchained singleton. That
  arrangement satisfies "the record was written" and still leaves it deletable without trace,
  so a fixture that only counts records would pass against it. A second fixture truncates the
  newest entries: the chain still verifies, and only the recorded head catches it.
- **Concurrent reads are all recorded** — the break fixture restores the read-then-write
  path (`build_next_entry` outside the insert transaction) and asserts the race is detected.
  A sequential test passes against that arrangement every time, which is why the row has to
  drive concurrent readers rather than assert on one.

## CI runs the enclave rows on same-repo pull requests (as of 009)

Nine of the seventeen rows need the enclave. **009 closed this gap for same-repo pull
requests**: `.github/workflows/enclave.yml` stands up the full enclave and runs
`make conformance`, with the Vault Enterprise licence supplied as a repository secret.

**Fork pull requests remain uncovered, and always will be.** The lane is conditioned on
`github.event.pull_request.head.repo.full_name == github.repository` because a
fork-originating run cannot read repository secrets — that is GitHub's design, not a
configuration choice, and it is the right one. A lane that tried anyway would fail on every
external contribution in a way indistinguishable from a real regression.

So the responsible-party record narrows rather than disappears:

| Where the change comes from | What covers these nine rows |
| --- | --- |
| Same-repo branch or pull request | The enclave lane. A required check, and it fails the merge |
| Fork pull request | **The agent harness in the IDE**, per `AGENTS.md` — unchanged |

**That lane must exclude by marker, not by path.** The fast lane currently passes
`--ignore=tests/conformance/durability`, which worked while every enclave-dependent row
lived in one directory. `tests/conformance/api/` holds both kinds, so the path exclusion
would collect the nine enclave rows and **fail the fork-safe lane on the merge commit** —
they fail loudly when the enclave is absent, by design. 008's T057a changed it to
`-m "not enclave"`.

One property holds across both lanes and is worth keeping stated: the rows **fail loudly
when the enclave is absent** rather than skipping, so a false green is not obtainable by
running them in the wrong place — only by not running them at all. That was the whole
safety margin when a human was the runner; it is now the thing that makes the automated
lane's green mean something.

## The snapshot grew, and the parity row grew with it (011)

`operations.snapshot.json` went from four operations to ten. The parity row did not change:
it compares `operation_pairs()` against the snapshot, so a larger snapshot is a larger
comparison, and an operation added to one transport fails immediately in either direction.

That property is why 011 could add six operations without touching this row's
implementation — and why it added them **snapshot-first**, one at a time: grow the
snapshot, watch the row go red, add both surfaces, watch it go green. The row became the
development loop rather than a check run afterwards.

One thing the coverage half still cannot do is compare *verdicts*, which is a separate set
of rows in `tests/conformance/mcp/test_surface_parity.py`. Two surfaces can expose the same
ten operations and disagree about what each returns.

## The snapshot grew again (012): ten to fifteen

Five thread operations, landed snapshot-first one at a time — grow the snapshot, watch
parity go red, land both surfaces, watch it go green. The parity row's implementation did
not change, which is the property that makes it worth having.

**The portal did not grow it.** It is a *consumer* of this catalogue, not a third
implementation, so parity still binds exactly one pair (API↔MCP) while the portal's own
rows assert containment — that it exposes nothing this catalogue does not. Those live in
`specs/012-conversational-portal/contracts/conformance-portal.md`.

## Sealed-core review

This feature changes sealed core in five places, and **two of them are not additive**:

- Additive: two `AuditEventType` members, `EvidenceDisposition`, and the `EvidenceQuery`
  protocol.
- **Not additive**: `AuditEntry` gains `tenant_id` and `compute_entry_hash` takes it as an
  input, changing the shape of an existing seam.
- **Not additive**: the write seam becomes `append_event`, which assigns position and link
  rather than accepting them. `append(entry)` and `build_next_entry` are removed, not kept
  alongside — a second write path that computes position outside the store keeps the
  concurrency defect reachable by whoever calls the older function. Five core call sites move.
- Identity flows move *into* `src/core/identity/` rather than living in a transport, per
  Principle V, which also houses the tenant resolver every existing caller now needs.

An earlier draft of this contract claimed all of it was additive. It could not have been:
the evidence table required a `tenant_id` that `AuditEntry` had no field for. Putting the
column outside the hash would have been the cheaper fix and the wrong one — the field
deciding who may see a record would then be alterable without breaking the chain.

Per the Development Workflow and CODEOWNERS this requires **security-maintainer review**,
and the specific claim to verify is that no persisted entry exists with a hash computed the
old way. That is true only because audit has never left memory, and will not be true next
time.
