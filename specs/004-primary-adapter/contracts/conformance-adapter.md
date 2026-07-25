# Contract: Primary-adapter conformance lane

**Feature**: `specs/004-primary-adapter`
**Status**: Planned
**Depends on**: Constitution Quality Gates; ADR-0001; ADR-0019

## Purpose

Define what `make conformance` must execute once the primary adapter exists, and what
is explicitly deferred.

## Command

```text
make conformance
```

MUST run the primary-adapter conformance tests (via `uv run pytest tests/conformance`
or equivalent) with the `adapters` extra available, and exit 0 on a clean tree.

The prior exit-2 stub is retired for this lane when 004 lands. Other reserved commands
(`test-full`, `dev-up`) may remain stubs.

## Required cases (004 slice)

| Case | Asserts | Spec |
| --- | --- | --- |
| Governance order | `tests/conformance/adapter/test_governance_order.py` — governance before co-resident non-governance | FR-004, SC-003 |
| Order break | `tests/conformance/adapter/test_governance_order_break.py` — inverted order fails | SC-003 |
| Fail closed | `tests/conformance/adapter/test_fail_closed.py` — injected fault → deny, zero executions | FR-008, SC-002/SC-003 |
| Invoke entry | Adapter tool path reaches `invoke_tool` (probe/counter), not a native bypass | FR-003 |

## Deferred (out of 004 conformance slice)

These constitution Quality Gate rows **attach when those features land** — 004 must not
add silent-green stubs for them:

- Second (LangGraph) adapter cases — absent or single explicit skip, never a silent green
- Full ADR-0024 durability scenario matrix
- Four-transport surface parity (no northbound surfaces yet)
- Deferred-disclosure tool-call parity (ADR-0040 productization)
- Registry isolation control-plane write denials beyond what 002 already covers
- Eval gates (packs/models/policies)

## Invariants

1. Conformance failures are merge-blocking for adapter changes.
2. Skipping the secondary adapter MUST NOT skip or weaken primary-adapter required cases.
3. Conformance tests are deterministic — stub/scripted models only; no live providers.

## Related

- [governance-capability.md](./governance-capability.md)
- [quickstart.md](../quickstart.md)
