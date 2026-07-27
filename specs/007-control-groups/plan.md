# Implementation Plan: Control Groups

**Branch**: `spec/007-control-groups` | **Date**: 2026-07-26 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/007-control-groups/spec.md`

## Summary

Configure the control-plane Vault's **own** Control Groups to gate authority changes, and
add the seam through which the harness observes and records them. Ceiling changes,
definition changes, registration, manual control-plane writes, break-glass, and
reactivation require quorum. Revocation stays unilateral and immediate.

The shape of this feature is unusual and worth stating up front: **most of it is
configuration and evidence, not mechanism.** Vault Enterprise ships Control Groups, and
the licence in use provides them — confirmed against the running enclave, not read from
documentation. Building an approval engine beside the trust fabric would violate
Principle I and would put the authority record somewhere other than where ADR-0015 says
it lives. So the work is: express the policy in Terraform, wire the paths that must be
gated, and make the harness able to *see* and *record* what the trust fabric decided.

## Technical Context

**Language/Version**: HCL (Terraform ≥ 1.9) for policy; Python 3.12+ for the observation
seam. `src/core` stays free of agent-framework imports

**Primary Dependencies**: Existing — `hashicorp/vault` provider, Vault Enterprise
2.0.3+ent (Control Groups and Sentinel are licensed features; both confirmed present).
**No new library.** If this feature needs a new dependency, something has gone wrong with
its premise

**Storage**: The authority record lives in Vault. The harness records its *observations*
of authority changes in the existing audit chain — it does not keep a second copy of the
decision, which would be a second source of truth about who approved what

**Testing**: `pytest` unit + component against the real control-plane Vault. Control
Groups cannot be meaningfully faked: a fake that always approves proves nothing, and one
that never approves proves only that the caller handles denial. The enclave is the test
bar, as it is for durability

**Target Platform**: The local enclave for development; the customer's control-plane Vault
in production, where **their** administrator owns the policy

**Project Type**: Infrastructure and evidence. A small core addition for the observation
seam; the gate itself is Vault's

**Performance Goals**: N/A. An authority change waiting on humans is measured in hours by
design

**Constraints**: Nothing in this feature may pause, interrupt, or block a run (FR-012,
SC-009). Fail-closed when the approval mechanism is unreachable (FR-010). The requester
cannot satisfy their own quorum (FR-008)

**Scale/Scope**: One enclave, one tenant. Quorum sizes are small — two or three approvers
in a first deployment — and configurable per class of change

### The premise this plan rests on

**Vault Control Groups exist and are licensed.** Verified against the running enclave:

```text
Control Groups licensed: True
```

If that were false this plan would be wrong end to end, not merely inconvenient — the
whole design is "configure the trust fabric's mechanism", and the alternative is building
an approval engine, which FR-014 forbids. Checked rather than assumed for that reason.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*
*Source of truth: [`.specify/memory/constitution.md`](../../.specify/memory/constitution.md)
— **checked against v1.1.0**; re-check if the version advances.*

| Principle | Verdict | Notes |
| --- | --- | --- |
| I — Build Glue Only | **Pass, emphatically** | The quorum mechanism is Vault's. This feature configures it and observes it. Building an approval engine is explicitly forbidden by FR-014 |
| II — Total Interception; One Governed Tool Layer | Pass | No tool path changes. Control Groups gate what an agent may *become*; hooks gate what it *does* |
| III — Fail-Closed, In-Process Enforcement | Pass | An unreachable approval mechanism blocks the change (FR-010). No timeout grants by default (FR-009) |
| IV — Zero Standing Credentials; Authority Per Task | Pass | This governs the *ceilings* per-task authority is drawn from. Narrowing applies to authority manufactured after the change; nothing reaches into a running step (FR-013) |
| V — Sealed Core, Versioned Seams | Pass | One small core addition — the observation seam. No existing seam changes shape |
| VI — Lean by Default | Pass | Zero new dependencies and zero new operated components. A licensed capability of a component already in the baseline |
| VII — Anti-Fragmentation | Pass | One approval mechanism, the trust fabric's. FR-014 is this principle written as a requirement |
| VIII — Eval-Gated Promotion | N/A | No packs, prompts, models, or policies promoted |
| IX — Evidence Over Claims | **Pass, and load-bearing** | An authority change is the highest-consequence write in the system. Request, each approval or denial with its identity, and disposition must all be reconstructable (FR-011) |
| X — The Decision Record Governs | Pass | Implements ADR-0016. Binds ADR-0015 and ADR-0048. Cites ADR-0049 as **Proposed** — which is why nothing here is run-time, and why 004's approval hook is deliberately untouched |

**Gate result**: PASS — proceed to Phase 0

### Post-design Constitution Check

Re-checked after Phase 1: still **PASS**. Three notes for review:

- **Principle VI is the strongest it has been.** No new dependency, no new component, no new
  mechanism. If a later pass finds this feature growing an approval engine, that is the
  signal the premise broke — not an implementation detail.
- **Principle IX is where the real work is.** Vault decides; the harness must be able to
  show what was decided, by whom, and when, joined to the definition it changed. The seam
  exists for evidence, not for control.
- **Principle III has an edge worth naming.** "Fail closed when the approval mechanism is
  unreachable" is easy to state and easy to get backwards — an unreachable Vault must block
  authority *changes*, while agent runs already holding authority continue. Failing closed
  on the wrong thing here would halt the platform during a Vault blip.

## Project Structure

### Documentation (this feature)

```text
specs/007-control-groups/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── gated-paths.md
│   ├── quorum-policy.md
│   └── evidence.md
├── checklists/requirements.md
├── spec.md
└── tasks.md             # /speckit-tasks (not this command)
```

### Source (repository root)

```text
infra/modules/trust-fabric/
├── control-groups.tf        # NEW — Sentinel policies, controlled paths, quorum config
├── policies.tf              # gated paths reference the control group
└── variables.tf             # quorum policy inputs, owned by the customer's Vault admin

src/core/authority/
├── changes.py               # NEW — observe and record authority-change events
└── errors.py                # a distinct error for "blocked pending approval"

tests/
├── component/test_authority_change_quorum.py
├── component/test_revocation_asymmetry.py
└── unit/test_no_run_interrupt.py     # the negative requirement, asserted
                                      # no conformance lane — this feature adds no
                                      # blocking row to the constitution's list
```

**Structure Decision**: the gate lives in `infra/modules/trust-fabric/`, beside the
policies and roles it governs, because it *is* trust configuration — not a separate
subsystem. The core addition is deliberately small and named for what it does: observe
changes, not make them.

`tests/unit/test_no_run_interrupt.py` exists because FR-012 is a negative requirement, and
negative requirements are the ones that quietly stop being true. A feature about humans
authorizing is exactly where a run-time interrupt would grow back.

## Complexity Tracking

> No Constitution Check violations. Table intentionally empty.
