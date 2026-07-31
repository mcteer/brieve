# Data Model: Task-scoped authority manufacture

**Feature**: `specs/016-task-scoped-authority` | **Date**: 2026-07-31

Four objects. Two are new, one gains a field, and one is a wire format the substrate defines
and this feature only fills in.

---

## TaskGrant (new)

The authority established at launch. **Recorded as data, never as a credential** — a reader
of the record gains a description of the authority and not the authority itself (FR-015a).

| Field | Type | Notes |
| --- | --- | --- |
| `run_id` | str | The run this grant authorises. One grant per run. |
| `subject_user_id` | str | Who consented. From the `AuthenticatedSubject`, never from a request parameter. |
| `tenant_id` | str | Carried for the same reason every other record carries it — it bounds every read. |
| `agent_definition_id` | str | Which definition's ceiling was intersected. |
| `entailed_paths` | frozenset[str] | The resource paths the task entails, derived per F7. |
| `capabilities` | Mapping[str, frozenset[str]] | Per path, the operations granted. Vault's RAR is path→capabilities, not a flat set. |
| `expires_at` | datetime | Ceilinged by the definition's maximum duration (ADR-0026). |
| `issued_at` | datetime | |
| `arrangement` | Literal["federated", "platform_issued"] | Which tier minted it (US4). |

**Validation**

- `entailed_paths` MUST be a subset of the paths the definition's ceiling policy permits
  (FR-003). A grant that exceeded it is a defect, not a wider grant.
- `expires_at` MUST NOT exceed `issued_at` + the definition's maximum duration.
- Empty `entailed_paths` is **valid** — a task entailing no resource access gets a grant that
  reaches nothing, which is a correct grant rather than an error (spec Edge Cases).

**Lifecycle**

```text
issued (at launch) ──► in force ──► expired
                          │
                          └──► superseded by re-derivation on resume (same scope, new token)
```

The record does not change after issuance. A resume re-derives a *token* from it; it never
rewrites the grant, because rewriting it would make the resume a fresh authorization decision
rather than a continuation of the person's consent (FR-015b).

**Where it lives**: beside the run's other durable state, under the run role. Not in the
checkpoint — ADR-0026 says checkpoints hold state and never credentials, and while the grant
record is deliberately not a credential, keeping it out of the checkpoint keeps that
distinction from having to be re-argued by every reader.

---

## EntailedScope (new, transient)

Not persisted. The computation between "these tools were requested" and "this grant will
say". Named because it is the thing FR-004 refuses on and the thing F7's manifest field
feeds.

| Field | Type | Notes |
| --- | --- | --- |
| `paths` | Mapping[str, frozenset[str]] | path → capabilities, unioned across the requested tools |
| `undetermined` | frozenset[str] | Tools whose path declaration is missing |

**Validation**

- If `undetermined` is non-empty the launch **refuses** (FR-004). A tool that has not declared
  what it touches cannot be granted access to it, and granting broadly "to be safe" is the
  failure mode the spec's Assumptions name explicitly.

---

## Pack tool manifest — new field

The one additive change to an existing artifact (F7).

```toml
[[tools]]
name       = "vault_read"
risk_class = "secret_touching"
# NEW: what this tool reaches, and with what capability. Absent means undeclared, which
# refuses at launch rather than granting broadly.
paths      = [{ path = "secret/data/{agent}/*", capabilities = ["read"] }]
```

**Validation**

- A tool whose `risk_class` is `secret_touching` MUST declare `paths`. The loader refuses
  otherwise — the same shape as 013's rule that a non-repeatable tool must declare an
  observer, and for the same reason: the declaration is what makes the governance decidable.
- Templating (`{agent}`) resolves at grant time against the definition. Vault's RAR does
  **exact path matching**, so any template must be expanded to concrete paths before it
  reaches the grant — a wildcard that survived into `authorization_details` would be a path
  that matches nothing.

---

## Grant token (wire format, defined by the substrate)

What the platform mints and Vault validates. This feature fills it in; it does not design it.
Shape confirmed against the enclave (F4).

```json
{
  "iss": "https://harness.internal/task-authority",
  "aud": "vault",
  "sub": "<resolves to a Vault Identity entity — SEE F5, UNRESOLVED>",
  "jti": "<unique per grant; absence is a hard schema failure>",
  "iat": 1750000000,
  "nbf": 1750000000,
  "exp": 1750000900,
  "authorization_details": [
    { "type": "vault:path_access",
      "path": "secret/data/planner/greeting",
      "capabilities": ["read"] }
  ]
}
```

**Constraints the substrate imposes**

- `alg` is **ES256** — transit's JWS marshaling supports ECDSA P-256 only (F3).
- `jti` is mandatory (F4).
- `path` is matched **exactly**. No wildcards, no prefixes.
- `sub` must resolve to an Identity entity through an alias, and **how** is the open question
  F5 names. Every other field here is settled.

---

## Relationships

```text
AuthenticatedSubject ──┐
                       ├──► EntailedScope ──► TaskGrant ──► Grant token ──► Vault validates
requested_tools ───────┤                          │                            │
   └─► pack manifests ─┘                          │                            ├─ RAR constraint
                                                  │                            ├─ entity ACL policy
definition ceiling ───────────────────────────────┘                            └─ parameter constraints
   (bounds entailed_paths)                                                        (all three must pass)
```

The three-way check on the right is Vault's, not the platform's, and that is the property the
feature is buying: it holds when the platform's own code is wrong.
