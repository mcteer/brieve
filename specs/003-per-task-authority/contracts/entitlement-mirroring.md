# Contract: Entitlement Mirroring

**Feature**: `specs/003-per-task-authority`
**Status**: Planned
**Depends on**: `authority-binding.md`, 002 hook pipeline

## Purpose

Ensure product-affecting tools cannot wield shared grains or federated identity unless
the human subject’s product entitlements include the required action (ADR-0044).

## Tool metadata

| Field | Values | Default |
| --- | --- | --- |
| `product_mode` | `none` \| `federate` \| `broker` | `none` |
| `product` | `str` | Required when mode ≠ `none` |
| `product_action` | `str` | Required when mode ≠ `none` |

## Governance pre-hook order (pinned)

Within governance hooks, order is:

1. Authority gate (expiry + `live_effective` tool/product_action bounds — see
   `authority-binding.md`)
2. Entitlement mirroring (this contract)
3. Remaining 002 governance checks

Non-governance hooks run only after all governance hooks allow.

## Dual-bound product action check (pinned)

For `product_mode` ∈ {`federate`, `broker`}, allow only when **both** hold:

1. `product_action` ∈ `live_effective.product_actions` (authority gate; reason
   `authority_insufficient` if not)
2. `product_action` ∈ live user product entitlements from the fabric (this hook;
   reason `mirroring_denied` if not)

Live entitlements alone MUST NOT authorize an action outside the task’s
`live_effective.product_actions`.

## Behavior by mode

### `none`

Skip mirroring. Tool is harness-local / non-product.

### `federate`

1. Resolve entitlements for `(subject_user_id, product)` from identity fabric on
   every invoke (no wider cache).
2. If resolve fails → deny `identity_unavailable` or `exchange_failed`.
3. If entitlements empty or `product_action` ∉ entitlements → deny `mirroring_denied`.
4. Append `mirroring_decision` (allow/deny). On allow, proceed; product fake validates
   subject identity reference without a shared-grain credential object in the harness.

### `broker`

1. Same entitlement membership check as federate **before** any shared-grain wield.
2. Resolve brokered grain via fabric using `credential_id` only inside the fake.
3. If exchange fails → deny `exchange_failed`; no product side effect.
4. Append `mirroring_decision`. Product fake records wield only after allow.

## Invariants

1. Empty entitlements deny (never “unrestricted”).
2. Mid-run entitlement shrink **and** mid-run policy shrink are observed on the next
   invoke (`live_effective` + live entitlements).
3. Deny path: no product side effect; audit + correlation; no secret values.
4. Caller-visible messages use reason codes; do not dump other users’ entitlements.
