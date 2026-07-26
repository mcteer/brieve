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
| Order break | `tests/conformance/adapter/test_governance_order_break.py` — the ordering assertion raises under a deliberately inverted fixture; the test itself passes, proving the detector fires | SC-003 |
| Fail closed | `tests/conformance/adapter/test_fail_closed.py` — injected fault → deny, zero executions | FR-008, SC-002/SC-003 |
| Invoke entry | Adapter tool path reaches `invoke_tool` (probe/counter), not a native bypass | FR-003 |

## Deferred (out of 004 conformance slice)

These constitution Quality Gate rows **attach when those features land**
([ADR-0047](../../../docs/adr/0047-conformance-gate-rows-attach-as-features-land.md),
Accepted; constitution v1.0.1 — this section is the per-feature record that ADR makes
authoritative) — 004 must not add silent-green stubs for them:

> **No longer deferred: the durability matrix.** All seven rows — kill/resume,
> re-observe-never-re-execute, re-auth-never-replay, double-resume fencing, grant-expiry
> parking, duplicate-side-effect rejection, drain-across-upgrade — are **in force** as of
> `specs/005-durable-execution`, and run under `make conformance` against both the
> in-memory double and Postgres. See
> [conformance-durability.md](../../005-durable-execution/contracts/conformance-durability.md).
>
> Updated here by the feature that put them in force, per ADR-0047: a deferral list that
> goes stale reads as a gap nobody noticed.

Each remaining row names the ADR that defers it, as constitution v1.0.1 requires; a skip
marker in the suite MUST carry the same reference:

- Second (LangGraph) adapter cases —
  [ADR-0017](../../../docs/adr/0017-primary-adapter-selection.md) (second adapter is
  demand-driven). Absent, or a single explicit skip citing ADR-0017 — never a silent green
- Four-transport surface parity —
  [ADR-0033](../../../docs/adr/0033-four-transports-one-authorization-core.md); no
  northbound surface has shipped, so there is nothing to assert parity across
- Deferred-disclosure tool-call parity —
  [ADR-0040](../../../docs/adr/0040-deferred-tool-disclosure.md) productization
- Registry isolation control-plane write denials beyond what 002 already covers — the rule
  originates in [ADR-0025](../../../docs/adr/0025-enclave-is-the-default-topology.md)
  ("agents are structurally excluded from managing their own platform") and Principle IV.
  **No ADR defers this row specifically** — see Notes
- Eval gates (packs/models/policies) — Principle VIII;
  [ADR-0004](../../../docs/adr/0004-adopt-skills-as-governed-supply-chain.md) (packs),
  [ADR-0022](../../../docs/adr/0022-qualified-model-matrix.md) and
  [ADR-0039](../../../docs/adr/0039-per-role-model-bindings.md) (models). 004 promotes no
  pack, model, or policy, so the gate does not attach

## Invariants

1. Conformance failures are merge-blocking for adapter changes.
2. Skipping the secondary adapter MUST NOT skip or weaken primary-adapter required cases.
3. Conformance tests are deterministic — stub/scripted models only; no live providers.
4. Every deferred row above names the ADR deferring it, and any skip marker in the suite
   carries that same reference (constitution v1.0.1, ADR-0047).

## Notes

**Registry isolation has no deferring ADR.** Constitution v1.0.1 requires each deferred
row to be "absent or a single explicit skip carrying the ADR that defers it," which
assumes every row traces to one. The registry-isolation row does not: it derives from
Principle IV and ADR-0025's structural-exclusion rule, neither of which defers it — 004
simply has no control-plane write surface to test. The row is therefore recorded as
not-yet-attached rather than deferred-by-decision.

This is a wording gap in ADR-0047, not a gap in 004. If a second row turns out to lack a
deferring ADR, the fix is a PATCH to ADR-0047 distinguishing *deferred by decision* from
*not yet applicable*, rather than inventing citations to satisfy the clause.

## Related

- [governance-capability.md](./governance-capability.md)
- [quickstart.md](../quickstart.md)
