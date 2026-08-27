# Implementation Plan: Adopted skills reach the phase that needs them

**Branch**: `spec/051-phase-skill-binding` | **Date**: 2026-08-26 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/051-phase-skill-binding/spec.md`

## Summary

The Terraform pack pins two HashiCorp skills by digest and delivers neither to any model.
All five of its phase instructions claim them as practice. This feature makes the claim
true: `[[skills]]` gains a `phases` array, `core/packs/agents.py` assembles `AGENTS.md` plus
the skills bound to that phase into the bytes a phase's model receives, and every failure
mode — missing, mismatched, unknown phase, over budget — stops the run with its own reason
code. `terraform-style-guide` and `terraform-style-guide-security` bind to `plan`, `write`
and `judge`. Research and Propose stop claiming what they will not receive.

Two things the record must stop overstating come with it. `content_pins` learns to say
*bound* rather than implying *governed*, and per-phase delivery starts being written at all —
`run.agent_content_pins` has been in-memory-only since 049 ([research R11](research.md)).
And because the vendored guide recommends `terraform fmt` and `terraform validate`, which no
registry tool offers, the manifest declares those as unsatisfiable recommendations and the pull request states them,
scoped accurately: the authoring agent could not run them **on the branch it is proposing**
([research R6](research.md) — the eval lane does run `terraform validate`, and an
unqualified claim otherwise would be false).

Research turned up two things the spec did not anticipate, both carried below:
the phase files have already hand-copied most of the skill ([R7](research.md)), which
constrains what SC-002 can honestly measure; and the skill and the Write instruction
**contradict each other** on `required_version` ([R8](research.md)), which this feature is
about to place in one context.

## Technical Context

**Language/Version**: Python 3.13, fully typed. No TypeScript — the portal composes no
instruction ([test_portal_does_not_compose_agents.py](../../tests/conformance/phase_agents/test_portal_does_not_compose_agents.py)
already asserts this and stays green).

**Primary Dependencies**: none added. `tomllib` (stdlib) parses the new manifest fields;
`hashlib` already verifies digests.

**Storage**: none. Skills are files already on disk under `packs/<name>/skills/`, pinned by
digest. No runtime fetch is introduced (ADR-0030 — executed content is pinned).

**Testing**: `tests/conformance/phase_agents/` (new rows for assembly, order, fail-closed,
budget, prose/binding divergence), `tests/conformance/packs/` (manifest refusals),
`tests/component/` (`content_pins` shape, per-phase delivery record, PR body section),
`tests/evals_live/` (SC-002 — the new `variable_has_validation` property and its corpus
task). Suites re-run: `phase_agents` and `build_agents`, over **assembled** content
([R9](research.md)).

**Target Platform**: unchanged — enclave allocation; identical in connected, restricted and
air-gapped profiles, because nothing is fetched.

**Project Type**: existing single project. Core + pack content + one surface recording site.

**Performance Goals**: none binding. Delivery adds two file reads and two SHA-256 hashes per
phase bind (≈12 KB hashed), against a phase that is about to make a model call.

**Constraints**: skill bytes are never edited or filtered (ADR-0004, FR-015); no platform
source may name a skill or a phase binding (FR-002, SC-004); delivery order deterministic
from the manifest (FR-006); assembled instruction ≤ `INSTRUCTION_BUDGET_BYTES` = 256 KiB,
refuse never truncate (FR-009, [R4](research.md)); a phase bound to no skills is
byte-identical to today (FR-011); binding and re-qualification promote together (FR-013),
and no runtime state exists for a binding not in force (FR-013a).

**Scale/Scope**: 2 packs, 5 phases, 3 skills (2 Terraform, 1 Vault). Terraform binds 2
skills × 3 phases; Vault binds none and is the live fixture for "adopted but inert".

## Constitution Check

*Source of truth: [`.specify/memory/constitution.md`](../../.specify/memory/constitution.md)
v1.6.0 (Last Amended 2026-08-05) — checked against that version.*

| Principle | Verdict | Notes |
| --- | --- | --- |
| I — Build Glue Only | Pass | Adopted content delivered byte-exact; the platform adds assembly and verification, which nothing upstream provides. Assembly sits in core, not a surface ([R1](research.md)) |
| II — Total Interception; One Governed Tool Layer | Pass | No tool, no transport, no egress class added. FR-014 makes the registry's bound explicit *in the instruction* — adopted practice may not widen what a model may call |
| III — Fail-Closed, In-Process Enforcement | Pass | Every new failure mode stops the phase through the existing `_bind_phase_or_fail` path; nine distinct reason codes (contract §3), none falling through to delivery (FR-004, SC-005) |
| IV — Zero Standing Credentials; Authority Per Task | N/A | No identity, credential, ceiling, or scope surface is touched |
| V — Sealed Core, Versioned Seams | Pass **with obligation** | Touches `core/packs/manifest.py` (registry schema) and the `RUN_START` `content_pins` payload (**audit schema**). Both are sealed core: this feature has an approved spec, and the implementation PR **must request security-maintainer review**. Recorded in [contracts/pack-skill-binding.md](contracts/pack-skill-binding.md) as a stability commitment, with the `content_pins` key grammar pinned rather than left to implementation |
| VI — Lean by Default | Pass | No operated component, no dependency, no new module. Two existing files gain fields; one gains a section |
| VII — Anti-Fragmentation | Pass | One mechanism, identical on every substrate; nothing is fetched, so restricted and air-gapped behave identically. [R11](research.md) rejects a third pin map on exactly this ground |
| VIII — Eval-Gated Promotion; Pinned vs Fresh | Pass | The principle this feature serves. Skills stay pinned and are now actually executed. FR-013 ties binding to re-qualification; [R9](research.md) requires the scorers to score **assembled** bytes, or the gate greens without asserting anything (ADR-0047) |
| IX — Evidence Over Claims | Pass | The feature's second half is removing an overstatement. `content_pins` stops implying every pinned skill governed the run; the PR text derives from the manifest, never from a model's account (FR-018); [R6](research.md) narrows the unsatisfiable claim to what is actually true |
| X — The Decision Record Governs | Pass | ADR-0004's consumption half; ADR-0030 governs pinning; ADR-0003 keeps the binding in pack content; ADR-0038 hands unperformable practice to the reviewer. No Accepted ADR is contradicted and none is needed — the traceability table was reconciled against the record before this plan ran |

**Gate result**: **PASS — proceed to Phase 0.**

### Carried findings — resolved in `spec.md` by the `/speckit-analyze` remediation

All three are now spec sentences. Recorded here because the plan was written before them and
its reasoning still rests on them.

1. **FR-007** ([R3](research.md)) named a refusal that cannot exist under FR-002's shape.
   Rewritten to the three refusals that are reachable: unknown phase, phase with no
   `[[agents]]` pin, duplicate skill name.
2. **FR-014a** added ([R8](research.md)). The skill's `required_version = ">= 1.14"` example
   contradicts the Write instruction's "`>=` is not a pin", and the eval detector agrees with
   the instruction. Without a content-precedence rule the likeliest observable outcome of
   this feature is a *regression* on `required_version`; row E4 guards it.
3. **FR-019 / SC-010** added. The spec named the "upstream bump adds an undeclared
   unsatisfiable step" hazard with nothing behind it. Because the pull request derives from
   the declaration and never from the skill's bytes, a declaration that lags the content
   tells a reviewer that less work remains than actually does. Closed with
   `unsatisfiable_reviewed_at` on every `[[skills]]` entry, checked at load — which is where
   the spec said the hazard was invisible.

### Corrections applied after design

| Finding | Correction |
| --- | --- |
| Both skills were to declare `terraform fmt` / `terraform validate` | `SECURITY.md` contains neither string, no shell block, no tool invocation. Only `terraform-style-guide` declares them; the other would have printed each bullet twice and misattributed a recommendation |
| The scorers were to assemble via `load_phase_agents` | Deadlock: editing a phase file makes its pin stale, `load_phase_agents` refuses `digest_mismatch`, so the suites cannot pass, so promotion cannot run. Assembly is now the pure function `assemble_instruction`, called with bytes rather than re-deriving them |
| Contract §5 claimed a pre-change run resumed post-change "must not silently match" | `resume_run` never reads `content_pins` — zero occurrences. No comparison exists. §5 now states the true position rather than a safety property the code does not implement |

## Project Structure

### Documentation (this feature)

```text
specs/051-phase-skill-binding/
├── plan.md              # This file
├── research.md          # Phase 0 — R1–R12
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   ├── pack-skill-binding.md              # manifest schema, assembly, refusals, pin grammar
│   └── conformance-phase-skill-binding.md # gate rows, hermetic and named-runner
├── checklists/
│   └── requirements.md  # existing, from /speckit-specify
└── tasks.md             # Phase 2 — /speckit-tasks, NOT created here
```

### Source Code (repository root)

```text
src/core/packs/
├── manifest.py       # SkillPin gains `phases` + `unsatisfiable`; new UnsatisfiableRecommendation
├── loader.py         # parse both new fields; validate_manifest gains binding refusals
├── agents.py         # ASSEMBLY LIVES HERE — PhaseAgents gains `skills`; digest-verify at delivery
└── registration.py   # load_packs gains the FR-017 stale-declaration check (whole set, order-free)

src/core/evals/
└── phase_agents_corpus.py   # scorers score the ASSEMBLED instruction, not AGENTS.md alone

src/core/authoring/
└── proposal.py       # Proposal gains `unsatisfiable_recommendations`; + render section

src/surfaces/
├── toolset.py        # content_pins key grammar: @<phases> or @unbound
└── dispatch/
    ├── phase_agents.py   # record delivered skills per phase; no assembly
    └── entrypoint.py     # write the per-phase pins into the checkpoint payload; pass
                          # unsatisfiable recommendations into compose()

packs/terraform/
├── pack.toml             # phases = [...] on both skills; [[skills.unsatisfiable]] tables
└── agents/               # all five files re-promoted: FR-012a prose, FR-014 precedence
    └── {research,plan,write,judge,propose}/{AGENTS.md,PROVENANCE.md}

evals/
└── authoring/corpus.toml       # SC-002 task + the case the detector must fail

tests/
├── conformance/phase_agents/   # assembly, order, fail-closed, budget, prose-vs-binding
├── conformance/packs/          # manifest refusals, FR-017 staleness
├── component/                  # content_pins shape, delivery record, PR section
└── evals_live/                 # SC-002: variable_has_validation property + corpus task
```

**Structure Decision**: existing single-project layout, unchanged. The feature adds no
module. Assembly lands in `src/core/packs/agents.py` because FR-003's verify-at-delivery is
already implemented there for `AGENTS.md` and the eval lane reaches phase content through the
same function — two assembly implementations would let the suites score bytes production
never sends ([R1](research.md), [R9](research.md)). `packs/terraform/pack.toml` is the only
place a skill name meets a phase name; no file under `src/` names either (SC-004).

## Implementation order

Derived from the dependency the spec makes explicit: US2 must not ship after US1, or the
first correct runs are recorded by a scheme that cannot distinguish them from the incorrect
ones. `/speckit-tasks` orders within these.

| # | Slice | Delivers | Why here |
| --- | --- | --- | --- |
| 1 | Manifest schema + refusals | FR-002, FR-007, FR-008, FR-015, FR-017 | Nothing can bind until a binding can be declared and a bad one refused |
| 2 | Record: per-phase pins written; `content_pins` grammar | FR-005, US2 | Must precede delivery. Also closes the 049 gap where per-phase pins were never written at all ([R11](research.md)) |
| 3 | Assembly + delivery + budget | FR-001, FR-003, FR-004, FR-006, FR-009, FR-011, US1 | The feature |
| 4 | Pack content: bindings, FR-012a prose, FR-014 precedence | FR-010, FR-012, FR-012a, FR-014 | Needs 1 and 3 to exist; changes digests, so it forces 5 |
| 5 | Re-qualification over assembled content | FR-013, FR-013a, SC-007 | All-five-or-none promotion; the scorers must read assembled bytes first ([R9](research.md)) |
| 6 | Unsatisfiable recommendations in the pull request | FR-016, FR-018, US4 | Needs 1's declarations and 4's bindings |
| 7 | SC-002 measurement | SC-002 | Needs everything; the eval lane runs last |

## Post-Design Constitution Re-check

*Re-run against v1.6.0 after Phase 1. Nothing in the design moved a verdict; two are
strengthened by what the design settled.*

| Principle | Verdict | What Phase 1 changed |
| --- | --- | --- |
| I — Build Glue Only | Pass | Contract §2.5 fixes assembly at one implementation in core. No new module; `bind_phase_agents` stays 25 lines of resolution and recording |
| II — Total Interception | Pass | Contract §7.2 rule 1 puts the registry bound in the instruction itself. No tool, transport, or egress class added; skills are read from disk, never fetched |
| III — Fail-Closed | Pass | Eight reason codes in contract §3, each distinct, all travelling `_bind_phase_or_fail`. §2.4 places the budget check before return so no partial instruction can escape |
| IV — Zero Standing Credentials | N/A | Unchanged |
| V — Sealed Core, Versioned Seams | Pass **with obligation** | **Strengthened.** Contract §5 pins the `content_pins` key grammar, §1 pins the manifest field shapes, and §5 states the migration position explicitly: no shim, and a run started before the change must not silently match after it. Security-maintainer review recorded in both contracts |
| VI — Lean by Default | Pass | Final surface: two dataclass extensions, one new dataclass, one render section, one constant. No dependency |
| VII — Anti-Fragmentation | Pass | Row E1 asserts the identical assembled instruction across connected, restricted and air-gapped profiles — provable because nothing is fetched |
| VIII — Eval-Gated Promotion | Pass | **Strengthened.** Contract §9 requires the scorers to read assembled bytes through the production path. Without it FR-013 would have been satisfied by a suite that never looked at the change — the ADR-0047 stub this spec cites as its own precedent |
| IX — Evidence Over Claims | Pass | Data model §5 splits the record in two because `RUN_START` cannot answer "delivered", and §5b closes the 049 gap where per-phase pins were never written. Row A13 asserts the negative case. §2 of the data model narrows the unsatisfiable text to what is true of the registry |
| X — The Decision Record Governs | Pass | No Accepted ADR contradicted; none needed. Two spec reconciliation items carried to analyze rather than resolved in the plan |

**Gate result**: **PASS — design stands.**

## Complexity Tracking

No Constitution Check violation requires justification. One obligation is recorded rather
than a violation:

| Item | Why | Where it is discharged |
| --- | --- | --- |
| Sealed-core touch: `core/packs/manifest.py` and the `RUN_START` `content_pins` payload | The manifest is a registry schema and `content_pins` is audit-schema payload; both are named sealed core in `AGENTS.md` | Approved spec exists; the implementation PR requests security-maintainer review, and [contracts/pack-skill-binding.md](contracts/pack-skill-binding.md) pins the `content_pins` key grammar and the `SkillPin` field shapes as stable now — not "decided at implementation time" |
