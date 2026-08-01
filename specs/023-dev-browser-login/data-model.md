# Data Model: 023 — a browser login for the dev lane

**Phase 1.** Three entities, none of them persisted. The provider holds no state before this
feature and holds none after.

---

## 1. Discovery document

**What it represents**: where to authorize, exchange, and fetch keys.

**One body, two paths.** Served at `/.well-known/openid-configuration` (already) and
`/.well-known/oauth-authorization-server` (new — the path clients actually probe, measured from a
404 in the surface's own log). Serving one body twice cannot drift; maintaining two could.

| Field | Value | Note |
| --- | --- | --- |
| `issuer` | the provider's configured issuer | **Host-resolvable.** What the client follows and what the surface compares a token's `iss` against. |
| `authorization_endpoint` | `{issuer}/authorize` | Unchanged. Already a real 302 redirect. |
| `token_endpoint` | `{issuer}/token` | Unchanged. Already a real PKCE exchange. |
| `jwks_uri` | `{issuer}/jwks` | What a *client* would use. The **surface** is configured separately and does not read this. |
| `registration_endpoint` | `{issuer}/register` | **New.** Its absence is why a client with no `client_id` had nowhere to go. |
| `code_challenge_methods_supported` | `["S256"]` | Unchanged, and must stay — PKCE is required, not offered (FR-010). |
| `_warning` | the existing `DEV_ONLY` string | **Must survive.** Becoming standards-complete must not make this look deployable (FR-013). |

### Validation rules

- **The `issuer` here and the `iss` the provider mints MUST be the same string** (FR-006a). The
  whole safety of advertising a host-resolvable name while the surface fetches keys elsewhere is
  that the *identity* does not differ — only the addresses do.
- **Both paths MUST return the same body.** A row asserts it, because the failure would be silent.

---

## 2. Registered client

**What it represents**: an editor that asked for an identifier so it could start a flow.

| Field | Note |
| --- | --- |
| `client_id` | Issued on request. |
| `redirect_uris` | What the client says it will be sent back to. **Constrained, not trusted** — see below. |

### Validation rules

- **Stateless.** Registration is repeatable without error and stores nothing (research F5). Editors
  re-register on reconnect; a provider that accumulated records would grow without bound and buy
  nothing, since it authenticates nobody and has no client to distinguish.
- **A redirect target is constrained (FR-011).** Authenticating nobody is not a reason to hand an
  authorization code to any address it is given. The provider is reachable from a developer's
  machine, and "it's only dev" is how a loopback-only assumption becomes an open redirector.
- **Registration MUST NOT become an authentication step.** If it starts deciding *who* may register,
  the provider has begun to authenticate someone and is no longer the thing quarantined in
  `tests/`.

---

## 3. Signing key

**What it represents**: the material a token is signed with, and the id a verifier looks it up by.

| Field | Before | After |
| --- | --- | --- |
| key | fresh per process | unchanged — still fresh per process |
| **key id** | **`test-key-1`, reused across processes** | **distinct per process** |

### Why the id is the whole fix

`src/surfaces/api/verification.py` caches keys with a **600-second TTL** and refetches immediately
on an id it does not recognise. Reusing the id defeats that: after a restart the cache is still
fresh and still holds the id, so it returns the **old modulus** and every token fails as
`unverifiable_identity` for up to ten minutes.

A distinct id per process makes the surface meet an unknown id, refetch on the spot, and verify
correctly — **with no change under `src/`**.

**This corrects an explanation this repository carries in two places**, including a merged pull
request: that the surface caches keys at startup and must be restarted. It does not, and it need
not.

### Validation rules

- The id MUST differ between two provider processes. A row restarts the provider and asserts it.
- Tokens from a previous process MUST be refused **promptly** — they were signed by a key that no
  longer exists. Prompt refusal is the correct outcome, not a regression.

---

## State transitions

None. No entity here is stored, updated, or expired by this feature. The provider holds a
short-lived authorization code between `/authorize` and `/token`, exactly as it does today, and
this feature does not change that.
