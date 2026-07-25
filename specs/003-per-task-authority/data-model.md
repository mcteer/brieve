# Data Model: Per-Task Authority

**Feature**: `specs/003-per-task-authority`
**Date**: 2026-07-25

## Entities

### AuthorityScope

Harness-domain authorization set used for intersection and subset checks.

| Field | Type | Rules |
| --- | --- | --- |
| `tool_names` | `frozenset[str]` | Tool registry names the subject may invoke |
| `product_actions` | `frozenset[str]` | Stable product action ids (e.g. `product.workspace.read`) |

**Validation**: Both fields required (may be empty). Empty `tool_names` denies all tools;
empty `product_actions` denies all product actions when mirroring requires an action.

**Relationships**: Used by user fixtures, ceiling, requested task scope, policy scope, and
`TaskCredentialRef.effective`.

### TaskCredentialRef

Opaque, non-secret handle bound to a governed run after successful manufacture.

| Field | Type | Rules |
| --- | --- | --- |
| `credential_id` | `str` | Opaque id; not a bearer secret |
| `subject_user_id` | `str` | Human subject for this run |
| `expires_at` | `datetime` | UTC; `now >= expires_at` ⇒ expired |
| `effective` | `AuthorityScope` | Intersection result at issue time |

**Validation**: Must not carry raw tokens/passwords. Never logged as a secret value.

**Relationships**: Stored on `GovernedRun`; keyed into fake fabric for brokered material.

### GovernedRun (extensions)

Existing 002 entity gains:

| Field | Type | Rules |
| --- | --- | --- |
| `authority` | `TaskCredentialRef` | Required after successful start |
| `run_salt` | `bytes` (len 32) | In-memory only; never audited raw |
| `scope` | `frozenset[str]` | Remains tool-name projection of `authority.effective.tool_names` |
| `live_effective` | `AuthorityScope \| None` | Recomputed per invoke by the authority hook (`effective ∩ current_policy`); never persisted; never wider than issue-time effective |

### IdentityFabric (fake protocol)

Test/operator-facing fixture surface — not a durable store.

| Capability | Behavior |
| --- | --- |
| Resolve user scope | Returns `AuthorityScope` for `subject_user_id` or unavailable |
| Resolve ceiling | Returns ceiling `AuthorityScope` for the environment |
| Resolve policy | Returns policy `AuthorityScope` (default unrestricted fixture) |
| Resolve product entitlements | Returns `frozenset[str]` actions for `(user, product)` |
| Issue credential material | Stores brokered secret under `credential_id` only inside the fake |
| Simulate failures | Flags for unavailable / exchange_failed / mid-run policy shrink / mid-run entitlement shrink |

### ProductApi (fake)

| Capability | Behavior |
| --- | --- |
| Record wield | Appends call with subject/action; used to prove absence of side effects |
| Enforce federate/broker | Denies if entitlements or brokered grain check fails |

### Audit entries (new event types)

| Event type | When | Payload notes |
| --- | --- | --- |
| `authority_issued` | Successful manufacture | refs + hashes; no secrets |
| `authority_refused` | Start refused (amplification / identity fail) | reason code |
| `authority_denied` | Invoke denied for authority reasons | reason code |
| `authority_expired` | Invoke after TTL | reason `authority_expired` |
| `mirroring_decision` | Federate/broker gate | allow/deny + reason; no entitlement dump of other tenants |

All join on `correlation_id`. Hash chain rules remain as in 002.

## State transitions

```text
[no run]
   │ start_governed_run
   ├─ refuse → authority_refused audit (if appendable) → no TaskCredentialRef
   └─ issue  → authority_issued → ACTIVE (authority bound)
                    │
                    │ invoke_tool
                    ├─ expired → deny authority_expired (no side effect)
                    ├─ out of effective scope / mirroring deny → deny (no side effect)
                    ├─ identity/exchange fail → deny fail-closed
                    └─ allow → tool body (002 pipeline continues)
                    │
                    │ (no auto-refresh)
                    └─ new start_governed_run required after expiry
```

## Intersection algebra

```text
effective.tool_names =
  user.tool_names ∩ ceiling.tool_names ∩ requested.tool_names ∩ policy.tool_names

effective.product_actions =
  user.product_actions ∩ ceiling.product_actions ∩ requested.product_actions ∩ policy.product_actions
```

**Amplification check (start)**: `requested ⊆ user` and `requested ⊆ ceiling` for both
components. If false → refuse, no credential.

**Subset helper**: `assert_scope_narrowed(ref, at_most=user_scope)` asserts
`ref.effective.tool_names ⊆ at_most.tool_names` and
`ref.effective.product_actions ⊆ at_most.product_actions`.
