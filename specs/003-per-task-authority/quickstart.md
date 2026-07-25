# Quickstart validation: Per-Task Authority

**Feature**: `specs/003-per-task-authority`
**Purpose**: Prove FR-001–FR-015 end-to-end after `feat/003-per-task-authority` lands.
**Not**: an implementation guide with full module bodies (see `tasks.md`).

Contracts: [authority-binding](./contracts/authority-binding.md),
[entitlement-mirroring](./contracts/entitlement-mirroring.md),
[task-credential](./contracts/task-credential.md). Model: [data-model](./data-model.md).

## Prerequisites

- `main` includes 002 governed core (hooks, audit, harness helpers)
- Python 3.12+, `uv`, `make`
- No Docker, live IdP, Vault, collector, or model required

## Scenario A — Narrowed authority issued (US1)

```bash
uv sync
pytest tests/component/test_authority_issue.py -q
```

**Expect**:

- `start_governed_run` returns a run with `TaskCredentialRef`
- `assert_scope_narrowed(ref, at_most=user_scope)` passes
- Audit includes `authority_issued` under the run correlation ID
- No secret values in audit/spans

## Scenario B — Amplification refused (US2)

```bash
pytest tests/component/test_authority_refuse.py -q
```

**Expect**: start raises refuse (`authority_refused`); no usable credential; audit
`authority_refused` when sink available; no product side effects.

## Scenario C — In-scope allow / out-of-scope deny (US3)

```bash
pytest tests/component/test_authority_invoke.py -q
```

**Expect**: in-scope tool allow path still joins 002 audit/spans; out-of-scope deny with
`authority_insufficient` before tool body; `assert_denied_closed` +
`assert_no_side_effect`.

## Scenario D — Entitlement mirroring (US4)

```bash
pytest tests/component/test_entitlement_mirroring.py -q
```

**Expect**:

- Broker/federate tool with action ∈ entitlements → allow; product fake records wield
- Missing/empty entitlements → `mirroring_denied`; zero wields
- `mirroring_decision` audited; secrets absent

## Scenario E — Expiry (US5)

```bash
pytest tests/component/test_authority_expiry.py -q
```

**Expect**: after `frozen_clock.advance` past TTL, invoke denies `authority_expired`;
no side effect; new run required (no auto-refresh).

## Scenario F — Identity / exchange fail-closed

```bash
pytest tests/component/test_authority_fail_closed.py -q
```

**Expect**: fabric unavailable or exchange failure → refuse start or deny invoke; never
allow; four-way assertions hold.

## Scenario G — Harness import contract

```bash
python -c "from tests.harness import (
  fake_identity_fabric,
  fake_product_api,
  frozen_clock,
  assert_scope_narrowed,
)"
```

**Expect**: imports succeed; `tests/harness/README.md` documents the same names.

## Scenario H — Inner loop still green

```bash
make check
```

**Expect**: lint, typecheck, and unit/component suites pass including 002 regressions.

## Mapping

| Spec | Quickstart |
| --- | --- |
| US1 / FR-001–003 (issue + allow) | A, C (allow half) |
| US2 / FR-002–003 (refuse + insufficient) | B, C (deny half) |
| US3 / FR-004–006 (mirroring) | D |
| US4 / FR-007, FR-015 (fail-closed) | F |
| US5 / FR-008, FR-012 (expiry + harness) | E, G |
| FR-012–013 harness imports | G |
| Inner loop / 002 regressions | H |
