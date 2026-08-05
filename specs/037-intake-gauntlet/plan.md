# Implementation Plan: The intake gauntlet

**Branch**: `037-intake-gauntlet` | **Date**: 2026-08-05 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/037-intake-gauntlet/spec.md`

## Summary

Seven stages, built as **three independently shippable layers** so the half that carries no
new risk lands before the half that does. **Detection** (US1) polls pinned upstreams, computes
the exact delta, and opens a proposal — no model reads anything, so the injection hazard is
absent by construction. **Containment** (US2, US4) builds the hardened isolation tier
ADR-0038 named and never got, runs the analyzer inside it under the narrowest ceiling in the
fleet, and qualifies that analyzer against its own human-labelled hostile corpus with a floor
that fails rather than warns. **Detonation** (US3) stands up a purpose-built range — not the
test fake — and runs candidate against pinned version with the observer reading records from
outside, never candidate output.

The whole thing feeds `promote_skill` and changes nothing about it. **No stage can promote**:
US5's rows assert that no sequence of pipeline outcomes reaches production without a recorded
human acceptance.

## Technical Context

**Language/Version**: Python 3.12 (matches repository)

**Primary Dependencies**: none new. The poller uses `urllib` like `corpus_sync.py` and the
enclave readers — no HTTP client enters the tree (the same call 012 made for the portal
relay). The analyzer binds a Qualified Model Matrix cell through the existing
`resolve_with_fallback`, so no provider SDK is added.

**Storage**: none new. Proposals are files in the repository and a pull request; verdicts,
detonation outcomes, canary contact and manual-path use land in the existing audit trail.

**Testing**: pytest — component suites for the pipeline stages, conformance rows in
`tests/conformance/intake/` (new), unit gates for the structural properties, and the
analyzer's qualification as a new eval suite scored like any other.

**Target Platform**: unchanged (macOS dev, Linux CI/Nomad). The range is a Nomad job on the
existing substrate.

**Project Type**: single project. New: `src/core/intake/` (the pipeline's core), a range
jobspec under `infra/jobs/`, `evals/intake-seed/` (the human-labelled corpus), and
`corpus/golden-tasks/` (the detonation corpus).

**Performance Goals**: cost tracks upstream *motion*, not upstream size — the delta against
the pin is the analysis subject (ADR-0053 stage 3). The poll itself is a scheduled job whose
cadence is operator configuration, not a platform constant.

**Constraints**: every stage fails closed; the analyzer's ceiling contains nothing to be
redirected to; specimen and observer are separate workload identities in separate
allocations; `promote_skill` is unchanged; the audit schema grows, so Principle V review.

**Scale/Scope**: two adopted skills today (`packs/terraform/skills/terraform-style-guide`,
`packs/vault/skills/vault-secret-access`), one of which carries an `[upstream]` pin. The
pipeline must work for one and not assume many.

## Constitution Check

| Principle | Verdict | Notes |
| --- | --- | --- |
| I — Build Glue Only | **Pass** | The gauntlet assembles pieces the platform already has — dispatch, ceilings, audit, the matrix, the eval harness. What is genuinely new is the isolation tier and the range, both of which are *posture* rather than product. No gateway, no registry product. |
| II — Total Interception; One Governed Tool Layer | **Pass** | The analyzer is a registered agent definition dispatched like any other; its calls reach tools through `invoke_tool`. The range holds no real authority, so there is no second governed path — there is a governed path pointed at nothing real. |
| III — Fail-Closed, In-Process Enforcement | **Pass** | FR-024 is the feature's spine and every stage carries a row for it. The analyzer's containment is *structural* (FR-009): a redirected analyzer has nothing reachable, which is stronger than an instruction telling it not to be redirected. |
| IV — Zero Standing Credentials; Authority Per Task | **Pass** | The analyzer and the specimen each hold attested workload identity like any allocation. **The range holds no real authority at all** — that is its defining property, and the reason FR-015 refuses the test fake is that a fake with a production life is a credential story nobody reviewed. |
| V — Sealed Core, Versioned Seams | **Pass, with review** | The audit schema grows: analyzer verdicts, detonation outcomes, canary contact, and manual-path use. Additive members on `TOOL_CHOSEN`'s precedent, carrying the approved spec and security-maintainer review Principle V demands. |
| VI — Lean by Default | **Pass, with a named trigger** | The detonation range is an **operated component** and therefore owes a named trigger in an ADR — supplied by ADR-0053's adoption (see Complexity Tracking). No new library, no new store, no new service beyond the range. |
| VII — Anti-Fragmentation | **Pass** | One pipeline, one trigger difference (ADR-0021): connected estates poll, restricted estates poll through the proxy, air-gapped estates run the identical pipeline against an imported snapshot. Two implementations is the thing this forecloses. |
| VIII — Eval-Gated Promotion; Pinned vs Fresh | **Pass** | The feature *is* Principle VIII applied to intake, and the analyzer is itself gated content — US4 exists so the gate has a gate. `OWED` gains a row for the first time since 021 if the analyzer suite lands after the pipeline; the plan sequences it so it does not. |
| IX — Evidence Over Claims | **Pass** | The evidence package is the product. The load-bearing rule: audit distinguishes a machine verdict from a human approval (FR-022), so a reader can never mistake the gauntlet's output for an approval. |
| X — The Decision Record Governs | **Pass, with obligation** | **ADR-0053 moves Proposed → Accepted** in this change, amended by what clarification settled: the range is purpose-built, the analyzer's floor is its own, and the manual path survives with a record. An ADR whose Decision the implementation contradicts is the defect ADR-0060 closed. |

**Gate result**: **PASS — proceed to Phase 0.** Three obligations travel with the feature:
the Principle V review, ADR-0053's status change with its three amendments, and the range's
named trigger.

## Project Structure

### Documentation (this feature)

```text
specs/037-intake-gauntlet/
├── plan.md              # This file
├── research.md          # Phase 0 — what was measured, and what it forced
├── data-model.md        # Phase 1 — proposals, verdicts, comparisons, canaries
├── quickstart.md        # Phase 1 — how to prove each stage, including that it can fail
├── contracts/
│   ├── conformance-intake.md      # detection, containment, the human gate
│   └── conformance-detonation.md  # the range, the separation, the canaries
└── tasks.md             # Phase 2 (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
src/core/intake/              # NEW — the pipeline, product-blind like the rest of core
├── pins.py                   # read [upstream] pins; what "moved" means
├── proposal.py               # candidate identity by content digest, delta, evidence package
├── verdict.py                # the analyzer's structured output; may block, never approves
├── detonation.py             # the comparison: attempts, denials, canary contact
└── manual.py                 # the recorded bypass (FR-025a)

src/core/evals/
├── suites.py                 # + "intake_analysis"; OWED untouched (the suite lands with it)
└── intake_seed.py            # NEW — load/floor the human-labelled hostile corpus

src/core/audit/schema.py      # additive: ANALYSIS_VERDICT, DETONATION_COMPARED,
                              #           CANARY_CONTACT, INTAKE_BYPASSED
evals/intake-seed/            # NEW — human-labelled hostile cases, reviewed like code
corpus/golden-tasks/          # NEW — the fixed task corpus detonation diffs against
infra/jobs/detonation-range.nomad.hcl   # NEW — the operated range, no real authority
infra/bin/intake-poll         # NEW — the scheduled poller (urllib, like corpus-sync)
docs/adr/0053-*.md            # Proposed → Accepted, amended by the clarifications
tests/
├── conformance/intake/       # both contracts
├── component/                # stage behaviour, fail-closed per stage
└── unit/                     # structural: ceiling narrowness, identity separation
```

**Structure Decision**: the pipeline lives in `core/` and is **product-blind** — it knows
about pins, deltas and verdicts, not about Terraform or Vault. The analyzer is an agent
definition, not a module: it is dispatched through the seam that already dispatches every
other agent, which is what makes its ceiling checkable by the machinery that already checks
ceilings. Layering US1 → US2/US4 → US3 is deliberate: each is independently shippable, and
the riskiest layer lands last against a pipeline that already works.

## Constitution re-check (post-design)

Re-evaluated after Phase 1. No verdict changed; two were sharpened by design decisions:

- **IV** — research R5 turned "the range holds no real authority" from a property to assert
  into a component with no authority source to hold, and D6 reads the absence structurally
  rather than testing that nothing happened to be used.
- **IX** — the data model gives `CANARY_CONTACT` its own event rather than a field on the
  comparison, because a canary is a fact about containment and burying it in a diff would
  make the loudest available signal the quietest field in a payload.

One risk moved into the record rather than being resolved: R9 sequences the analyzer's eval
suite to land *with* the analyzer so `OWED` stays empty. Shipping the pipeline first would
create exactly the ungated input ADR-0053 warns about, and ADR-0047 would then require it be
recorded as owed — a worse outcome than sequencing correctly.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
| --- | --- | --- |
| **An operated component** (the detonation range), against Principle VI's default | Stage 5 requires executing a presumed-hostile candidate somewhere it can do nothing. That is a *place*, not a library — it needs its own network posture, its own identity boundary, and canary seeding | **Reusing the test-only authority fake** was the obvious path and is refused by FR-015a: it would mean amending a merge-blocking guard to accommodate a convenience, which is the shape this repository refused when it declined psycopg rather than loosen the licence gate. **Detonating in-process** collapses FR-013's identity separation, which is the one property whose loss recreates the vulnerability the gauntlet exists to inspect |

The trigger is named in ADR-0053's Accepted form, per Principle VI's requirement that every
additional operated component carry one.
