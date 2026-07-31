# Data Model: Task-scoped authority manufacture

**Feature**: `specs/016-task-scoped-authority` | **Date**: 2026-07-31

Four objects. One is an existing record gaining two fields, one is new and transient, one is
an existing manifest gaining a field, and one is a wire format the substrate defines and this
feature only fills in.

---

## DelegationGrant (extended — the record already exists)

The authority established at launch. **`DelegationGrant`, `issue_grant`, and the provider's
`save_grant`/`load_grant` already exist** from 005/014 — the durable consent object the spec
calls a "task grant" is that record with two fields added, not a second grant beside it. Two
grant records for one consent would be the fragmentation Principle VII forbids.

**Recorded as data, never as a credential** — a reader gains a description of the authority
and not the authority itself (FR-015a), which SC-006a makes falsifiable.

| Field | Type | Status | Notes |
| --- | --- | --- | --- |
| `grant_id` | str | existing | Referenced by the checkpoint via id only — ADR-0026 keeps credentials out of checkpoints. |
| `subject_user_id` | str | existing | Who consented. From the `AuthenticatedSubject`, never a request parameter (FR-006). |
| `agent_definition_id` | str | existing | Whose ceiling was intersected. |
| `requested_scope` | AuthorityScope | existing | Tools and product actions. **Unchanged by this feature** (F6) — the harness half of the ceiling. |
| `issued_at` | datetime | existing | |
| `expires_at` | datetime | existing | Ceilinged by the definition's maximum duration. |
| **`entailed_paths`** | **Mapping[str, frozenset[str]]** | **NEW** | path → capabilities. The secrets half, and the whole of what this feature adds to authority. A mapping rather than two fields because Vault's RAR is path→capabilities, not a flat set. |
| **`arrangement`** | **Literal["federated", "platform_issued"]** | **NEW** | Which tier minted it (US4). |

**Validation**

- `entailed_paths` keys MUST be a subset of the paths the definition's ceiling policy permits
  (FR-003). A grant exceeding it is a defect, not a wider grant.
- `expires_at` MUST NOT exceed `issued_at` + the definition's maximum duration.
- Empty `entailed_paths` is **valid** — a task entailing no resource access gets a grant that
  reaches nothing, which is a correct grant rather than an error (spec Edge Cases).

**Lifecycle**

```text
issued (at launch) ──► in force ──► expired
                          │
                          └──► re-derived on resume (same scope, new token)
```

The record does not change after issuance. A resume re-derives a *token* from it and never
rewrites it — rewriting would make the resume a fresh authorization decision rather than a
continuation of the person's consent (FR-015b).

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
                       ├──► EntailedScope ──► DelegationGrant ──► Grant token ──► Vault validates
requested_tools ───────┤                          │                            │
   └─► pack manifests ─┘                          │                            ├─ RAR constraint
                                                  │                            ├─ entity ACL policy
definition ceiling ───────────────────────────────┘                            └─ parameter constraints
   (bounds entailed_paths)                                                        (all three must pass)
```

The three-way check on the right is Vault's, not the platform's, and that is the property the
feature is buying: it holds when the platform's own code is wrong.
