# Research: Task-scoped authority manufacture

**Feature**: `specs/016-task-scoped-authority` | **Date**: 2026-07-31

Everything below was established against the running enclave — Vault v2.0.3+ent — by
executing it, not by reading about it. Where a thing was *not* established, it says so and
names what would settle it. The enclave was restored to its baseline afterwards (F8).

---

## F1 — The resource-server feature exists, is off, and the flag is two-way

**Decision**: Bring-up activates `oauth-resource-server`; it is a normal bring-up step, not a
migration.

**What the enclave says**: `sys/activation-flags` lists `oauth-resource-server` under
`unactivated`. `sys/activation-flags/oauth-resource-server/activate` turns it on and
`.../deactivate` turns it back off — verified both directions in one session. So this is not
a one-way door, which removes the main reason to be cautious about switching it on in an
estate before the rest of the feature is ready.

**Rationale**: A reversible flag can be activated at bring-up alongside every other piece of
trust-fabric configuration, which keeps `make dev-up` the single description of what an
enclave is. An irreversible one would have forced a staged rollout and an ADR about when to
pull the trigger.

**Alternatives considered**: *Activate only when a resource-server profile is configured.*
Rejected — it makes the enclave's shape depend on optional configuration, and the absence of
the feature would then be indistinguishable from the absence of a profile.

---

## F2 — The trust profile takes static keys, so the issuer needs no public surface

**Decision**: Register the issuer's public key directly on the profile
(`use_jwks=false` + `public_keys`). The platform runs no discovery document, no JWKS
endpoint, and no HTTP surface for this at all.

**What the enclave says**: `sys/config/oauth-resource-server/{name}` accepts `issuer_id`,
`audiences`, `jwt_type`, `clock_skew_leeway`, `optional_authorization_details`,
`no_default_policy`, and either `jwks_uri` (with `use_jwks=true`) or `public_keys` — a list
of objects carrying `key_id` and `pem`.

Two traps found by hitting them:

- `public_keys` must be sent as **JSON objects**. The Vault CLI's `key=value` form produces
  `public_key at index 0 must be an object`; a JSON request body works. Terraform's
  `vault_generic_endpoint` sends JSON, so this is a CLI ergonomics issue rather than a design
  constraint — but it will cost an hour if nobody writes it down.
- `use_jwks` defaults to **true**, so omitting it yields `jwks_uri is required when
  use_jwks=true` even when `public_keys` is supplied. It must be set false explicitly.

**Rationale**: ADR-0056 chose the platform-minted tier as the default, and its cost was
supposed to be "a component that mints tokens". Static keys remove the *serving* half of that
component entirely: there is nothing listening, so nothing to secure, monitor, or keep alive.

**Alternatives considered**: *Serve a JWKS document from the API surface.* Rejected — it adds
a public endpoint whose availability becomes the platform's, to distribute a key Terraform can
place directly.

---

## F3 — Vault signs; the platform holds no key

**Decision**: An `ecdsa-p256` transit key signs the grant. The private key never exists
outside Vault.

**What the enclave says**: `transit/sign/<key>` with `marshaling_algorithm=jws` produces a
JWS-compatible ES256 signature in url-safe base64, and the public half exports as PEM ready
for F2's `public_keys`. Exercised end to end: a JWT was assembled from a Vault signature and
its structure accepted by Vault's own validator (F4 covers what it then said about the
claims).

`marshaling_algorithm=jws` is documented as *"currently only valid for ECDSA P-256 key
types"*, so ES256 is forced rather than chosen.

**Rationale**: This is what makes ADR-0056's "no second standing credential" true rather than
mitigated. The issuing code holds a Vault token obtained from its own attested workload
identity, exactly like every other component here.

**Alternatives considered**: *A PKI-issued short-lived signing certificate.* Rejected — the
private key would exist in process memory, which is weaker for no gain given transit works.
*Vault's identity OIDC token endpoint.* Rejected in ADR-0056 — `authorization_code` only, and
its role templates interpolate entity metadata rather than per-request claims.

---

## F4 — The JWT schema is stricter than RFC 8693 requires

**Decision**: The grant carries `iss`, `aud`, `sub`, `jti`, `iat`, `nbf`, `exp`, and
`authorization_details`.

**What the enclave says**: A token missing `jti` is rejected with
`JWT schema validation failed: claim jti/uti is missing` — logged by the Vault server, and
**not** returned to the caller, who sees a bare `403 permission denied`.

**Rationale**: `jti` is a replay-prevention identifier and its absence is a hard schema
failure, not a policy outcome. Recording it here saves the next person the hour it cost to
discover that the informative error only exists in the server log.

**Consequence worth carrying into the contract**: every RAR rejection presents to the caller
as an indistinguishable 403. Conformance rows must therefore assert the *reason* against
something other than the HTTP response — the server log, or a probe that isolates one
variable at a time. A row that asserted "403 therefore RAR worked" would pass for the wrong
reason on a malformed token.

---

## F5 — Entity resolution is the open integration detail, and it blocks everything

**Decision**: **Unresolved.** The implementing feature's first task is to establish how a
grant's subject binds to a Vault Identity entity.

**What the enclave says**: With a valid signature, a well-formed schema, and RAR details
present, Vault refuses with two errors in its log:

```text
2 errors occurred:
  * no alias found
  * error looking up entity
```

So the JWT's subject must resolve to an Identity **entity** through an **alias**, and none of
the obvious candidates worked: `sub` as the agent-registry entity UUID, `sub` as the
registration's display name, and both with a matching `client_id` claim. The registered
entity carries no aliases (`aliases: []`), and `identity/entity-alias` refused creation with
the resource-server profile's `config_id` as `mount_accessor` — so the profile is not an auth
mount and its accessor is not the binding key.

**What would settle it**, in the order worth trying:

1. HashiCorp's own agent-identity tutorial repository
   (`hashicorp-education/learn-vault-agentic-iam`), which is the only public artifact found
   that exercises this path end to end.
2. `vault path-help identity/entity-alias` against the enclave, to enumerate what accessors it
   will accept, and whether a synthetic accessor exists for resource-server profiles.
3. Vault's audit device, enabled temporarily, which records the resolution attempt with more
   structure than the server log's summary.

**Why this is a first task rather than a risk to monitor**: nothing else in the feature can be
demonstrated until a grant validates. Every conformance row, the whole of US1, and the tier
detection in US4 all sit behind it. A plan that scheduled it later would discover in week two
that it was week one's work.

**Rationale for not guessing**: the wrong guess here is invisible — a design built on an
assumed resolution mechanism looks complete and fails at the first live row. ADR-0056 was
written by checking the substrate rather than inferring it, and this feature inherits that
standard.

---

## F6 — The intersection is real, and the ceiling's two halves stay disjoint

**Decision**: Task scope narrows the **secrets** half of the ceiling. The harness-domain
ceiling is untouched.

**What the enclave says**: the two halves are already separate objects, exactly as ADR-0044
requires and `ceilings.tf` states in its opening comment:

| Half | Where it lives | What it bounds | Example |
| --- | --- | --- | --- |
| Secrets | Vault policy named by the registration's `ceiling_policies` | which paths a run's token may reach | `agent-ceiling-planner`: `secret/data/planner/*` |
| Harness | KV record at `harness-authority/harness-ceilings/<id>` | which tools and product actions | `{tool_names: [echo, plan], product_actions: [product.workspace.read]}` |

RAR's `vault:path_access` type addresses the first and cannot express the second. That is
precisely the split clarification chose, and it means this feature adds no rule to an engine
that does not already own it — Principle III's disjoint-jurisdictions requirement is satisfied
structurally rather than by care.

**Rationale**: had the grant tried to carry tool authority, it would have duplicated the
harness ceiling into Vault policy — the exact duplication ADR-0044 forbids.

---

## F7 — Entailed scope is derivable from what already exists at launch

**Decision**: Derive the grant's paths from the run's requested tools, via the packs that
declare them.

**What the enclave says**: `start_governed_run` already receives `requested_tools`;
`AuthorityScope` already carries `tool_names` and `product_actions`; pack manifests already
declare each tool's `name`, `risk_class`, `transport`, `handler`, and `product`. What they do
**not** declare today is which Vault paths a tool touches — `packs/vault/pack.toml` names
`vault_read` and `vault_write` as `secret_touching` without saying what they read or write.

So the derivation needs one new declaration: a per-tool path set in the pack manifest. This is
a small, additive manifest field — not a new artifact and not a new authoring workflow, which
is what clarification's "no authoring burden" answer was protecting.

**Rationale**: the alternative is inferring paths from handler code, which would be a static
analysis that breaks the first time a path is computed at runtime, and would fail *open* when
it could not tell.

**Alternatives considered**: *Declare the path set on the agent definition rather than the
tool.* Rejected at clarify — it drifts from the tools it describes. *Take the union of the
ceiling policy's paths.* Rejected — that is the ceiling, so the grant would equal it and the
feature would narrow nothing.

**Accepted limit, already recorded in the spec**: the grant is only as tight as the tools'
declarations. A `secret_touching` tool declaring `secret/data/planner/*` yields a grant no
tighter than the ceiling for a run that requests it. The property bought is that a run
requesting a *subset* of tools gets a *subset* of paths, which is the difference between
per-definition and per-task authority.

---

## F8 — What this research changed, and put back

Probing required real changes to the enclave. All were reverted and the reversion verified:

| Change | Reverted |
| --- | --- |
| Activated `oauth-resource-server` | Deactivated; `sys/activation-flags` shows it `unactivated` |
| Created `task-authority` transit mount + `grant-issuer` key | Mount disabled |
| Created `sys/config/oauth-resource-server/task-authority` profile | Deleted |
| Attached `agent-ceiling-planner` to the `planner-agent` entity | Policies restored to `[]` |
| Wrote `secret/planner/greeting`, `secret/applier/deploy` | Metadata deleted |

Recorded because the enclave is shared state and a research session that quietly leaves
configuration behind is indistinguishable from a feature that quietly requires it.
