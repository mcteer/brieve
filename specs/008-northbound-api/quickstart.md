# Quickstart: Northbound API

**Feature**: `specs/008-northbound-api` | **Date**: 2026-07-27

How to run this feature and prove it works. Validation guide, not implementation — the code
belongs in `tasks.md` and the implement phase.

## Prerequisites

```bash
make dev-up        # Terraform -> Vault -> Nomad -> harness (ADR-0048's order)
make dev-status    # Nomad up, Vault up (unsealed), Postgres up
```

The enclave is a prerequisite for six of the fourteen conformance rows, not an alternative
to them. `make dev-up` is idempotent — re-running with parts already up is fine, and it
never re-initialises a Vault that already has a raft store.

## The one thing that is faked, and the one rule about it

**The OIDC provider is a test double.** It is outside our boundary — we do not deploy the
customer's identity provider — which is exactly the case where faking is correct. Everything
else runs for real: real Vault, real Postgres, real allocations.

The rule that makes the double worth having: **it must run real OIDC flows and sign real
JWTs with a real key.** A double that returns a pre-baked subject without signing anything
would leave this feature's central guarantee — that identity is verified before it becomes
the subject of everything downstream — completely unproven, while every test passed.

## Validation

### 1. Hermetic rows

```bash
make check          # lint, typecheck, unit + component (no enclave)
```

Covers eight rows: identity-as-subject, fail-closed identity, unmapped claim, no static
credential, no tool route, description completeness, nothing-pauses-a-run, and IdP-
unreachable.

### 2. The full lane

```bash
make conformance
```

Adds the six enclave rows. **Fails loudly if the enclave is absent** rather than skipping.

### 3. The three things worth checking by hand

Each is a guarantee that is easy to implement in a way that passes tests without holding.

**The read path really cannot write.** Not "the code does not call append" — ask Postgres:

```bash
# Draw the evidence role's dynamic credentials, then attempt a write.
# Expected: Postgres refuses. Permission denied, from the database, not from Python.
```

If this succeeds, the SELECT-only grant is wrong and defence #2 is absent — leaving only
the application-layer Protocol, which is the one a refactor removes silently.

**Run start does not block.** Start a run whose work outlasts the request:

```bash
# Expected: the response returns with a handle while the run is still executing.
# The response time is unrelated to the run's duration.
```

A surface that blocks would contradict 005 outright — the feature that exists to let work
outlive a process.

**Zero rows, twice, differently.** Query as a subject in the tenant over an empty window,
then as a subject outside it:

```bash
# Expected: both return zero records to the caller.
# Expected in the trail: SCOPED for the first, OUT_OF_SCOPE for the second.
```

The caller must not be able to tell the difference — that would leak the existence of what
they may not see. The trail must. An investigator needs to distinguish "nothing happened"
from "you may not see it," and that distinction is the whole of FR-011.

### 4. The description snapshot

```bash
# Expected: the committed operation snapshot matches the generated document.
# Adding an operation without updating the snapshot fails here.
```

This is what makes the parity comparison possible later. It is not parity — that row stays
owed until a second transport exists (FR-014).

## What you will not find

- **No API key to configure.** There is no supported way to create one (FR-003). If you are
  looking for where to paste a credential, the absence is the feature.
- **No approval prompt.** Nothing here pauses a run to ask a human anything (FR-015). A
  claim-to-role mapping change returns **pending** and the caller collects it later; it does
  not hold a connection open for hours.
- **No compliance verdict.** The read path returns records with citations, never a judgment
  about what they mean (ADR-0035).

## Troubleshooting

| Symptom | Cause |
| --- | --- |
| Enclave rows fail with Vault sealed | `make dev-up`. Terraform run against a sealed Vault drops every resource from state and the next apply crashes the provider — bring it up before applying anything |
| Evidence queries return nothing for everyone | The subject's `tenant_id` claim is absent or does not match the configured tenant. A subject with no tenant refuses rather than defaulting |
| Every authentication refuses after an IdP restart | Cold JWKS key cache plus an unreachable provider is a correct fail-closed (D3). Check the provider is reachable, not the cache |
| A new route does not appear in the description | It does — the snapshot diff is what failed. Update the committed snapshot, deliberately |
