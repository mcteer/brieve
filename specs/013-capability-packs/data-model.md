# Phase 1 Data Model: Capability Packs and Eval Gates

**Feature**: `specs/013-capability-packs` | **Date**: 2026-07-29

Four record kinds, one field added to an existing one, two audit events, and a directory
whose authority comes from a person having labelled it.

The organizing rule: **a pack declares; the platform decides.** A manifest is a claim about
what a pack contains and how dangerous it is. Nothing in a manifest grants anything — the
ceiling still bounds tools, the matrix still bounds models, the tier still bounds
composition. A pack that could widen any of those would be a way to grant yourself
authority by shipping a file.

---

## Pack manifest *(new: `packs/<name>/pack.toml`)*

| Field | Type | Notes |
| --- | --- | --- |
| `name` | string | Pack identifier. Named by a definition; never inferred |
| `product` | string | The managed product. **The only place a product is named outside `packs/`** — nothing under `src/core` may contain it (SC-002) |
| `version` | string | The pack's own version, bumped deliberately |
| `provenance` | enum | `adopted` \| `authored`. Terraform is adopted; Vault is authored |
| `upstream` | table? | For `adopted`: repository, commit, licence. Absent for `authored` |
| `tools[]` | array | Tool declarations — see below |
| `skills[]` | array | Skill pins — see below |
| `workflows[]` | array | Workflow declarations, each with a minimum tier |
| `evals` | table | Which suites this pack ships cases for |

**Properties**:

- **A manifest is data, never code.** Loading executes nothing from the pack; the handler a
  tool declaration names is resolved from what the platform already provides.
- **`provenance` is not decorative.** `adopted` requires `upstream`, and promotion checks
  the pinned commit; `authored` skips the upstream check and gains an obligation instead —
  FR-027d's format requirement, so it can become `adopted` later without a rewrite.

## Tool declaration *(inside the manifest)*

| Field | Type | Notes |
| --- | --- | --- |
| `name` | string | Registered under this name in the one governed registry |
| `risk_class` | enum | `read` \| `write` \| `destructive` \| `secret_touching` |
| `transport` | enum | `mcp` \| `native`. A tool property (Principle II), never a uniformity requirement |
| `product_action` | string? | Joins to the ceiling vocabulary, as 010 established |
| `repeatable` | bool | Existing registry semantics |
| `isolation_required` | bool | Registry review may demand process isolation for `secret_touching` and `destructive` |

**`risk_class` is the finding F2 made real.** It exists in the glossary and nowhere in the
code; nothing in this platform has ever known how dangerous a tool is. Harmless while every
tool was `echo`, and not harmless the moment a pack declares something that deletes
infrastructure — which is the first thing a real pack does.

## Skill pin *(inside the manifest)*

| Field | Type | Notes |
| --- | --- | --- |
| `id` | string | Skill identifier |
| `version` | string | **Pinned. Never auto-tracked** (FR-016) |
| `digest` | string | SHA-256 of the content. What makes "pinned" checkable rather than asserted |
| `upstream_path` | string? | For adopted skills: where it came from |
| `reviewed_at` / `reviewed_by` | string? | The injection-lens review record |
| `overlay_of` | string? | Set when this is an overlay on an adopted baseline, so FR-019's distinction survives a bump |

**A skill whose bytes changed without its digest changing is the ungated drift Principle
VIII exists to stop**, and it is invisible without the hash. Verification happens at load,
not at review time, because review is when someone looked and load is when it matters.

## Qualified cell *(new control-plane record: `harness-authority/data/model-matrix`)*

> **The read policy must grant this path.** `harness-authority-read` covers
> `data/harness-ceilings/*` and `data/role-bindings/*` and nothing else. Without a grant on
> `data/model-matrix/*`, Vault answers **403 rather than 404** — so "no matrix" is
> indistinguishable from "not allowed to look", and every run-start validation reports an
> unreachable trust fabric for a matrix that is merely unreadable. The `data/policies/*`
> grant in `policies.tf` documents this exact trap from 010; this is the same one.

| Field | Type | Notes |
| --- | --- | --- |
| `pack` | string | |
| `model` | string | **`provider/model@version`**, all three parts required. A bare name, an alias, or a `@latest` is refused at parse — FR-011's no-auto-tracking rule enforced at the identifier rather than only at the lookup, because an alias that resolves at read time is exactly the moving target it forbids |
| `role` | enum | `ask` \| `plan` \| `write` \| `judge` \| `summarize` — the closed vocabulary |
| `qualified_at` | timestamp | |
| `qualified_by` | enum | **`fixture` \| `live`** — which scorer, per cell (SC-013) |
| `suite_results` | table | Per-suite scores **and the thresholds they were judged against**. The thresholds live *here*, in the operator-authored matrix — never in the pack. A pack that set its own passing grade would be a pack that grades itself, and the whole point of a gate is that the thing being gated does not hold the bar |
| `judge` | string? | Which judge scored this cell; absent only for the seed-qualified first judge |

**Where it lives, and why that matters**: in the control-plane trust fabric beside the
ceilings 010 put there — operator-authored, read-only to runs, refused loudly when absent.
A cell is an *authorization fact*, the same kind of thing as a ceiling, and must be
un-widenable from inside a run for the same reason. In-repo TOML was rejected because it
would make qualifying a model a deploy, and the pressure to skip a deploy is exactly how
auto-tracking gets reinvented.

**`qualified_by` is the honesty field.** A cell scored by `FixtureScorer` is qualified
against a recording. The distinction is per cell rather than per matrix because the two
lanes will not stay in step — the live lane runs when someone runs it.

## Workflow record *(new: `src/core/packs/workflows.py`)*

| Field | Type | Notes |
| --- | --- | --- |
| `name` | string | Qualified by its pack, like a tool |
| `minimum_tier` | int | The tier a definition must hold to run it |
| `paved` | bool | A fully-verified golden path; lower tiers may run only these |

**Added by analyze pass 1 (G1).** The manifest already declared `workflows[]` and nothing in
the platform had a runtime shape for one — so tiers had nothing to bound, and US5's rows
would have asserted a refusal against a concept that did not exist. Deliberately minimal: a
workflow here is a *named, tiered thing a definition may or may not run*, which is all
ADR-0045 needs. What a workflow *does* is pack content.

## Binding map *(inside an agent definition)*

`role → model`, five entries or fewer, **each of which must resolve to a qualified cell for
that definition's pack**.

Validated **twice** (D6): at definition registration, and again at run start. The second is
not redundant — a cell can be *withdrawn* after a definition pinned it, and validating only
at registration would let a withdrawn cell keep running because nothing re-asked. The same
reasoning makes 010 resolve a ceiling per run rather than caching it.

## Eval case and result *(new: `packs/<name>/evals/`, results in Postgres)*

A **case** is an input, an expected outcome, and the suite it belongs to — content, shipped
in the pack. A **result** is a case, a cell, a scorer, a verdict, and a timestamp — a record,
stored in `eval_results`.

Results are **written by `core/evals`** and **read by `core/authority/matrix.py`** when it resolves a cell — so the run path reaches them only through the matrix module, and nothing on that path imports the scoring harness.

**The schema is applied at bring-up** (`src/core/evals/schema.sql`, in `enclave-up`'s
existing statement block), not on first use. 012 left `run_inputs` to the API service's
migrate-on-boot and every dispatched run died with `relation "run_inputs" does not exist`;
that script's comment records the rule and says it has bitten four times.

| Suite | Asserts |
| --- | --- |
| `must_deny` | Safety refusals the agent must make |
| `must_decline` | Requests outside declared scope it must decline with a pointer elsewhere |
| `citation_accuracy` | Claims carry citations that resolve, and absent grounding produces a decline rather than confabulation |
| `estate_state` | Answers about the estate match recorded fixtures |

**Report fidelity is deliberately absent** and recorded as owed against ADR-0018 (FR-013a):
`RunReport` does not exist in `src/`, so a suite over it would assert something about a thing
that is not there. Per ADR-0047 that is an explicit skip citing its deferring record, never
a stub, and never a weaker property asserted under its name.

## The seed set *(new: `evals/seed/`)*

Human-labelled verdicts. Cases with outcomes a person decided, checked in, reviewed like
code.

**This is the root of the judge chain** (ADR-0052, D1). The first judge is qualified by
scoring it against the seed; every later judge is qualified by a judge that was itself
qualified, back to here. The authority is a person's judgement — visible in a diff,
arguable, revisable through the same process as anything else.

It is also the one directory in this repository whose authority comes from *a human having
labelled it*, which is why it sits at the root rather than inside a package. Its maintenance
obligation is real and recorded in ADR-0052: a seed set that stops being representative
silently weakens every gate above it.

## Registry addition *(existing: `ToolRegistration`)*

One field: `risk_class`, additive and defaulted, so every existing caller is unchanged.

## Audit additions *(existing: `AuditEventType`)*

### `MODEL_GATE`

A model verdict that gated a step. Payload: `run_id`, `role`, `model`, `cell`, `verdict`,
`step_index`.

**Establishes a distinction rather than repairing one.** F3 found there is no approval event
to be confused with — `AuditEventType` has no approval member at all — so this is added
knowing that when human approvals gain their own event, the two are already separate. A
model verdict may gate a step and **never** satisfies an approval policy assigns to a human
(FR-015, Principle IX).

### `MATRIX_FALLBACK`

The pinned cell was unavailable and another qualified cell was used. Payload: `run_id`,
`role`, `pinned_model`, `used_model`, `reason`.

Separate from `MODEL_GATE` because they answer different questions — "a model decided
something" versus "the model that ran was not the model that was pinned" — and an
investigator looking for the second should not have to filter the first.

---

## Refusal vocabulary *(extending 011's frozen mapping)*

| Situation | Reason code |
| --- | --- |
| Definition pins a cell that is not qualified | `unqualified_cell` |
| Pinned cell withdrawn since registration | `cell_withdrawn` |
| No qualified cell available for fallback | `no_qualified_fallback` |
| Pack declares a tool outside the definition's ceiling | `pack_exceeds_ceiling` |
| Workflow above the definition's tier | `above_tier` |
| Skill content fails digest verification | `digest_mismatch` |
| Skill bump missing provenance, review, or a passing eval | `promotion_incomplete` |
| Injection-lens refusal | `injection_suspected` |

Each is added to `OPERATION_REASONS` rather than invented at a call site — the 010 rule,
and the reason a conformance row can assert on any of them.
