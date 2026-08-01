---

description: "Task list for 023 — a browser login for the dev lane"
---

# Tasks: A browser login for the dev lane, so nobody pastes a credential

**Input**: Design documents from `/specs/023-dev-browser-login/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/conformance.md](./contracts/conformance.md)

**Tests**: Test tasks are included. They are cheap here — the provider is an HTTP server on the
host — and the one row that matters cannot be automated at all, which makes the automatable ones
worth having.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1, US2, US3 per spec.md
- Exact file paths in every description

## Gate tasks in this feature

| Gate type | Required? | Where |
| --- | --- | --- |
| **Fail-closed** | **Yes** — the provider refuses a missing PKCE challenge and an unconstrained redirect target, and this feature's direction is making the flow *easier* | T014, T015a |
| **Conformance** | **Yes** — the served-surface lane must still pass, and both discovery paths must agree | T008, T016, T020 |
| **No-secret-leak** | **Yes** — the rejected design wrote a private key to disk; a row asserts none is written | T013 |
| **Correlation / evidence** | **No.** No run, no audit entry, no governed decision. Nothing here participates in a correlation walk. Stated rather than omitted. | — |
| **Eval** | **No.** No model, judge, pack, or policy. `OWED` stays empty. | — |

## Path Conventions

`tests/harness/`, `infra/bin/`, `tests/conformance/mcp_served/` — per plan.md. **Nothing under
`src/`** (FR-012, SC-007).

---

## Phase 1: Setup

- [X] T001 Read `tests/harness/dev_idp.py` and `tests/harness/fake_oidc_provider.py` end to end
      before changing either. `/authorize` already returns a real 302 and `/token` already performs
      a real PKCE `S256` exchange — this feature adds around them and rebuilds neither (research F6).
- [X] T002 Record the current behaviour as a baseline: `curl` both `.well-known` paths and `/jwks`,
      and keep the output. The 404 on `/.well-known/oauth-authorization-server` is the measurement
      this feature exists to answer, and it should be visible in the change rather than remembered.
- [X] T003 Confirm `tests/conformance/mcp_served` passes before anything moves, via
      `bash infra/bin/mcp-surface-conformance`. A later failure must be attributable to this work
      rather than inherited.

---

## Phase 2: Foundational — blocking prerequisites

- [X] T004 Extract the discovery document in `tests/harness/dev_idp.py` into a single function that
      builds it once, so the two paths in US1 cannot return different bodies. **One body, two
      routes** (research F4) — two bodies could drift, one cannot.
- [X] T005 Add `registration_endpoint` to that document, pointing at `{issuer}/register`.
- [X] T006 Keep the `DEV_ONLY` warning in the document unchanged (FR-013). Becoming more
      standards-complete must not make this provider look deployable.

**Checkpoint**: the document is built in one place and names the new endpoint. No route serves it
yet.

---

## Phase 3: US1 — a developer connects without holding a credential (P1)

**Goal**: an editor with no credential discovers, registers, and completes a browser sign-in.

**Independent test**: configure an editor with a URL and nothing else; connect; sign in; call an
operation.

- [X] T007 [US1] (FR-004) Serve the discovery document at `/.well-known/oauth-authorization-server` in
      `tests/harness/dev_idp.py`, alongside the existing OpenID Connect path. **This path was
      measured returning 404** in the surface's own log, immediately after a client fetched the
      protected-resource document.
- [X] T008 [US1] [GATE:conformance] Assert in `tests/conformance/mcp_served/` that both paths return
      **byte-identical** bodies, and that both name `registration_endpoint`.
- [X] T009 [US1] (FR-005) Implement `POST /register` in `tests/harness/dev_idp.py`, answering with a
      `client_id` and holding **no state** (research F5). The provider authenticates nobody and has
      no client to distinguish, so state would buy nothing and grow with every reconnect.
- [X] T010 [US1] Assert in `tests/conformance/mcp_served/` that registration succeeds **twice in a
      row**. Editors re-register on reconnect; a provider that errored the second time would work
      once per developer and then stop.
- [X] T011 [US1] Stop deriving the JWKS URI from the issuer in `infra/bin/mcp-surface-up` — remove
      `OIDC_JWKS_URI="${OIDC_ISSUER_OVERRIDE}/jwks"` and accept the two as independent inputs.
      `src/surfaces/mcp/served.py` reads them separately: the issuer is a string it **compares**,
      the JWKS URI a location it **fetches**. The script reimposes a coupling the platform does not
      have, and removing it is what makes the whole approach possible (research F2).
- [X] T012 [US1] Set the issuer to a host-resolvable address and the JWKS URI to a
      container-reachable one in `infra/bin/mcp-surface-conformance`, replacing the single
      `IDP_ISSUER` used for both. The provider's minted `iss` and the surface's expected issuer
      MUST remain the same string (FR-006a) — that identity is the only reason two addresses are
      safe. **Side effect worth making deliberate**: `DEV_IDP_ISSUER` currently means two things —
      the minted `iss` at line 30 and the address a test process connects to at line 104 — holding
      different values. After this change both are `127.0.0.1`, so the ambiguity disappears. Note it
      in the script rather than leaving a reader to wonder whether the collision is intentional.

**Checkpoint**: US1 is independently shippable. A client can discover, register, and sign in.

---

## Phase 4: US2 — the claims are the ones the platform already enforces (P1)

**Goal**: a browser login teaches the same identity model the platform enforces, including its
refusals.

**Independent test**: sign in through the flow and mint directly; compare what the surface makes of
each.

- [X] T013 [US2] [GATE:no-secret-leak] Assert in `tests/conformance/mcp_served/` that the provider
      writes **no private key material to disk**. This is the design that was rejected (persisting
      the keypair to keep old tokens alive), and a row is what keeps it rejected rather than
      re-adopted by someone solving the restart trap again.
- [X] T014 [US2] [GATE:fail-closed] Assert in `tests/conformance/mcp_served/` that `/authorize`
      still refuses a missing or non-`S256` challenge (FR-010). Asserted rather than assumed
      **because this feature's direction is making the flow easier**, and "just for dev" is how a
      requirement becomes optional.
- [X] T015 [US2] (FR-011a) **Observe a real client's `redirect_uri` before writing any constraint.**
      Log what arrives at `/authorize` from an editor doing a genuine discovery-and-sign-in, and
      record the value in this feature's research. **Nothing has ever measured this** — the one
      client watched never reached `/authorize` because discovery broke first, so no `redirect_uri`
      appears in any log. Editors commonly use `http://localhost:PORT/...`, a name rather than the
      IP literal, or a private scheme like `cursor://`.
- [X] T015a [US2] [GATE:fail-closed] (FR-011, FR-011b) Constrain the redirect target in
      `tests/harness/dev_idp.py` using what T015 observed, and assert a clearly-remote target is
      refused. **Check the host only** — scheme, port, and path stay free, because the portal
      already uses `https://127.0.0.1:8082/callback` and the harness uses
      `http://127.0.0.1:0/callback`, and a narrower rule breaks the portal, which lives in `src/`
      where FR-012 forbids a compensating change.
- [X] T015b [US2] Assert in `tests/conformance/mcp_served/` that both existing callers' redirect
      shapes still pass — the portal's `https` loopback and the harness's port-`0` loopback. **This
      row exists because the constraint is the one change here that can break something that
      already works**, and it would break it in `src/`, where this feature may not follow.
- [X] T016 [US2] [GATE:conformance] (FR-008, SC-003) Assert that a token obtained through the flow and one obtained
      by the existing `caller_token` path resolve to the **same** subject, tenant, and roles
      (FR-008). Note that `surfaces.caller_token` already walks the real flow rather than signing
      its own token, so this compares two real tokens rather than a token against a fixture.
- [X] T017 [US2] (FR-009, SC-004) Assert that claims mapping to **no** role are still producible through the flow and
      still refused by the surface (FR-009). **A harness that can only present a good identity
      cannot distinguish a working platform from a broken one** — the reason the provider takes
      claims from the caller in the first place.

---

## Phase 5: US3 — everyone told about the provider can reach it (P1)

**Goal**: the client resolves the issuer; the surface resolves the keys; the restart trap is gone.

**Independent test**: reach the provider from the host and from inside a container, and restart it
without restarting the surface.

- [X] T018 [US3] (FR-005a) Mint a distinct signing key **id** per process in
      `tests/harness/fake_oidc_provider.py`, replacing the reused `test-key-1`. The surface caches
      keys with a 600-second TTL and **refetches on an id it does not know**, so a per-process id
      makes it refetch on the spot (research F3).
- [X] T019 [US3] Document in that same file why the id changes and the key does not need persisting
      — including that the widely-repeated explanation, that the surface caches at startup and must
      be restarted, is **wrong**. It appears in a merged pull request, and correcting it only in a
      spec leaves it to be repeated from the code.
- [X] T020 [US3] [GATE:conformance] Assert in `tests/conformance/mcp_served/` that restarting the
      provider yields a different key id, and that a token from the previous process is refused
      **promptly and without restarting the surface** (SC-009). **Verified by restarting and
      calling** — not by reasoning about cache behaviour, which is how the wrong explanation
      survived twice.
- [X] T021 [US3] (FR-007, SC-005) Assert that the advertised issuer answers from the **host**, and that the JWKS URI
      answers from **inside a container** (SC-005). Both checked; neither inferred from the other.
      That inference is the single most likely way this feature ships working only on the machine it
      was written on.

---

## Phase 6: Polish & cross-cutting

- [X] T022 (FR-003a) Start the development provider from `infra/bin/mcp-surface-up` when it is not
      already listening, with the host-resolvable issuer. **Analysis found the first version of this
      task assumed work that did not exist**: `make dev-up` runs only `infra/bin/enclave-up`, which
      starts neither the provider nor the surface, so "ensure it is started by whichever script
      `dev-up` invokes" pointed at nothing. `mcp-surface-conformance` already does this and is the
      pattern to follow.
- [X] T022a (FR-003) Write down the full command sequence — enclave up, surface up, configure,
      connect — in the same place as T023. The Makefile separates `dev-up` from the surfaces *on
      purpose*, so the sequence is two commands and the documentation must say so rather than imply
      one. **A step a developer had to already know is the gap this feature is about**, reappearing
      as instructions instead of a token.
- [X] T023 (FR-002) Update `README` or `docs/development/` with the credential-free editor configuration:
      a URL and nothing else. **The absence of a token in that snippet is the deliverable**, and it
      should be somewhere a person will find it rather than only in this spec.
- [X] T024 (FR-014, SC-006) Confirm every conformance lane that used a directly minted token still passes, unchanged
      (FR-014). Automated rows must not acquire a browser step.
- [X] T025 Run `make check`, and assert **no file under `src/` differs** (SC-007) via
      `git diff --stat main -- src/`.
- [X] T026 (FR-001, FR-002, SC-001, SC-002, SC-008) Perform quickstart scenario 6 by hand: `make dev-up`, an editor configured with a URL and
      no credential, a browser sign-in, an operation answered — then wait for expiry and ask again.
      **Owed by name in the conformance contract.** It is the only row that tests what this feature
      is about, and the only one that would have caught the original problem.

---

## Dependencies

```text
Phase 1 (T001–T003)
   ↓
Phase 2 (T004–T006)   ← one document, built once; blocks US1 only
   ↓
   ├── Phase 3 US1 (T007–T012)
   ├── Phase 4 US2 (T013–T017)   ← needs Phase 1 only, NOT Phase 2 or US1
   └── Phase 5 US3 (T018–T021)   ← needs Phase 1 only
   ↓
Phase 6 (T022–T026)
```

**US2 and US3 do not depend on US1.** Both are about behaviour that already exists and must keep
existing; neither needs the new routes.

**T016 depends on T007–T012**, because comparing a flow-obtained token to a minted one requires the
flow to complete.

---

## Parallel opportunities

- **US2 and US3 run in parallel with US1** once Phase 1 lands — three of the four files involved are
  different.
- **T014, T015a, T017** all touch `dev_idp.py` and must be sequential with each other. **T015 is
  not one of them** — it is an observation, and it must complete before T015a is written at all.
- **T018–T019** touch `fake_oidc_provider.py` and are independent of everything in US1 and US2.
- **T011 and T012** touch different scripts and are independent.

---

## Implementation strategy

**MVP is US1 + US3, not US1 alone.** US1 makes a login possible; US3 makes the issuer reachable and
removes the restart trap. Shipping US1 without US3 gives a developer a login flow that points at a
host they cannot resolve — which is the exact failure being fixed, one layer along.

**US2 is the one to protect under pressure.** It adds no capability; it asserts that the flow did
not quietly loosen PKCE, widen a redirect, or start producing only well-mapped claims. Those are
the regressions a feature about *convenience* is most likely to introduce, and the least likely to
be noticed.

**T026 cannot be cut.** Every other row can pass while a developer still ends up pasting a token.

---

## Notes

**29 tasks**, of which 10 are rows. Small, and the smallness is the finding: the surface's OAuth half
already worked, `/authorize` already redirected, `/token` already exchanged. What was missing was
two routes, one constant, and one deleted line.

**Nothing is owed except T026.** No security review, no ADR amendment, no sealed-core change —
recorded here as well as in the plan because the previous three features each owed one, and its
absence should be visible rather than inferred.

**One task exists to correct the record** (T019). The explanation for the restart trap is wrong in a
merged pull request; fixing it only in a spec would leave the code free to teach it again.
