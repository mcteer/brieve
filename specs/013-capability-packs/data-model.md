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
| `hooks[]` | array | Pack hook declarations — see below. **Never `capability_kind = GOVERNANCE`** |
| `workflows[]` | array | Workflow declarations, each with a minimum tier |
| `evals` | table | Which suites this pack ships cases for |
| `probe` | string | **Names how this pack's product is checked for reachability.** Resolved from what the platform provides, exactly as a tool handler is — never pack code. Required whenever any tool declares a `product` |

**Properties**:

- **A manifest is data, never code.** Loading executes nothing from the pack; the handler a
  tool declaration names is resolved from what the platform already provides. **The probe
  follows the same rule**, which is why it is a name rather than an implementation: a pack
  supplying its own reachability check would be pack code running inside the health checker,
  and the checker is the single owner of "reachable" (009, FR-006a).
- **`probe` is required, and its absence is the sharpest trap in this feature** (analyze
  pass 12). `HealthChecker.products()` derives its subject set from `registry.products()` —
  so a loaded pack's product is monitored automatically, which is the good half. The probe
  is *supplied*, and the only one wired is `unconfigured_probe`, which returns
  `(False, "no probe configured for this product")`. Unreachable, therefore `UNHEALTHY`,
  therefore `dependency_pre_hook` denies **every call to that pack's tools** with
  `dependency_unavailable` — *"vault is not reachable"* — while Vault is running perfectly.
  009's own docstring records the assumption 013 breaks: *"this platform fakes product APIs
  by constitutional decision, so there is nothing here to reach yet."* FR-027b makes Vault
  the pack whose tools reach a product that genuinely runs, so 013 is where that stops being
  true. Refused at load (`probe_required`) rather than discovered at the first denied call,
  because the denial names the product and the product is not the problem — the same
  blames-the-wrong-system shape as the missing Vault grant found at pass 1.
- **`provenance` is not decorative.** `adopted` requires `upstream`, and promotion checks
  the pinned commit; `authored` skips the upstream check and gains an obligation instead —
  FR-027d's format requirement, so it can become `adopted` later without a rewrite.

## Tool declaration *(inside the manifest)*

| Field | Type | Notes |
| --- | --- | --- |
| `name` | string | Registered under this name in the one governed registry |
| `risk_class` | enum | `read` \| `write` \| `destructive` \| `secret_touching` |
| `transport` | enum | `mcp` \| `native`. A tool property (Principle II), never a uniformity requirement |
| `product_mode` | enum | `none` \| `federate` \| `broker`. **Declared, not inferred** — the registry raises a `ValueError` when this is not `none` and `product`/`product_action` are absent, and a manifest should refuse in its own vocabulary rather than surface a driver-level error |
| `product` | string? | Required when `product_mode != none` |
| `product_action` | string? | Joins to the ceiling vocabulary, as 010 established |
| `repeatable` | bool | Existing registry semantics |
| `observer` | string? | **Required when `repeatable = false`.** Names the observer that answers "what actually happened" for a call interrupted mid-flight |
| `isolation_required` | bool | Registry review may demand process isolation for `secret_touching` and `destructive`. **Declared and not yet enforced in 013** — recorded so a boolean nobody reads is not mistaken for a control |

**`observer` is the field whose absence would have broken every real pack.** The registry's
own comment says it plainly: *required in practice for a non-repeatable tool — without one,
an interrupted step resolves to `CANNOT_DETERMINE` and parks the run.* A pack's `write` and
`destructive` tools are exactly the non-repeatable ones, so a manifest that declared
`repeatable = false` and no observer would ship every dangerous tool with 005's
re-observation machinery unreachable — green gates over runs that suspend the first time
anything is interrupted. **Loading refuses `observer_required`**, which is where a
"required in practice" becomes checkable rather than hoped for.

**`risk_class` is the finding F2 made real.** It exists in the glossary and nowhere in the
code; nothing in this platform has ever known how dangerous a tool is. Harmless while every
tool was `echo`, and not harmless the moment a pack declares something that deletes
infrastructure — which is the first thing a real pack does.

## Pack hook declaration *(inside the manifest)*

| Field | Type | Notes |
| --- | --- | --- |
| `name` | string | Qualified by its pack |
| `phase` | enum | `pre` \| `post` |
| `capability_kind` | enum | **Never `governance`.** Refused at load: `governance_hook_from_pack` |
| `handler` | string | Resolved from what the platform provides, like a tool's |

**This is the one manifest component that is not inert content, and it went nine passes
without a record.** FR-001 and the glossary have both listed pack hooks since specify time;
the manifest had `tools`, `skills`, `workflows`, and `evals`.

**Why the governance restriction is the whole point**: `has_required_governance_hooks`
asserts the built-in governance pre-hooks are all present, and it identifies them by
`capability_kind == GOVERNANCE`. A pack registering a hook of that kind would enter the set
that check validates — so a pack could satisfy the platform's enforcement-is-whole check
with its own hook, which is enforcement authored by whoever ships a pack. Principle III
requires `GovernanceCapability` to run first and fail closed; a pack that could register at
that kind can reorder enforcement.

**Pack hooks receive the narrowed context and must not read `HookContext.run`.** That field
carries its own warning — *"populated for built-in governance hooks only; third-party hooks
must not depend on this attribute; the hook context narrows further before the Hook SDK seam
ships"* — and pack hooks are third-party by definition, arriving *before* that seam. A pack
depending on `run` today is a pack the Hook SDK breaks tomorrow.

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

## Definition bindings *(new control-plane record: `harness-authority/data/definition-bindings`)*

**The record the whole feature reads, and which did not exist until analyze pass 8.** FR-005
("a definition MUST reach only the packs it names"), the isolation check, the binding-map
validation, and tier resolution all read fields that lived in the glossary, in the
assumptions, and in four tasks' logic — and in no record.

| Field | Type | Notes |
| --- | --- | --- |
| `agent_definition_id` | TEXT | Keyed by the same display name the registration and ceiling use |
| `packs` | list | Which packs this definition reaches. **Naming a pack does not grant its tools** — the ceiling still bounds those (FR-005) |
| `binding_map` | table | `role → provider/model@version`, each resolving to a qualified cell |
| `tier` | int | The competency tier bounding what it may compose (ADR-0045) |

**Beside the ceiling, not on the registration** — the same reasoning `ceilings.tf` already
records: the registry engine serves its own registration format, so the harness's own facts
about a definition live in the harness-authority KV. Operator-authored, read-only to runs,
written by the same Terraform apply as the ceiling so no window exists where a definition
has one and not the other.

**The read policy must grant this path too**, for the reason `data/policies/*` documents:
without a grant, Vault answers 403 rather than 404 and a definition with no bindings is
indistinguishable from one nobody may read.

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

## Binding map *(inside the definition-bindings record above)*

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

**Who writes it, because nothing said and it turns out nothing could** (analyze pass 11).
The fallback is *resolved* inside `manufacture_authority`, which takes no audit sink and no
`tenant_id`, and returns a frozen `ManufacturedAuthority` with no channel for "cell A was
unavailable, cell B was used". `AuditEntry` requires a `tenant_id` that function never sees.
So the event was specified with no writer — and adding a sink parameter there would break
the discipline that module already keeps: **it raises `AuthorityRefuseError` and lets the
caller record `AUTHORITY_REFUSED`.** The fallback follows the same rule in the other
direction — it is **returned, not written** — and the caller that owns the sink emits it.

## Fallback carrier *(existing records, one additive field each)*

| Record | Field | Emitted by |
| --- | --- | --- |
| `ManufacturedAuthority` (`core/authority/manufacture.py`) | `matrix_fallback: MatrixFallback \| None = None` | `start_governed_run`, which already holds `sink` and `tenant` |
| `ResumeDecision` (`core/durability/resume.py`) | `matrix_fallback: MatrixFallback \| None = None` | the resume caller, on the same rule |

`MatrixFallback` is a frozen record carrying `role`, `pinned_cell`, `used_cell`, and
`reason` — the payload of the event, one layer before it becomes one.

**Both, not just the first.** `resume_run` calls `manufacture_authority` too, so a resumed
run can fall back, and a resumed run's fallback going unrecorded is the same defect wearing
a different phase. Neither field changes a signature; both are additive with defaults.

## Durability touchpoints *(existing: `core/durability/`)*

Three things this feature requires of the layer that survives an interruption, none of which
were stated and all of which the code decides.

**A withdrawn cell on resume must stop with a reason.** `resume_run` acquires the lease and
*then* calls `manufacture_authority`, with no `except AuthorityRefuseError`. Every other
failure in that function returns a `ResumeDecision` carrying `stop_reason` — a missing
checkpoint, an expired grant. This one throws past the contract with the lease held. That was
tolerable while the only refusals were fabric-level errors; D6's rationale is that **a cell
can be withdrawn**, which makes it an ordinary mid-flight state landing on the one path that
records nothing. `cell_withdrawn` and `pack_not_loaded` both resolve to `STOPPED` with the
reason recorded (FR-010, SC-004).

**A suspended pack-tool step must name the product, not the tool.** `resume_run`'s
`depends_on` maps tool → product so a suspension names something the sweeper also names —
and it is **constructed nowhere in the tree**, so today every suspension falls back to the
tool name. `SuspendedRunIndex.awaiting()` matches on *product*. The docstring already states
the consequence: a suspension carrying only a tool name is never matched by a product
recovering. Pack tools reach real products and `ToolDeclaration` carries `product`, so the
map is derivable from loaded manifests — and without it a suspended Vault step **never
resumes and nobody is told**.

**The run record must name which pack content executed.** `CheckpointBlob` carries
`correlation_id`, `grant_id`, `step_index`, `written_by`, and `outcome` — nothing about
content. A resumed run in a new allocation reloads `packs/` from disk and verifies digests
*against the manifest sitting beside them*, so edited content verifies clean and the run
continues at a different skill version. FR-020's pinning holds per-load, not per-run. The
loaded pack digests go in the `RUN_START` payload — no seam change, and it is what lets an
attestation name the pack version the way FR-021 already names consulted guidance.

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
| Pack hook declares `capability_kind = governance` | `governance_hook_from_pack` — refused at load. Enforcement is the platform's, and a pack that could register at that kind could satisfy the enforcement-is-whole check with its own hook |
| Non-repeatable tool declared with no observer | `observer_required` — refused at load. The registry calls an observer "required in practice"; this is where that becomes checkable |
| `product_mode` set without `product` or `product_action` | `incomplete_product_binding` — refused at load, in the pack's own vocabulary, rather than as a registry `ValueError` |
| Definition names a pack that is not loaded | `pack_not_loaded` — refused **at run start**, so the person is told before anything executes rather than after a step has run |
| Pack ships fewer eval cases than the floor | `insufficient_eval_coverage` — refused **at load**, not warned about, because a floor nothing enforces is a suggestion and the failure belongs where the pack is added |
| Pack declares a product with no `probe` | `probe_required` — refused **at load**. Without it the product records `UNHEALTHY` on the default probe and the dependency gate denies every one of that pack's tools, naming a product that is running fine |

Each is added to `OPERATION_REASONS` rather than invented at a call site — the 010 rule,
and the reason a conformance row can assert on any of them.
