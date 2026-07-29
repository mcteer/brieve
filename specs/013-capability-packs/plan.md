# Implementation Plan: Capability Packs and Eval Gates

**Branch**: `feat/013-capability-packs` | **Date**: 2026-07-29 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/013-capability-packs/spec.md`

## Summary

Two packs, five qualified roles, four eval gates, and the judge regress resolved by a
**human-labeled seed set** — the only one of the spec's three bounded options that
terminates without importing trust from somewhere this platform cannot inspect.

A pack is a **declared manifest plus content**, loaded through a seam that registers its
tools into the registry 002 already built. Nothing in `core` learns a product name. The
Terraform pack *adopts* real upstream skills from `hashicorp/agent-skills`; the Vault pack
*authors* its own in the same format — so ADR-0004's supply chain has a genuine subject and
the authored half is a pull request away from becoming adopted.

The Qualified Model Matrix lands as a **record in the control-plane trust fabric**, beside
the ceilings 010 put there, because it is the same kind of thing: an operator-authored
authorization fact a definition may reference and never widen.

## Technical Context

**Language/Version**: Python 3.12 (existing toolchain; `uv`)

**Primary Dependencies**: no new *runtime* dependency. A new `evals` dev extra carries the
scoring harness and, for the live lane only, one model-provider SDK. **Deliberately absent
from base and `surfaces`**: any provider SDK — the platform's default posture stays "calls
no model", which `pyproject.toml` currently states in as many words.

**Storage**: the control-plane Vault for the matrix and pack pins (operator-authored,
read-only to runs — the 010 pattern). Pack content on disk under `packs/`, verified by
digest. Eval results in Postgres beside the audit trail.

**Testing**: pytest. Rows for pack loading and isolation, matrix refusals, supply-chain
promotion, and the gates themselves. Live-model scoring behind `@pytest.mark.live_model`,
never in the blocking lane.

**Target Platform**: the dev enclave. **No new operated component** — Vault, Nomad, and
Postgres already run, which is why Vault was the right second pack.

**Project Type**: a core seam (pack loading) + content (two packs) + a gate discipline
(evals) + one trust-fabric record type (the matrix).

**Performance Goals**: none newly binding. An eval run is a gate, not a hot path.

**Constraints**: no core module names a product; no pack widens a ceiling; no path reaches
an unqualified model; no auto-tracking anywhere; a model verdict never satisfies a human
approval; report fidelity recorded as owed rather than stubbed.

**Scale/Scope**: two packs, five roles, one provider in the live lane.

## Constitution Check

| Principle | Verdict | Notes |
| --- | --- | --- |
| I — Build Glue Only | **Pass** | Terraform's skills are *adopted* from `hashicorp/agent-skills`, which is ADR-0004's instruction honoured rather than paraphrased. No registry product: packs register into the registry 002 built. Vault's authored skills use the upstream format (FR-027d) so they migrate onto upstream as it matures — the "migrate onto and delete anything they absorb" half of this principle, made operational. |
| II — Total Interception; One Governed Tool Layer | **Pass** | Pack tools are `ToolRegistry` registrations like any other, so they inherit the hook pipeline **by construction rather than by discipline**. **Risk class becomes real** — it is in the glossary and nowhere in code today — and registry review may require process isolation for `secret-touching` and `destructive`. Transport stays a tool property; no MCP server is authored for uniformity. |
| III — Fail-Closed, In-Process Enforcement | **Pass** | No new enforcement point. Every new refusal — unqualified cell, tier violation, unpinned skill, unverified digest — fails closed, and each is asserted as the *absence of any permissive path* rather than as one branch behaving. |
| IV — Zero Standing Credentials; Authority Per Task | **Pass** | A pack carries no credential. Pack tools resolve authority through the same manufacture path, and **a pack cannot widen a ceiling** (FR-005) — asserted, because a pack declaring tools its definition's ceiling omits is the obvious shortcut and would read as a feature. The live lane's provider key is a dev-lane secret: never in a jobspec, never read by a run. |
| V — Sealed Core, Versioned Seams | **Pass, two recorded additions** | `ToolRegistration` gains `risk_class` (additive, defaulted). `AuditEventType` gains `MODEL_GATE`, because FR-015 requires the trail to distinguish a model verdict from a human approval and reusing an approval event would erase exactly that distinction. Both are sealed-core edits; this approved spec is the required spec, security-maintainer review is Dan. |
| VI — Lean by Default | **Pass** | No new operated component. The eval harness is a library and a dev extra, not a service. Pack content is files. |
| VII — Anti-Fragmentation | **Pass** | Packs are identical across substrates; the matrix is a control-plane record every deployment already has. |
| VIII — Eval-Gated Promotion | **Pass — and this is the feature** | Brought online for the first time: the matrix, binding maps, fallback-only-to-qualified-or-stop, no auto-tracking, pinned judges, and provenance + injection-lens + eval on every skill bump. **Report fidelity is recorded as owed against ADR-0018**, per ADR-0047 — absent or an explicit skip citing its deferring record, never a stub. |
| IX — Evidence Over Claims | **Pass** | Provenance-at-read for consulted artifacts into the run record. Eval results are records rather than claims. `MODEL_GATE` keeps a verdict and an approval distinguishable in the trail. |
| X — The Decision Record Governs | **Pass** | ADR-0004, 0022, 0030, 0039, 0045 built as written. **ADR-0052 (new)** records the judge-regress resolution, because "what qualified the first judge" must outlive this spec. ADR-0023 stays unbuilt and is recorded as owed rather than quietly dropped. |

**Named-runner obligation** (constitution v1.1.0): the **live-model lane** has no automated
runner — it needs a provider credential and costs money per run, so it cannot sit in CI.
Named runner: **Dan**, before merge, with the per-cell outcome recorded in
`contracts/conformance-packs.md` (SC-013).

*This is a genuine named-runner case rather than the shape 012 got wrong. There, "needs a
human" was deferral disguised as rigour and a browser could do the work. Here the obstacle is
a paid credential and non-determinism, not missing tooling — and the blocking lane still runs
every gate, against fixtures.*

**Gate result**: **PASS — proceed to Phase 0.**

## Project Structure

### Documentation (this feature)

```text
specs/013-capability-packs/
├── plan.md              # This file
├── research.md          # Phase 0 — findings F1–F3, decisions D1–D12
├── data-model.md        # Phase 1 — manifests, cells, pins, eval records
├── quickstart.md        # Phase 1 — end-to-end validation
├── contracts/
│   ├── pack-manifest.md          # What a pack declares; what loading it does
│   ├── qualified-matrix.md       # Cells, binding maps, refusals, fallback
│   └── conformance-packs.md      # Four gates, the owed fifth, per-cell fixture/live record
└── tasks.md             # /speckit-tasks output (not created here)
```

### Source Code (repository root)

```text
src/core/packs/
├── __init__.py          # Package intent: packs are content; the core stays product-blind
├── manifest.py          # PackManifest, ToolDeclaration, RiskClass, SkillPin
├── loader.py            # PackLoader protocol + FilesystemPackLoader; digest verification
├── registration.py      # Manifest → ToolRegistry registrations, risk class preserved
└── isolation.py         # Which packs a definition reaches; the no-widening check

src/core/evals/
├── __init__.py          # Package intent: gates are records, not claims
├── suites.py            # must-deny, must-decline, citation accuracy, estate-state
├── scoring.py           # Scorer protocol; FixtureScorer and LiveModelScorer
├── matrix.py            # QualifiedCell, matrix reader, binding-map validation
├── promotion.py         # Skill bumps: provenance + injection lens + eval, all three
└── judge.py             # The seed set, and what qualified the first judge

src/core/registry/memory.py   # + risk_class on ToolRegistration (additive)
src/core/audit/schema.py      # + MODEL_GATE (a verdict is not an approval — FR-015)

packs/
├── terraform/           # ADOPTED from hashicorp/agent-skills @ pinned commit
│   ├── pack.toml
│   ├── skills/          # upstream content, unmodified, with PROVENANCE.md
│   └── evals/
└── vault/               # AUTHORED here, in the upstream format (FR-027d)
    ├── pack.toml
    ├── skills/
    └── evals/

evals/seed/              # Human-labeled verdicts. The root of the judge chain (ADR-0052).

docs/adr/0052-the-first-judge-is-qualified-by-a-human-labeled-seed-set.md
```

**Structure Decision**: `core/packs` and `core/evals` are new packages in the existing
layout. **`packs/` sits at the repository root rather than under `src/`**, deliberately: it
is content, not code, and putting product knowledge inside the Python package tree would
ship it in the distribution that Principle I says stays product-blind. `evals/seed/` is
likewise data — and it is the one directory in this repository whose *authority comes from
a human having labelled it*, which is worth keeping visible rather than buried in a package.

## Complexity Tracking

No violations to justify. The two seam additions and the new ADR are recorded in the
Constitution Check above.
