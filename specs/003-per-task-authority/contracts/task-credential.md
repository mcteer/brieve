# Contract: Task Credential & Harness Helpers

**Feature**: `specs/003-per-task-authority`
**Status**: Planned
**Depends on**: `authority-binding.md`

## TaskCredentialRef

Public fields only: `credential_id`, `subject_user_id`, `expires_at`, `effective`
(`AuthorityScope`). No bearer secret fields.

## Clock protocol

```text
now() -> datetime  # timezone-aware UTC
advance(delta: timedelta) -> None  # frozen_clock only
```

Default TTL: **15 minutes** from manufacture.

## Harness exports (exact names)

| Symbol | Contract |
| --- | --- |
| `fake_identity_fabric` | Factory/builder for identity + entitlement + issue fixtures and failure modes |
| `fake_product_api` | Records product wields; enforces federate/broker checks in-process |
| `frozen_clock` | Deterministic clock with `advance` |
| `assert_scope_narrowed` | `assert_scope_narrowed(token, at_most=user_scope)` — both scope components ⊆ |

All exported from `tests.harness` (re-export pattern as 002).

## Content hashing

Authority-related redacted hashes: `HMAC-SHA256(run_salt, material)` hex digest.
`run_salt` is 32 random bytes per run, memory-only, never audited raw.

## Four-way deny assertions

Authority and mirroring deny tests MUST use harness helpers to assert:

1. Decision is deny (typed reason)
2. Audit chain includes the deny/mirroring event with correlation_id
3. No product/tool side effect
4. No secret values in audit/spans/messages (`assert_no_secret_values`)
