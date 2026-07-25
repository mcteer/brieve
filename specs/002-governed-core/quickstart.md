# Quickstart validation: Governed Core MVP

**Feature**: `specs/002-governed-core`
**Purpose**: Prove FR-001–FR-015 end-to-end after `feat/002-governed-core` lands.
**Not**: an implementation guide with full module bodies (see `tasks.md`).

## Prerequisites

- Repo with 001 toolchain green: `uv sync` && `make check` baseline
- Python 3.12+, `uv`, `make`
- No Docker, IdP, collector, or live model required

## Scenario A — In-scope allow path joined (US1 / SC-001 / SC-003 / SC-004)

```bash
uv sync
# Run the component test module that covers in-scope allow (name finalized in tasks):
pytest tests/component/test_governed_allow.py -q
```

**Expect**:

- Tool body executes exactly once
- Audit trail by correlation ID includes run start, pre-decision, tool outcome, post-decision
- Hook-decision spans carry the same correlation ID
- `assert_correlated` / `assert_audit_chain` / `assert_no_secret_values` pass

## Scenario B — Unregistered / out-of-scope deny (US2 / SC-002)

```bash
pytest tests/component/test_governed_deny.py -q
```

**Expect**: deny before execution; zero tool-body side effects; denial audited under the
correlation ID; `assert_denied_closed` and `assert_no_side_effect` pass.

## Scenario C — Enforcement error fail-closed (US3 / SC-002 / SC-005)

```bash
pytest tests/component/test_fail_closed.py -q
```

**Expect**: pre-hook or registry fault → deny; tool body never runs; no secret markers in
audit/spans/logs.

## Scenario D — Tool body error still runs post-hooks (US1 edge / FR-015)

```bash
pytest tests/component/test_tool_body_error.py -q
```

**Expect**: post-hooks invoked; audit shows allow-then-failed execution under the same
correlation ID; redaction holds.

## Scenario E — Governance-first order (US4 / SC-006)

```bash
pytest tests/component/test_governance_order.py -q
```

**Expect**: probe order or spans show governance before other; test fails if order is
reversed.

## Scenario F — Harness helper import contract (US5 / FR-012)

```bash
python -c "from tests.harness import (
  assert_denied_closed,
  assert_correlated,
  assert_audit_chain,
  assert_no_secret_values,
)"
```

**Expect**: imports succeed; `tests/harness/README.md` documents the same four names.

## Scenario G — Inner loop still green

```bash
make check
```

**Expect**: exit `0` with unit + component suites included; no live network services
required.

## References

- Pipeline behavior: [contracts/hook-pipeline.md](./contracts/hook-pipeline.md)
- Audit chain: [contracts/audit-sink.md](./contracts/audit-sink.md)
- Helpers: [contracts/harness-helpers.md](./contracts/harness-helpers.md)
- Entities: [data-model.md](./data-model.md)
