# Research: 023 — a browser login for the dev lane

**Phase 0.** Everything below was measured against the repository and the running service on
2026-08-01. Two findings correct claims this repository already carries.

---

## F1 — The surface's OAuth half is complete, and needs nothing

**Measured**: the served surface answers `/.well-known/oauth-protected-resource` with
`{"resource": ..., "authorization_servers": [...], "bearer_methods_supported": ["header"]}`. An
editor was observed fetching it and following the link. The MCP SDK provides this from
`AuthSettings`, which `served.py` already populates.

**Decision**: change nothing on the surface. **Nothing under `src/` moves** (FR-012).

**Consequence worth stating**: pointing `OIDC_ISSUER` / `OIDC_JWKS_URI` at Auth0 or Okta gives a
browser login today with no code change. That is asserted from the configuration path and is
**still unverified against a real IdP** — flagged in the spec's Assumptions for the same reason it
is flagged here.

---

## F2 — Issuer identity and key location are already separate, and the dev script welds them

**Measured**, and this is the finding the whole feature turns on:

- `src/surfaces/mcp/served.py:166-167` reads `OIDC_ISSUER` and `OIDC_JWKS_URI` as **two
  independent values**. The issuer is passed to the verifier as a string to **compare** against a
  token's `iss`; the JWKS URI is a location to **fetch**. The surface never resolves the issuer.
- `infra/bin/mcp-surface-up:52-54` then does:

  ```sh
  OIDC_ISSUER="$OIDC_ISSUER_OVERRIDE"
  OIDC_JWKS_URI="${OIDC_ISSUER_OVERRIDE}/jwks"
  ```

  **deriving one from the other**, which re-imposes the coupling the platform does not have.

**Decision**: break that derivation. Advertise `http://127.0.0.1:${port}` as the issuer — resolvable
by a client on the host — and keep a container-reachable name for the JWKS URI.

**Rationale**: this is why clarify's answer is safe. The client resolves the issuer; the surface
resolves the keys; neither resolves the other's name. The identities match because the provider
mints the same string the surface compares.

**Alternatives considered**:

- **`/etc/hosts` entry** for `host.docker.internal → 127.0.0.1`. Works, needs `sudo`, and is a
  change to the developer's machine rather than the repository — every new person hits the same
  wall with no error that explains it.
- **The machine's LAN address.** Both sides resolve it, and it changes with the network. A value
  that breaks when someone joins a VPN is worse than one that never worked.

---

## F3 — The restart trap was misdiagnosed twice, and the correct fix is one line

**Measured**: `src/surfaces/api/verification.py`.

- `DEFAULT_JWKS_TTL_SECONDS = 600.0` — keys are cached with a **bounded TTL**, explicitly so that
  rotation takes effect.
- `_key_for(kid)` returns a cached key only `if self.is_fresh()`, and on a miss **refetches
  immediately** before refusing.

**So the surface does not "cache JWKS at startup", and does not need restarting.** That explanation
was stated twice in this repository — once in the body of a merged pull request — and is wrong.

**The actual mechanism**: the dev provider mints a new keypair per process while reusing
`kid="test-key-1"`. After a restart the surface's cache is still *fresh* and still contains that
id, so it returns the **old modulus**, the signature check fails, and the caller sees
`unverifiable_identity` for up to ten minutes.

**Decision**: mint a distinct key id per provider process.

**Rationale**: the surface's own unknown-id path then does the work — refetch on the spot, verify
correctly, no restart, no window. This removes the condition rather than improving the message, and
requires no change under `src/`.

**Alternative considered**: persist the keypair across restarts, so outstanding tokens keep
working. Rejected — it writes an RSA private key to disk, which sits badly against this
repository's posture on secrets even in a dev-only tool, and it solves a smaller problem: with a
browser login the client re-authenticates on its own, so a dead token costs nothing.

---

## F4 — Two discovery paths, because clients probe the one we do not serve

**Measured**: the provider serves `/.well-known/openid-configuration` and returns **404** for
`/.well-known/oauth-authorization-server`. The 404 appears in the surface's own access log
immediately after a client fetched the protected-resource document — so this is what a client
actually requests, not what a specification permits.

**Decision**: serve the same document at both paths.

**Rationale**: they describe the same authorization server. Serving one body from two paths cannot
drift; maintaining two bodies could.

---

## F5 — Registration is the last missing piece, and it holds no state

**Measured**: the discovery document has no `registration_endpoint` and there is no `/register`
route. A client with no pre-configured `client_id` therefore has nowhere to obtain one (RFC 7591).

**Decision**: accept a registration and answer with an identifier, holding nothing.

**Rationale**: the provider authenticates nobody — that is why it is quarantined in `tests/`. There
is no secret to protect and no client to distinguish, so state would buy nothing and would
accumulate across reconnects. Registration must be repeatable without error because editors
re-register on reconnect (spec Edge Cases).

**Constraint carried from the spec (FR-011)**: authenticating nobody is not a reason to redirect an
authorization code anywhere it is asked to. The redirect target must be constrained, and how is a
design decision for `data-model.md` rather than an open question.

---

## F6 — What must not change

- **Nothing under `src/`** (FR-012, SC-007).
- **`/authorize` and `/token` are not rebuilt.** The first genuinely redirects with `code` and
  `state`; the second performs a real PKCE `S256` exchange and refuses a missing or wrong
  challenge. Both were read in full before this plan proposed anything.
- **PKCE stays required** (FR-010).
- **The direct-mint path keeps working** (FR-014). Every conformance lane depends on it, and
  replacing it would put a browser step in the middle of automated rows.
- **No new dependency is added.** The HTTP wrapper is standard library; `fake_oidc_provider.py`
  already imports PyJWT and `cryptography` to sign. An earlier draft of this line said the
  provider was standard-library only, which is true of one file and false of the pair — the fourth
  unverified assertion caught in this repository in two days, and the reason the check is now to
  read the imports rather than recall them.
- **The `DEV_ONLY` warnings stay.** Becoming more standards-complete must not make this look
  deployable (FR-013).

---

## Open for tasks, not for plan

- **Resolved by analysis, and it moved a requirement.** `make dev-up` runs only
  `infra/bin/enclave-up`, which starts neither the provider nor the surface — so FR-003's first
  draft, *"`make dev-up` MUST be sufficient"*, described something that was never true. The Makefile
  keeps them apart deliberately (*"the surfaces a person uses, separate from `dev-up` on purpose"*),
  so widening `dev-up` would fight that decision. FR-003a instead puts the obligation on the surface
  command, which is the one a person runs when they intend to connect something to it.
- Whether the two `DEV_IDP_ISSUER` uses — the provider's minted `iss`
  (`mcp-surface-conformance:66`) and the address a test process connects to (line 104) — should
  keep sharing one variable name. They mean different things and currently differ in value, which
  is confusing but correct; renaming is cheap and out of this feature's stated scope.
