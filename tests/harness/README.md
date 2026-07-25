# Test harness (`tests/harness`)

Public API under the **semver seam promise** (see `docs/development/testing.md` and
`specs/002-governed-core/contracts/harness-helpers.md` /
`specs/003-per-task-authority/contracts/task-credential.md`).

## Import path

```python
from tests.harness import (
    assert_denied_closed,
    assert_correlated,
    assert_audit_chain,
    assert_no_secret_values,
    assert_no_side_effect,
    assert_hook_order,
    assert_scope_narrowed,
    fake_identity_fabric,
    fake_product_api,
    frozen_clock,
    scripted_agent,
    capture_audit,
)
```

The import path is part of the public contract. Packaging the harness as an
installable distribution for operators is deferred: the interface is stable now;
the distribution mechanism arrives with extension-authoring features. Moving the
import path later is a MAJOR seam change and rides the deprecation process.

## Assertion helpers

| Helper | Role |
| --- | --- |
| `assert_denied_closed` | Deny / fail-closed outcome |
| `assert_correlated` | One correlation ID joins audit + spans |
| `assert_audit_chain` | Append-only hash chain intact |
| `assert_no_secret_values` | Fixture secret markers absent |
| `assert_no_side_effect` | Zero executions (counter-based) |
| `assert_hook_order` | Governance before other |
| `assert_scope_narrowed` | Issued effective ⊆ user (or other) bound |

## Fakes

| Fake | Role |
| --- | --- |
| `scripted_agent` | Fixed tool-call sequences (no live model) |
| `capture_audit` | In-memory audit sink |
| `fake_identity_fabric` | User/ceiling/policy/entitlements + fault injection |
| `fake_product_api` | Federate/broker product wield counters |
| `frozen_clock` | Deterministic time; `advance()` for TTL |

## Authority notes (003)

- Default task credential TTL is **15 minutes** from manufacture.
- After expiry, invokes deny until a **new** `start_governed_run` (no auto-refresh).
- Brokered secret markers live only inside `fake_identity_fabric`, never on `GovernedRun`.

Breaking changes require a deprecation window consistent with other versioned seams.
