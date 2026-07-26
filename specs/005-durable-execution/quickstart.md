# Quickstart validation: Durable Execution

**Feature**: `specs/005-durable-execution`
**Purpose**: Prove FR-001–FR-019 end-to-end after `feat/005-durable-execution` lands.
**Not**: an implementation guide with full module bodies (see `tasks.md`).

Contracts: [durability-seam](./contracts/durability-seam.md),
[grant-and-resume](./contracts/grant-and-resume.md),
[conformance-durability](./contracts/conformance-durability.md).
Model: [data-model](./data-model.md).

## Prerequisites

- `main` includes 002 governed core, 003 per-task authority, 004 primary adapter
- Python 3.12+, `uv`, `make`
- **The local enclave.** Unlike 001–004, durability validation is not hermetic. `make dev-up`
  brings up Terraform → Vault → Nomad → the scheduled Postgres, per
  [CONTRIBUTING.md](../../CONTRIBUTING.md) and [`infra/dev-enclave`](../../infra/dev-enclave/)
- No live model provider, no live managed-product API — that part of the determinism bar survives
  unchanged (SC-010)

> Scenarios A, C, E, and F below need the enclave. Unit-level scenarios (B's checkpoint scan, D's
> bounds) run without it. If `make dev-up` has not been run, the durability lane fails loudly
> rather than skipping — a skipped guarantee reads as a passing one.

## Scenario A — Kill and resume (US1)

```bash
make dev-up
pytest tests/component/test_resume.py -q
```

**Expect**: a run disrupted mid-flight resumes from its checkpoint and completes; every
already-completed step shows **exactly one** execution across the whole run; correlation ID and
hash chain join across the disruption boundary (SC-001, SC-008).

## Scenario B — Re-authenticate, never replay (US2)

```bash
pytest tests/unit/test_checkpoint_purity.py -q     # no enclave needed
pytest tests/component/test_resume_authority.py -q # enclave needed
```

**Expect**: no checkpoint written by any provider contains credential, token, or secret material
(SC-003); resume manufactures fresh authority under the surviving grant (SC-002); a credential
captured before the disruption is not honoured after it.

> Under ADR-0048 the resumed run is a new allocation with a new attested identity, so the old
> credential is *unobtainable*. What this scenario actually proves is the negative: no code path
> reintroduces one. Read a failure here as "someone added a way to carry authority across a
> disruption," not as "the substrate leaked."

## Scenario C — Park on expired consent (US3)

```bash
pytest tests/component/test_park_on_expiry.py -q
```

**Expect**: resume under an expired grant reaches `PARKED` with **zero** subsequent steps
(SC-004); the parked run is durable and queryable; renewed consent permits resume. Renewal here
is programmatic — the human surface is Control Groups (ADR-0016), out of scope.

## Scenario D — Re-observe, never re-execute (US4)

```bash
pytest tests/component/test_reobservation.py -q
```

**Expect**: an interrupted non-repeatable step is resolved against **observed external state**, in
both directions — `happened` skips, `did_not_happen` redoes (SC-005) — and the observation is
recorded as the basis of the decision. `cannot_determine` parks; it never resolves to a guess.

## Scenario E — Fencing against double resume (US5)

```bash
pytest tests/component/test_fencing.py -q
```

**Expect**: the superseded instance's tool calls and checkpoint writes are **rejected on identity
comparison** — zero side effects, zero state mutation (SC-006). Single-node only; multi-node
partition is not exercised, and the conformance contract says so.

## Scenario F — Bounds and the full gate (US6, US7)

```bash
pytest tests/unit/test_bounds.py -q     # no enclave needed
make conformance
```

**Expect**: each of the three bounds — duration, step limit, stuck-wait — stops a run that exceeds
it, with the reason recorded (SC-007). `make conformance` executes all **seven** durability rows
as in force, not deferred, and they pass (SC-009). Each row's break fixture demonstrates the row
fails when its guarantee is weakened (FR-014).

## Scenario G — Provider independence (US7)

```bash
pytest tests/conformance/durability -q --provider=memory
pytest tests/conformance/durability -q --provider=postgres
```

**Expect**: identical results. Rows are written against the seam, not an implementation (FR-012).
This is the executable form of ADR-0024's claim that swapping providers changes performance and
never semantics — if a row needs rewriting per provider, the claim is false and the seam is drawn
in the wrong place.

## Full gate

```bash
make check          # lint, types, unit + component
make conformance    # requires the enclave
```

Both green is the completion bar. `make check` alone is not — the durability rows are exactly the
part that cannot run hermetically.
