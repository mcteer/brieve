# Quickstart validation: Control Groups

**Feature**: `specs/007-control-groups`
**Purpose**: Prove FR-001–FR-018 after `feat/007-control-groups` lands.
**Not**: an implementation guide (see `tasks.md`).

Contracts: [gated-paths](./contracts/gated-paths.md),
[quorum-policy](./contracts/quorum-policy.md), [evidence](./contracts/evidence.md).
Model: [data-model](./data-model.md).

## Prerequisites

- `make dev-up` — the enclave, with the control-plane Vault unsealed
- **No fake.** There is no faked Control Group anywhere in these scenarios: a fake that
  always approves proves the caller can proceed, one that never approves proves it handles
  denial, and neither proves the gate holds

## Scenario A — Widening a ceiling needs more than one person (US1) 🎯

```bash
pytest tests/component/test_authority_change_quorum.py -q
```

**Expect**: the change does not take effect below quorum; the agent's authority is
unchanged; it takes effect when quorum is reached, with approving identities recorded
(SC-001).

## Scenario B — A requester cannot approve their own request (FR-008)

**Expect**: the requester's own assent does not count toward quorum. Otherwise the
requirement is one person with two hats (SC-003).

## Scenario C — Revocation is unilateral; restoration is not (US2, US3)

```bash
pytest tests/component/test_revocation_asymmetry.py -q
```

**Expect**: one authorized identity revokes, alone, immediately, with zero approvals
(SC-004). The revoked agent cannot obtain new authority. Restoration by one person does
**not** take effect; with quorum it does (SC-005).

**The asymmetry is the point.** A gate that makes revoking as slow as granting is one
people route around in an incident.

## Scenario D — Nothing pauses a run (FR-012) 🎯 the negative requirement

```bash
pytest tests/unit/test_no_run_interrupt.py -q
```

**Expect**: zero runs paused, interrupted, or blocked by anything in this feature
(SC-009). Narrowing a ceiling applies to authority manufactured *after* the change and
reaches into zero running steps (SC-010).

This scenario exists because negative requirements are the ones that quietly stop being
true. Nobody notices the day a pause is added; a failing test does.

## Scenario E — Operating within an approved definition is not gated (US5)

**Expect**: scheduling, restarting, and scaling instances of an approved definition request
approval in zero cases (SC-006). Gating routine operations would train people to approve
without reading, which destroys the gate that matters.

## Scenario F — Fail closed, on the right thing (FR-010)

**Expect**: with the approval mechanism unreachable, authority changes succeed in zero
cases (SC-007) — **and agent runs already holding authority continue.** Failing closed on
the wrong thing here would halt the platform during a Vault blip.

## Scenario G — A pending request expires without granting (FR-017)

**Expect**: a request that reaches its TTL without quorum results in no change (SC-012).
Expiry is the safe direction: the cost is a change someone must propose again, versus an
approval collected months after the context that justified it.

## Scenario H — Evidence is reconstructable (FR-011)

**Expect**: for every authority change, an investigator retrieves the request, each
approval or denial with its identity, and the disposition — joined by correlation ID
(SC-008). No credential material, no policy content, and no mirror of Vault's approval
state.

## Scenario I — The gate cannot be lowered by whoever it constrains (FR-015)

**Expect**: changing the quorum policy is itself gated. After provisioning completes and
the bootstrap credential is revoked, zero authority changes are possible outside the
quorum mechanism (SC-011).

## Full gate

```bash
make check
make conformance    # requires the enclave
```

Both green is the completion bar. Per constitution v1.1.0, the party responsible for
running the enclave-dependent rows before merge is named in this feature's conformance
contract.
