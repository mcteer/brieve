# Implementation Plan: Product-and-phase Build instructions

**Branch**: `spec/049-phase-product-prompts` | **Date**: 2026-08-19 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/049-phase-product-prompts/spec.md`

## Summary

Replace the generic Build steer with **one pinned `AGENTS.md` per phase per product pack**.
Terraform and Vault each ship five files (Research, Plan, Write, Judge, Propose) under
`packs/<pack>/agents/<phase>/AGENTS.md`, declared as digest-pinned `[[agents]]` rows in
`pack.toml`. The authoring-tier run binds **exactly one pack** (`AuthoringRequest.pack` /
`RUN_PACKS`) and loads that pack's file for the current `PhaseName`. Missing, empty,
digest-mismatched, or unpromoted instructions fail closed and do not open a PR. Ask is
unchanged. The portal does not compose these files.

Authorship of published HashiCorp practice happens when writing those files (provenance
sibling, ADR-0004). Runtime never fetches the public web. Individual then joint refinement
uses the requester-named methods: **GEPA** per instruction, then a **DSPy** five-predictor
program jointly, both only in optional extra `prompt-tune` (never `src/core`, never during a
person's Build). Promotion reuses the existing three-check pattern via
`promote_phase_agents`.

## Technical Context

**Language/Version**: Python 3.12 (uv-managed); pack content is Markdown + TOML

**Primary Dependencies**: none on the served path. Optional extra `prompt-tune` pins
`dspy==3.3.0` (MIT; PyPI package `dspy`, not the `dspy-ai` alias) for offline GEPA then
DSPy. Transitives must pass `scripts/check-licenses.sh` before the extra lands; a GPL-family
transitive stops the extra rather than the license gate. Model calls during refinement use
the existing eval-lane broker (ADR-0058), not a new vendor key.

**Storage**: pack tree + existing Postgres audit / run pins. No new operated datastore.
Instruction identity is recorded on the run (`content_pins` keys
`{pack}/agents/{phase}` → digest) joinable on the correlation ID.

**Testing**: pytest hermetic for binding, fail-closed omission, product isolation, pinning,
record-keeping, and "DSPy is not importable from served packages". Eval lane (fixtures that
can fail, plus named-runner live GEPA/DSPy and SC-006) for instruction quality. Tests never
call a live model.

**Target Platform**: authoring-tier allocations (same as 047); air-gapped profiles execute
the same pinned files.

**Project Type**: single project — pack content, pack loader/manifest, choice request field,
dispatch phase bind, eval promotion, optional extra + offline scripts.

**Performance Goals**: loading five small Markdown files at phase start is dominated by the
existing model/tool loop; no new latency budget.

**Constraints**: core remains product-blind (`test_core_is_product_blind` unedited in
spirit; no Terraform/Consul/Packer identifiers in `src/core`). Adapter glue may prepend
`ChoiceRequest.instruction` but must not learn product practice. No second authorization
path. No root-`AGENTS.md` fallback. No SKILL.md stand-in. Judge cell stays distinct from
Write (ADR-0039). ADR-0067 remains Proposed and is not cited as governing.

**Scale/Scope**: ten `AGENTS.md` files + ten `PROVENANCE.md` siblings; loader + pin + bind
path; two eval qualifications (`phase_agents`, `build_agents`); extra `prompt-tune`;
ADR-0071 (prompt-optimization libraries stay off the served path).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*
*Source of truth: [`.specify/memory/constitution.md`](../../.specify/memory/constitution.md)
(v1.6.0).*

| Principle | Verdict | Notes |
| --- | --- | --- |
| I — Build Glue Only | **Pass** | Product practice lives in packs. Core loads bytes by pack name + `PhaseName`. `dspy` is extra-only; a unit gate refuses `src/core` and served `src/adapters` / `src/surfaces` importing it |
| II — Total Interception; One Governed Tool Layer | **Pass** | No new tool, no live web fetch during Build, no second authorization path. Refinement is operator/eval-lane, analogous to corpus-sync — not a served egress class |
| III — Fail-Closed, In-Process Enforcement | **Pass** | Missing/empty/mismatch/unpromoted/ambiguous pack → phase fails, no PR. ImportError of `dspy` refuses promotion rather than shipping unrefined text as promoted |
| IV — Zero Standing Credentials | **Pass** | No new standing secret. GEPA/DSPy use the existing model broker in the eval lane |
| V — Sealed Core, Versioned Seams | **Pass, review owed** | Touches `PackManifest` / loader, `ChoiceRequest`, `content_pins`, adapter prompt composition, possibly audit payload keys. Security review. Named reviewer: Dan |
| VI — Lean by Default | **Pass** | No new operated component. `prompt-tune` is an extra, not the Lean default install |
| VII — Anti-Fragmentation | **Pass** | One bind path for every authoring-tier phase (`load_phase_agents`); API/MCP/portal inherit it. Ask does not grow a parallel instruction table |
| VIII — Eval-Gated Promotion; Pinned vs Fresh | **Pass** | Executed `AGENTS.md` is digest-pinned (ADR-0030). GEPA/DSPy never run inside a person's Build. `promote_phase_agents` requires provenance, injection lens, and both qualifications |
| IX — Evidence Over Claims | **Pass** | Run record names pack, phase, version, digest on the correlation ID. Provenance siblings are reviewable |
| X — The Decision Record Governs | **Pass** | Consumes Accepted ADR-0004, 0022, 0030, 0034, 0039, 0047, 0068. Does not treat Proposed ADR-0067 as authority. Adds ADR-0071 at implement |

**Gate result**: **PASS — proceed to Phase 0.**

**Post-design re-check**: still **PASS**. Design pins exact pack paths, keeps core product-blind,
puts GEPA/DSPy in `prompt-tune` only, and fails closed on incomplete or unpromoted sets.

*Named-runner obligation*: live GEPA then DSPy promotion against the eval broker; SC-006
statistical comparison vs generic steer. **Named runner: Dan McTeer (maintainer).** Enclave
rows fail loudly when the enclave is absent.

## Project Structure

### Documentation (this feature)

```text
specs/049-phase-product-prompts/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── pack-agents.md
│   ├── prompt-tune.md
│   └── conformance-phase-product-prompts.md
└── tasks.md                 # not created by /speckit-plan
```

### Source Code (repository root)

```text
packs/terraform/agents/{research,plan,write,judge,propose}/AGENTS.md
packs/terraform/agents/{research,plan,write,judge,propose}/PROVENANCE.md
packs/vault/agents/{research,plan,write,judge,propose}/AGENTS.md
packs/vault/agents/{research,plan,write,judge,propose}/PROVENANCE.md
packs/{terraform,vault}/pack.toml          # [[agents]] pins
packs/{terraform,vault}/evals/phase_agents.toml
packs/{terraform,vault}/evals/build_agents.toml

src/core/packs/manifest.py                 # AgentPin
src/core/packs/loader.py                   # digest + completeness
src/core/packs/agents.py                   # load_phase_agents (product-blind)
src/core/choice/chooser.py                 # ChoiceRequest.instruction
src/core/choice/bounded.py                 # pass instruction through
src/core/evals/promotion.py                # promote_phase_agents
src/core/evals/suites.py                   # PHASE_AGENTS_QUALIFICATION, BUILD_AGENTS_QUALIFICATION
src/surfaces/toolset.py                    # content_pins keys
src/surfaces/dispatch/entrypoint.py        # bind at phase start; fail closed
src/adapters/model_chooser.py              # prepend request.instruction; keep tool-schema hints only

evals/prompt-tune/                         # GEPA then DSPy scripts; not imported by served code
pyproject.toml                             # optional-dependencies.prompt-tune
docs/adr/0071-prompt-optimization-is-eval-lane-only.md
```

**Structure Decision**: executed instructions are pack content (repository-root `packs/`,
never inside `src/`). Core grows a product-blind pin/load/promote seam parallel to skills.
Dispatch binds one file per phase. Refinement lives under `evals/prompt-tune/` behind extra
`prompt-tune`.

## Complexity Tracking

| Violation | Why needed | Simpler alternative rejected because |
|-----------|------------|-------------------------------------|
| Optional extra `prompt-tune` (`dspy==3.3.0`) | Spec names GEPA then DSPy; those libraries are the methods | Hand-editing prompts with no losing optimizer would fail FR-009/010 and SC-004 |
| `AgentPin` alongside `SkillPin` | FR-016 forbids SKILL.md as the phase instruction | Reusing `[[skills]]` would make a skill a stand-in |
