# Implementation Plan: Registry isolation — the refusal is observed, not argued

**Branch**: `spec/018-registry-isolation` | **Date**: 2026-07-31 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/018-registry-isolation/spec.md`

## Summary

The constitution's Quality Gates names a blocking row — *"registry isolation (agent-credential
control-plane writes observed denied)"* — that no feature implements and no ADR defers. It
has been unowned since 004, which documented the situation and declined to invent a citation
to satisfy the clause.

The mechanism holds. Probing the running control plane under a real run's authority, every
write to a bounding record was refused. What has never happened is the **observation**: the
guarantee rests on someone having read the configuration and concluded no write was granted,
which is an argument. A configuration change granting the write would pass every check in
this repository today.

Research changed three things about how to build it:

1. **`403 permission denied` is not evidence on its own.** A mount that does not exist is
   refused in identical words — verified. Vault will not distinguish *forbidden* from
   *absent*, correctly, because doing so leaks the tree's shape. **A refusal counts only
   when the same authority can read the path** (R1).
2. **FR-003 was backwards and the spec is corrected.** It required an authority carrying only
   the bound under test; the claim is about the authority a run *actually holds*, all three
   policies of it (R2).
3. **There are more bounding record kinds than the spec named**, one added the same day it
   was written. The set is derived from the deployed policy, not listed in the suite (R4).

Plus the ADR-0047 amendment, in the same change, because FR-010 requires the row that
prompted it to move to in-force with it (R5).

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: None new. The existing conformance harness and the `enclave` /
`host_enclave` markers. A gate that added a dependency would need a named trigger under
Principle VI.

**Storage**: N/A. Every write it attempts is expected to be refused, and any that is not is
removed (FR-004b).

**Testing**: pytest, in `tests/conformance/authority/` — the package that already holds
authority-manufacture rows, so this joins an enumerated directory rather than creating one a
lane must be taught about.

**Target Platform**: The live control plane, reached under a real run's authority.

**Performance Goals**: None. A handful of refused requests.

**Constraints**: **No automated check may widen authority** (FR-008). The demonstration that
the gate can fail is manual, one-time, and recorded. This is the sharpest constraint in the
feature, and it is a safety property rather than a preference.

**Scale/Scope**: Six or more bounding paths, derived rather than listed. One ADR amendment.
No `src/` change expected.

## Constitution Check

*Source of truth: [`.specify/memory/constitution.md`](../../.specify/memory/constitution.md) (v1.3.0).*

| Principle | Verdict | Notes |
| --- | --- | --- |
| I — Build Glue Only | **N/A** | No product knowledge. |
| II — Total Interception | **N/A** | No tool call is made or intercepted. |
| III — Fail-Closed, In-Process Enforcement | **Pass** | No permissive branch: a write that is not refused fails, and a refusal that cannot be attributed fails. |
| IV — Zero Standing Credentials; Authority Per Task | **Pass, and this is the subject** | The row asserts a bound of Principle IV itself — that a run cannot move the limits its authority is manufactured against. Adds no credential; uses the authority a run already holds. |
| V — Sealed Core, Versioned Seams | **Pass** | No core change. |
| VI — Lean by Default | **Pass** | No new operated component, dependency, or lane. |
| VII — Anti-Fragmentation | **Pass** | One suite, one way to run it. The rows join a directory the recipe already enumerates. |
| VIII — Eval-Gated Promotion | **N/A** | Nothing promotes. |
| IX — Evidence Over Claims | **Pass, and this is the feature** | Replacing an argument about configuration with an observed refusal. FR-011 bounds the claim so a green row does not imply more than it asserts. |
| X — The Decision Record Governs | **Pass** | Amends ADR-0047 at PATCH level, naming a state that existed in practice and was unnamed. No row's assertion changes; nothing in force is relaxed. |

**Blocking-row ownership** (Quality Gates): this row becomes blocking and is **executed by an
automated check** — **no named human runner is owed for it.** The one-time demonstration that
the gate can fail is *not* a row: it is a documented act performed by a person, recorded with
its output, and the contract must say so rather than let it read as a gate anyone re-runs.

**Gate result**: **PASS — proceed to Phase 0**

*Re-checked after Phase 1: unchanged. Principle IX is strengthened rather than strained — the
read-200 discriminator exists precisely so the evidence means what it says.*

## Project Structure

### Documentation (this feature)

```text
specs/018-registry-isolation/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── conformance.md   # What the rows assert, and what they do not
├── checklists/
│   └── requirements.md  # From /speckit-specify
└── tasks.md             # /speckit-tasks — NOT created here
```

### Source Code (repository root)

```text
tests/
└── conformance/
    └── authority/                      # EXISTING — already enumerated by the recipe
        ├── bounding_records.py         # NEW — derives the set from the DEPLOYED policy
        └── test_a_run_cannot_move_its_own_bounds.py   # NEW — the rows

docs/adr/
└── 0047-conformance-gate-rows-attach-as-features-land.md   # + PATCH amendment

specs/004-primary-adapter/contracts/conformance-adapter.md  # the row moves to in-force
```

**Structure Decision**: The rows join `tests/conformance/authority/`, which the
`make conformance` recipe already names on its `host_enclave` line. Creating a new directory
would mean teaching a lane about it — the step 010 forgot, 014 nearly repeated, and 017 spent
a whole phase guarding against. Joining an enumerated directory avoids the class entirely.

`bounding_records.py` derives the set from the **deployed** policy rather than from Terraform
source or a literal list. Reading Terraform would reintroduce the argument this feature exists
to replace with evidence; a literal list was already two entries stale on the day the spec
was written (R4).

## Complexity Tracking

> No Constitution Check violations. Table omitted.

One risk is worth naming. **The read-200 discriminator makes the gate depend on the run's
read grant continuing to exist.** If a future change removed `harness-authority-read` from
the run role, every row would fail — correctly, because the refusal could no longer be
attributed, but at first glance reading as though isolation had broken. The failure message
must distinguish *"the write was permitted"* from *"the refusal could not be attributed"*.
FR-004a requires the first; the contract must state the second.
