# Implementation Plan: Per-Task Authority

**Branch**: `spec/003-per-task-authority` | **Date**: 2026-07-25 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/003-per-task-authority/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Extend the 002 governed core with per-run, short-lived task authority: at run start,
manufacture effective authority as user ∩ agent ceiling ∩ task scope ∩ policy (refuse
amplification); bind an opaque, expiring task-credential *reference* on the run (never
persist secret values); enforce expiry and authority bounds on every `invoke_tool` via
governance-first hooks; apply entitlement mirroring for product-tagged tools, with a
mandatory pre-wield check on brokered shared-grain fakes; ship `fake_identity_fabric`,
`fake_product_api`, `frozen_clock`, and `assert_scope_narrowed` under `tests.harness`.
No production IdP/Vault clients, no standing managed-product credentials, no adapters or
northbound surfaces.

## Technical Context

**Language/Version**: Python 3.12+ (existing floor); typed; Pydantic models at public
authority boundaries

**Primary Dependencies**: Existing runtime (`pydantic`, `opentelemetry-api`). No new
runtime packages for 003 — TTL and opaque references use stdlib (`datetime`,
`secrets` for per-run salt and credential reference ids). Dev/test unchanged
(`pytest`, `opentelemetry-sdk`). No agent frameworks, no Vault/OIDC client libraries in
core for this feature.

**Storage**: No durable credential store. Task credential *values* are never written to
audit, run state, or checkpoint-shaped structures — only references, hashes (per-run
salted), reason codes, and metadata. Audit continues via 002 `AuditSink`.

**Testing**: `pytest` unit + component; `fake_identity_fabric`, `fake_product_api`,
`frozen_clock`, `scripted_agent`, `capture_audit`; helpers including
`assert_scope_narrowed`, `assert_denied_closed`, `assert_no_secret_values`,
`assert_correlated`, `assert_audit_chain`, `assert_no_side_effect`. No live IdP, Vault,
models, or product APIs.

**Target Platform**: In-process library on contributor machines and CI; hermetic suite

**Project Type**: Sealed-core library extension (`src/core/authority/…`) + harness public
API; integrates with existing `start_governed_run` / `invoke_tool` / hook engine

**Performance Goals**: N/A — no separate latency/throughput SLO for 003. Authority checks
stay on the existing `invoke_tool` hot path; success criterion is `make check` green,
not a measured budget.

**Constraints**: Fail closed on identity/exchange/ceiling/entitlement/expiry errors
(ADR-0006); scopes only narrow (ADR-0026/0044); federate-before-broker in the model
(ADR-0044); no standing product credentials in tree (Principle IV); evidential-gap on
un-auditable authority decisions (002 contract); sealed-core + attestation-relevant →
security-maintainer review on `feat/003`; lean deps (Principle VI) — zero new runtime
packages unless a later review forces otherwise

**Scale/Scope**: Single requesting user → single agent run; fakes only; Control Group
mutations out of scope; durability/resume out of scope except “no credentials in state”

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*
*Source of truth: [`.specify/memory/constitution.md`](../../.specify/memory/constitution.md).*
*A failing gate stops planning — redesign or withdraw the spec; do not proceed to research.*

| Principle | Verdict | Notes |
| --- | --- | --- |
| I — Build Glue Only | Pass | Authority logic in framework-agnostic core; IdP/Vault are fakes behind protocols — no gateway product |
| II — Total Interception; One Governed Tool Layer | Pass | Authority and mirroring enforced inside the existing hooked `invoke_tool` path; no bypass API |
| III — Fail-Closed, In-Process Enforcement | Pass | Identity/exchange/entitlement/expiry errors deny or refuse start; never allow |
| IV — Zero Standing Credentials; Authority Per Task | Pass | Short-lived per-run authority; no standing managed-product credentials; broker management token not introduced |
| V — Sealed Core, Versioned Seams | Pass | Touches identity/authority + hook integration + harness seam; approved spec; security-maintainer on feat PR |
| VI — Lean by Default | Pass | No new runtime deps; no operated IdP/Vault in 003 |
| VII — Anti-Fragmentation | Pass | One authority model for all later substrates |
| VIII — Eval-Gated Promotion; Pinned vs Fresh | N/A | No packs/models/policies |
| IX — Evidence Over Claims | Pass | Authority/mirroring/expiry decisions audited under correlation ID; secrets never in evidence |
| X — The Decision Record Governs | Pass | Binds ADR-0015, 0026, 0044, 0006; no contradiction with Accepted ADRs |

**Gate result**: PASS — proceed to Phase 0

### Post-design Constitution Check

Re-checked after Phase 1 artifacts: still **PASS**. Contracts pin intersection algebra,
credential reference semantics, brokered pre-check, federate mode without standing
secrets, harness names, and per-run salted hashing for secret-class material; structure
keeps fakes in `tests/harness` and sealed manufacture/enforcement in `src/core`.

## Project Structure

### Documentation (this feature)

```text
specs/003-per-task-authority/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── authority-binding.md
│   ├── entitlement-mirroring.md
│   └── task-credential.md
├── checklists/
│   └── requirements.md
├── spec.md
└── tasks.md             # /speckit-tasks (not this command)
```

### Source Code (repository root)

```text
src/core/
├── authority/
│   ├── __init__.py
│   ├── types.py              # AuthorityScope, TaskCredentialRef
│   ├── fabric.py             # IdentityFabric protocol (fakes implement)
│   ├── hashing.py            # HMAC-SHA256(run_salt, material) hex digests
│   ├── intersection.py       # user ∩ ceiling ∩ task_scope ∩ policy (pure)
│   ├── manufacture.py        # issue ref at run start or refuse
│   ├── clock.py              # Clock protocol; system clock default
│   └── errors.py             # AuthorityRefuseError, AuthorityExpiredError, …
├── hooks/
│   ├── authority.py          # governance pre: expiry + effective-scope gate
│   └── mirroring.py          # pre-tool entitlement mirroring (brokered / federated)
├── run.py                    # extend start_governed_run: identity + authority bind
└── …                         # existing 002 modules

tests/harness/
├── fake_identity_fabric.py   # user, ceiling, exchange, entitlements; fault injection
├── fake_product_api.py       # federate | broker modes; call counters
├── frozen_clock.py           # deterministic time; advance()
├── assertions.py             # add assert_scope_narrowed
└── README.md                 # document new exports

tests/unit/                   # intersection, refuse amplify, expiry, salt hashing
tests/component/              # US1–US5 scenarios through start_governed_run + invoke_tool
```

**Structure Decision**: Keep authority manufacture and pure intersection in `src/core/authority`;
enforce via governance-ordered hooks already required by 002; expose only protocols +
fakes at the harness seam. No Option-2/3 web split.

## Complexity Tracking

> No Constitution Check violations. Table intentionally empty.
