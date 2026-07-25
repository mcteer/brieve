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

## Adapter fixtures (004)

`adapter_fixtures.py` builds governed agent runs. Requires the `adapters` extra
(`uv sync --extra adapters`); every `make` recipe already passes it.

| Helper | Purpose |
| --- | --- |
| `governed_agent_fixture` | Agent + deps + side-effect counters + audit sink in one call |
| `scripted_tool_model` | `FunctionModel` issuing a fixed tool-call sequence, then text |
| `CountingHandler` | Registry body exposing `call_count` for `assert_no_side_effect` |
| `echo_toolset` | Framework tools whose bodies **raise** if executed directly |
| `build_probe_capability` | Co-resident capability recording what it saw, for ordering |
| `build_failing_capability` | Capability that raises, for fail-closed cases |

Two conventions worth knowing before writing an adapter test:

- **Framework tool bodies raise.** The core registry holds the real body; the framework
  toolset supplies only the schema the model sees. If a framework body ever executes, the
  governed mapping was bypassed, and the `AssertionError` says so.
- **Ordering is observed through `GovernedRun.probe_log`.** `build_probe_capability`
  snapshots the log when it runs, so a test can assert governance had already admitted the
  call rather than trusting list position.

`agent_definition_id` is required on every `start_governed_run` (004, FR-007). Use
`DEFAULT_AGENT_DEFINITION_ID` unless the test is about per-definition ceilings, in which
case pass `ceilings={...}` to `fake_identity_fabric` — an id outside that map refuses
rather than falling back to the default ceiling.

Breaking changes require a deprecation window consistent with other versioned seams.
