# Contract: Authority Binding

**Feature**: `specs/003-per-task-authority`
**Status**: Planned
**Depends on**: `specs/002-governed-core` (governed run, hook pipeline, audit sink)

## Purpose

Bind short-lived, non-amplifying task authority to a governed run before any tool
invoke is possible.

## API surface

### `start_governed_run` (extended)

Required inputs beyond 002:

| Input | Type | Notes |
| --- | --- | --- |
| `subject_user_id` | `str` | Human subject |
| `requested_scope` | `AuthorityScope` | Task request |
| `identity_fabric` | protocol | Fake in tests |
| `clock` | clock protocol | `frozen_clock` in tests |

Behavior:

1. Resolve user, ceiling, and policy scopes from the identity fabric.
2. If any resolve path raises/unavailable → raise typed refuse (`identity_unavailable` or
   `exchange_failed` as mapped by the fabric) and append `authority_refused` when the
   audit sink is available.
3. If `requested_scope` is not a subset of user and ceiling (both components) → refuse
   with `authority_refused`; no credential.
4. Compute `effective` via intersection (see data-model).
5. Manufacture `TaskCredentialRef` with `expires_at = now + 15 minutes`.
6. Generate 32-byte `run_salt` in memory.
7. Append `authority_issued` (fail → no usable run; evidential gap).
8. Return `GovernedRun` with `authority`, `run_salt`, and `scope = effective.tool_names`.

### Invoke-time authority gate

A governance pre-hook MUST:

1. Deny if `clock.now() >= authority.expires_at` with reason `authority_expired`.
2. Re-resolve **policy** from the identity fabric on every invoke (no wider cache).
3. Compute live effective bounds (both components):
   `live_effective = authority.effective ∩ current_policy`
   (component-wise intersection). Stale wider issued authority MUST NOT win.
4. Deny if tool name ∉ `live_effective.tool_names` with reason
   `authority_insufficient` (in addition to 002 registry scope checks).
5. When the resolved tool has `product_mode` ≠ `none`, deny if
   `product_action` ∉ `live_effective.product_actions` with reason
   `authority_insufficient` before mirroring runs.

Entitlement re-resolution for product mirroring is defined in
`entitlement-mirroring.md` and also runs on every invoke.

## Reason codes

| Code | Meaning |
| --- | --- |
| `authority_refused` | Start refused (amplification or bind failure) |
| `authority_expired` | Credential past TTL |
| `authority_insufficient` | Tool/action outside effective scope |
| `identity_unavailable` | Identity fabric unavailable |
| `exchange_failed` | Credential manufacture/exchange failed |
| `internal_error` | Fail-closed on unexpected errors |

## Invariants

1. No active run without a bound `TaskCredentialRef`.
2. Effective scope never exceeds user ∩ ceiling ∩ requested ∩ policy.
3. Secret material never appears on the run object, audit, or spans.
4. Fail closed on identity, exchange, clock, or audit failures affecting authority.
