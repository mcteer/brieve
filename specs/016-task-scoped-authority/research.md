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

## F5 — Entity resolution: the subject binds through an alias on the agent-registry mount

**Decision**: **RESOLVED 2026-07-31.** A grant's `sub` resolves to a Vault Identity entity
through an entity alias whose `mount_accessor` is the **agent-registry mount's** accessor.

**What the enclave says.** The alias is created with the classic pair plus two OAuth fields:

```bash
vault write identity/entity-alias \
  canonical_id="<the registration's entity_id>" \
  name="planner-agent" \
  mount_accessor="agent-registry_xxxxxxxx" \
  external_id="planner-agent" \
  issuer="https://harness.internal/task-authority"
```

`name` and `mount_accessor` remain **mandatory** — `identity/entity-alias` refuses with
`'id' or 'mount_accessor' and 'name' must be provided` when given only `external_id` and
`issuer`. The accessor must be the agent registry's; `identity`'s is rejected. The JWT's
`sub` matches the alias `name`.

**How it was found, because the route matters for the next one of these.** Three attempts
failed on the wrong shape — `sub` as entity UUID, as display name, and with a matching
`client_id`, all against a `mount_accessor` of the resource-server profile's `config_id`.
The answer came from `vault path-help identity/entity-alias`, which lists `external_id`
("Unique external identifier from external IdP") and `issuer` — fields that exist only for
this purpose and are absent from the auth-mount alias shape. HashiCorp's
`learn-vault-agentic-iam` repository does **not** contain it: its README explicitly leaves
"the OAuth resource server profile, the subject/actor identity entities and aliases, and the
Agent Registry registration" as tutorial exercises.

**Verified end to end.** With the alias in place, the entity carrying `agent-ceiling-planner`
(`secret/data/planner/*`), and a grant naming one path, all three cases behave as specified:

| Grant | Path requested | Result |
| --- | --- | --- |
| `secret/data/planner/greeting` | `secret/data/planner/greeting` | **ALLOWED** — in ceiling ∩ in task |
| `secret/data/planner/greeting` | `secret/data/planner/other` | **REFUSED** — in ceiling, **not in task** |
| `secret/data/applier/deploy` | `secret/data/applier/deploy` | **REFUSED** — in task, **not in ceiling** |

The middle row is the feature. The refusal is Vault's, issued against a path the agent
definition's ceiling permits, because this run's task did not entail it.

**Consequences for the plan, and none of them are structural.** ADR-0056's tier analysis is
unchanged: Vault is still the resource server, the platform still computes scope, the static
public-key profile still works, and no signing key leaves Vault. What changes is one task's
content — provisioning now includes an entity alias per registered agent, keyed on the
`sub` the issuer will mint. That belongs beside the registration in `registry.tf`, since the
alias is meaningless without it.

**A second finding, previously invisible.** The entity must also carry its ceiling policy as
a **baseline policy** (`identity/entity/id/<id> policies=...`). Vault's RAR evaluation is a
restrictive intersection of the grant *and* the entity's own ACL, so an entity with no
policies is refused everything regardless of what the grant says. Today's registrations set
`ceiling_policies` on the agent-registry record and leave the entity's `policies` empty —
which is correct for the JWT-auth path in use now, and insufficient for this one.

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
