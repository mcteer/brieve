# Phase 0 Research: Adopted skills reach the phase that needs them

**Feature**: 051 | **Date**: 2026-08-26 | **Spec**: [spec.md](spec.md)

Every `NEEDS CLARIFICATION` raised in the plan's Technical Context is resolved here. Two
findings (R7, R8) were not anticipated by the spec and change what the feature must ship;
both are carried into the plan rather than left in this file.

---

## R1 — Where the instruction is assembled

**Decision**: `core/packs/agents.py`. `load_phase_agents` returns a `PhaseAgents` whose
`body` is already the assembled instruction, and gains a `skills` tuple naming what went
into it. `surfaces/dispatch/phase_agents.py` is unchanged except for recording.

**Rationale**: Three facts decide it.

1. FR-003 requires digest verification **at the moment of delivery**, on the same terms as
   load-time verification. `load_phase_agents` already does exactly this for `AGENTS.md`
   ([agents.py:79-84](../../src/core/packs/agents.py#L79-L84)) — re-reads the bytes, re-hashes,
   compares to the pin. Skills need the identical treatment, in the same function, or the
   two verifications drift.
2. Assembly in `src/surfaces/` would put content-composition logic in a surface. Principle I
   is explicit that logic in the thin layer belongs in core; `bind_phase_agents` is 25 lines
   of pack-name resolution and recording, and it should stay that.
3. There is exactly one consumer seam — `run.phase_instruction`, read at
   [entrypoint.py:233](../../src/surfaces/dispatch/entrypoint.py#L233),
   [620](../../src/surfaces/dispatch/entrypoint.py#L620),
   [975](../../src/surfaces/dispatch/entrypoint.py#L975) and via `propose_agents.body` at
   [999](../../src/surfaces/dispatch/entrypoint.py#L999). Assembling upstream of that seam means
   no call site changes and no phase can be reached by an unassembled path.

**Alternatives rejected**: assembling in `bind_phase_agents` (layering, and the eval lane
loads phase content through `load_phase_agents` without going through the surface — the
suites would then score different bytes than production delivers, which is R9's trap);
a new `core/packs/skills.py` module (a second loader with a second digest check, for content
that is already `SkillPin` in the same manifest).

---

## R2 — Delivery order

**Decision**: manifest declaration order of `[[skills]]`, filtered to those bound to the
phase. AGENTS.md body first, then each bound skill, each under a fixed delimiter naming the
skill and its digest.

**Rationale**: FR-006 requires order "deterministic and derived from the manifest".
Declaration order is the only ordering the manifest already carries; sorting by name would
be equally deterministic but would silently reorder when a skill is renamed, and would put
`terraform-style-guide-security` before `terraform-style-guide` — general practice after
its own security appendix. `tomllib` preserves array-of-table order, and `PackManifest.skills`
is a `tuple`, so the order is already stable through parse.

AGENTS.md first because it is the phase's own instruction and the skills are practice it
draws on; FR-014's precedence rule (R8) is stated there and must be read before the content
it governs.

---

## R3 — How a binding is declared

**Decision**: a `phases` array on `[[skills]]`.

```toml
[[skills]]
name    = "terraform-style-guide"
path    = "skills/terraform-style-guide/SKILL.md"
version = "8c6573abbd21e8094fab8f538eb5f97db63133fd"
digest  = "fea8a0e…"
phases  = ["plan", "write", "judge"]
```

**Rationale**: FR-002 says the binding lives "beside the pin, version and digest that
already govern it" — that is the `[[skills]]` table. Absent `phases` means bound to nothing,
which keeps FR-011 (a phase bound to no skills is unchanged) true by default and makes the
Vault pack's current manifest valid with no edit.

**Reconciliation item for `/speckit-analyze`** — FR-007 names two refusals: binding a skill
to an unknown phase, **and** "binding a name no `[[skills]]` entry declares". Under this
shape the second is structurally unreachable: a binding *is* a `[[skills]]` entry, so there
is no name to dangle. The shape that makes it reachable is a `skills = [...]` array on
`[[agents]]`, which contradicts FR-002's "beside the pin". Two requirements in the merged
spec cannot both be satisfied by one shape. FR-002 is the load-bearing one (it is US3's
whole content and SC-004's measure), so this plan takes `[[skills]].phases` and records the
FR-007 clause as unsatisfiable-as-written rather than improvising a reading of it. The
equivalent guarantees are kept and specified in [contracts/pack-skill-binding.md](contracts/pack-skill-binding.md):
a `phases` entry that is not a `PhaseName` refuses `unknown_phase`; a `phases` entry naming a
phase with no `[[agents]]` pin refuses `skill_binding_unbacked`; a duplicate `[[skills]]`
name refuses `duplicate_skill`. **This is a spec change, not a plan decision — analyze must
send FR-007 back to clarify.**

---

## R4 — What "cannot be delivered whole" means (FR-009)

**Decision**: a fixed byte ceiling on the assembled instruction —
`INSTRUCTION_BUDGET_BYTES = 256 * 1024` — checked before delivery. Over it, the phase stops
with `instruction_too_large`. Never truncate.

**Rationale**: FR-009 must stop the run *deterministically and with the reason recorded*.
The only other candidate signal is the model provider rejecting an over-long prompt, and
that fails three ways: it is post-hoc (the run has already paid for the call), it is
provider- and model-specific (so two qualified cells disagree about whether the same pack
loads), and it is not available to the eval lane, so no row could assert it. A byte count
over content that is pinned by digest is the same number on every run, in every profile, on
every model — which is what makes it assertable.

**Why 256 KiB**: the largest assembly this pack can currently produce is Write —
4,805 + 6,926 + 4,872 = 16,603 bytes. 256 KiB is ~15× headroom, so no legitimate skill
adoption trips it, and it is far below any qualified cell's context window, so a refusal
means somebody bound something structurally wrong (a vendored directory, a corpus) rather
than that practice grew. The precedent for a fixed budget carrying its own reasoning is
`READ_BUDGET_BYTES` at [tool.py:44-49](../../src/core/authoring/tool.py#L44-L49), including
its warning: an unfixed threshold is one that gets raised until the corpus passes.

**Alternatives rejected**: token counting (needs a tokenizer per model — a model-specific
dependency in `src/core`, which Principle I forbids); no check at all (FR-009 is a
requirement); a per-cell limit read from the matrix (makes pack loading depend on model
binding, and a cell change would silently change which packs load).

---

## R5 — Where FR-017's stale-declaration check runs

**Decision**: in `load_packs`, after every pack in the set has registered, against the
complete registry. Not in `FilesystemPackLoader.load`.

**Rationale**: `PackLoader.load` is registry-blind by construction —
[loader.py:373](../../src/core/packs/loader.py#L373) takes only a manifest and a directory,
and `parse_manifest` / `validate_manifest` never see a `ToolRegistry`. FR-017 asks whether
"the registry **does** offer" a capability, which cannot be answered there.

`register_pack` has the registry but registers one pack at a time, so a check placed there
is **order-dependent**: pack B's declaration of `terraform_fmt` would refuse only if pack A
registered its `terraform_fmt` tool first. Order-dependent refusal is the defect
[isolation.py:9-11](../../src/core/packs/isolation.py#L9-L11) already refuses to ship for
ambiguous tool names — "load order changes without anybody deciding it did".

`load_packs` ([registration.py:130-147](../../src/core/packs/registration.py#L130-L147)) holds
the whole set and the registry after all registration. Checking there is order-independent
by construction. It keeps `load_packs`'s existing all-or-nothing contract: a stale
declaration refuses the whole set.

**What counts as "offered"**: a name in `registry.tool_names()` after the set registers, or
a key in `bindings.handlers`. The handler table is included because a capability with a
platform handler is one somebody has built — the declaration is stale from that moment, not
from whenever a pack gets round to declaring a tool for it.

---

## R6 — `terraform validate` is unavailable to the *registry*, not to the *platform*

**Decision**: the unsatisfiable declaration and the FR-017 check are scoped to the tool
registry — what a model may call inside a governed run. The eval lane is explicitly out of
that scope, and the plan says so in the phase instruction and in the PR text.

**Rationale**: this nearly shipped as a false statement. `terraform validate` **is** executed
by this repository — [write_gates.py:150-152](../../tests/evals_live/write_gates.py#L150-L152)
shells out to `terraform -chdir=… validate` as gate one of Write scoring, and
[write_gates.py:121](../../tests/evals_live/write_gates.py#L121) runs `terraform init` before it.
A PR body saying "this platform cannot run `terraform validate`" without qualification would
be contradicted by the repository's own eval lane, which is precisely the overstated-evidence
liability Principle IX names — inverted, but the same failure.

The true statement is narrower and still worth making: no registry tool exists for `fmt` or
`validate`, so **the authoring agent cannot run them on the branch it is proposing**, and the
run's own artefacts were never formatted or validated by the platform. The eval lane scores
*corpus* tasks against a *reference*, not this pull request's tree. The reviewer's action item
is unchanged; the sentence that produces it must be accurate.

**Consequence for FR-017**: the check must not treat "a subprocess in `tests/` invokes it" as
the registry offering it. Scoped to `registry.tool_names()` ∪ `bindings.handlers`, it does not
— `tests/evals_live` contributes to neither.

---

## R7 — The phase instructions have already absorbed the skill by hand

**Finding, not a decision.** This was not anticipated by the spec and it materially affects
SC-002.

`packs/terraform/agents/write/AGENTS.md` §"Required HashiCorp practice"
([write/AGENTS.md:69-85](../../packs/terraform/agents/write/AGENTS.md#L69-L85)) is a
hand-written condensation of most of `SKILL.md`. Rule by rule:

| Skill rule | Already in a phase `AGENTS.md`? |
| --- | --- |
| Two spaces, no tabs, align equals | Yes — Write:70 |
| lowercase_with_underscores, singular, `main` for one-of-a-kind | Yes — Write:71 |
| Every variable has `type` + `description`; secrets `sensitive` | Yes — Write:72-75 |
| Every output has `description` | Yes — Write:76 |
| Prefer `for_each` over `count`; `count` for on/off | Yes — Write:77 |
| Meta-arguments first, `lifecycle` last, args before blocks | Yes — Write:64-66 |
| Standard file names (`terraform.tf`, `variables.tf`, …) | Yes — Write:67, Research:27-28, Plan:27 |
| Never commit `terraform.tfstate`; keep `.terraform.lock.hcl` | Yes — Write:97, Write:61 |
| Version pinning; `~>` is a pin | Yes — Write:36-40, and encoded in the scorer |
| **`validation { condition, error_message }` blocks on variables** | **No — appears in no phase file** |
| **`default_tags` on the provider; `merge(local.common_tags, …)`** | **No** |
| **`terraform.tf` holds *only* version requirements; `providers.tf` holds provider blocks** | **Partially — names listed, purposes not assigned** |
| **Aliased providers for multi-region** | **No** |

**Why this matters**: SC-002 requires "a style rule the vendored skill states and the unaided
model does not reliably follow", measured with the binding present and again with it removed.
Any rule in the left column's upper block is already delivered by the phase instruction, so
removing the skill binding changes nothing and the measurement is void — a rule that passes
with the skill absent is not evidence, as the spec's own Independent Test says.

**Consequence**: SC-002 must be measured on a rule from the bold rows. The plan selects
**variable `validation` blocks** — stated twice in `SKILL.md` examples
([SKILL.md:48-57](../../packs/terraform/skills/terraform-style-guide/SKILL.md#L48-L57) and
[SKILL.md:153-163](../../packs/terraform/skills/terraform-style-guide/SKILL.md#L153-L163)),
absent from all five phase files, textually detectable, and not something a base model emits
unprompted. This becomes a new property in
`tests/evals_live/authoring_properties.py` and a corpus task; see
[contracts/conformance-phase-skill-binding.md](contracts/conformance-phase-skill-binding.md) row E2.

**Out of scope, recorded**: the duplication itself. A pack restating adopted practice is not
forbidden by ADR-0004, and de-duplicating five promoted instruction files is a second feature
with its own re-qualification. It is named here so the next person does not rediscover it.

---

## R8 — The skill and the Write instruction disagree, and this feature puts them in one context

**Finding, and a decision.**

`SKILL.md` §Version Pinning ([SKILL.md:230-236](../../packs/terraform/skills/terraform-style-guide/SKILL.md#L230-L236))
shows `required_version = ">= 1.14"` and says to use "the latest minor version of Terraform".

`packs/terraform/agents/write/AGENTS.md` §Pins ([write/AGENTS.md:36-40](../../packs/terraform/agents/write/AGENTS.md#L36-L40))
says: "`~>` is a pin. `>=`, `>`, `<`, `<=`, `*`, or a missing `version` are not… fix every
floating provider or module constraint this change touches."

The eval-lane detector agrees with the phase file and against the skill:
`no_floating_version_constraint` in
[authoring_properties.py:60-72](../../tests/evals_live/authoring_properties.py#L60-L72) classifies
`>=` as floating, and its docstring notes the detector was *corrected* to stop scoring `~>` as
floating because doing so "scored HashiCorp practice as the failure the `pin_the_provider`
task exists to catch".

Today these two documents never meet. This feature's entire purpose is to put them in one
model context, where they contradict each other on the same line of HCL — and the phase whose
output is scored by a detector that will mark the skill's own example as a failure.

**Decision**: FR-014's precedence sentence is widened from capabilities to content. The phase
instruction states both precedences:

1. **Capability** — the registry bounds what can be done; adopted practice does not widen it
   (FR-014 as written).
2. **Content** — where this file and a delivered skill differ on a concrete rule, this file
   governs, and the difference is not a licence to do neither.

Rule 2 is not in the spec. It is required by FR-001 + FR-012 together the moment those two
documents share a context, and without it the most likely observable outcome of this feature
is a *regression* on `required_version` — the run's own scorer marking output that followed
delivered practice. Naming which document wins is also the only option ADR-0004 permits: the
skill's bytes may not be edited.

**Flagged for `/speckit-analyze`**: this widens FR-014 and adds an acceptance obligation US1
does not carry. It is recorded as a plan decision here and needs a spec sentence.

---

## R9 — What "re-qualified" has to score (FR-013 / SC-007)

**Decision**: `score_phase_agents_case` and `score_build_agents_case` must score the
**assembled** instruction — `AGENTS.md` plus the skills bound to that phase — not the
`AGENTS.md` file alone.

**Rationale**: both scorers are mechanical (ADR-0063) and today check only that the
referenced path exists and is non-empty
([phase_agents_corpus.py:135-157](../../src/core/evals/phase_agents_corpus.py#L135-L157)).
SC-007 says no phase ships bound to a skill "whose **combined** instruction content has not
passed both suites". A scorer that reads `packs/terraform/agents/write/AGENTS.md` and stops
has not looked at the bytes the model will receive. Passing it and calling the phase
re-qualified is a gate that greens without asserting anything about the change — ADR-0047's
"a passing stub is worse than a missing one", which this spec cites as its own precedent.

The corpus case keeps `instruction_ref` as the `AGENTS.md` path; the scorer resolves the pack
from that path and assembles the same way production does, through `load_phase_agents`. That
shared path is why R1 puts assembly in core: two assembly implementations would let the suite
pass on bytes production never sends.

**Injection lens**: `promote_phase_agents` lenses each `AGENTS.md`
([promotion.py:294-299](../../src/core/evals/promotion.py#L294-L299)); `promote_skill` lenses each
skill. Combined content is therefore lensed in halves, and this feature adds no new content —
only a new adjacency. No third lens pass is added. Recorded because "we lensed the parts" and
"we lensed the whole" are different claims and the contract should say which one holds.

---

## R10 — Which unsatisfiable recommendations reach the pull request

**Decision**: every declared unsatisfiable recommendation of every skill bound to **any**
phase of the bound pack. Manifest-derived, no run state consulted.

**Rationale**: this reconciles the tension between FR-016 ("a run whose **phases were
bound**") and FR-018 ("identical across runs, derived from the manifest alone"). A set that
depends on which phases ran would vary between runs; a set that ignores phases entirely would
name practice from a skill this pack adopted but bound to nothing, which US2 is at pains to
keep distinguishable.

They coincide, because **a run that opens a pull request has necessarily run all five phases**:
`open_proposal` is reached only after Propose binds
([entrypoint.py:1543](../../src/surfaces/dispatch/entrypoint.py#L1543)), which is reached only
after Judge permits publication
([entrypoint.py:968](../../src/surfaces/dispatch/entrypoint.py#L968)), which follows Write, Plan
and Research. So "bound to a phase that ran" and "bound to any phase" are the same set at the
only moment the question is asked. The implementation reads the manifest and never the
progress record, which is what makes FR-018 structurally true rather than carefully
maintained.

**Where it lands in the body**: a new `## Adopted practice not carried out` section, between
`## Provenance` and `## Limits` in `Proposal.render`
([proposal.py:280-291](../../src/core/authoring/proposal.py#L280-L291)) — after where the content
came from, before what is not covered, matching the ordering rationale already recorded there.
Not folded into `limits`: `limits` is `DERIVATIVE_LIMIT + disclosures` and disclosures are
run-derived (truncated reads), while this text must be run-independent.

---

## R11 — The record that distinguishes delivered from present (FR-005)

**Decision**: two records, because one cannot answer both halves.

1. **`content_pins` at `RUN_START`** gains binding in the key:
   `terraform/skills/terraform-style-guide@plan+write+judge` for a bound skill,
   `terraform/skills/<name>@unbound` for an adopted-but-inert one. Static, manifest-derived,
   written once at start.
2. **Per-phase delivery** is recorded as phases actually bind, keyed
   `terraform/agents/write@0.2.0+terraform-style-guide`.

**Rationale**: `content_pins` is a `RUN_START` payload
([run.py:344-345](../../src/core/run.py#L344-L345)), written before any phase executes. It
therefore *cannot* satisfy US2 acceptance 2 — "a Build that stopped before the write phase…
a skill bound only to `write` is not recorded as having shaped the run" — because at
`RUN_START` no phase has run. `RUN_START` can honestly say what is bound; only a later record
can say what was delivered.

**The gap this exposes**: `run.agent_content_pins` is set by `bind_phase_agents`
([phase_agents.py:41-43](../../src/surfaces/dispatch/phase_agents.py#L41-L43)) and **is never
written anywhere**. `_payload_with_progress`
([entrypoint.py:180-192](../../src/surfaces/dispatch/entrypoint.py#L180-L192)) carries only
progress; no checkpoint, no audit event, no result body carries it. Per-phase instruction pins
have been in-memory-only since 049. So US2 is not "add a field to an existing record" — it is
"start recording the per-phase pins at all", and the 049 pins come along. Task ordering must
reflect that.

**Alternatives rejected**: a third pin map (a third name→digest record on the same run, with
the same ordering question, is the fragmentation Principle VII names); recording delivery
inside `content_pins` (impossible — wrong point in the run).

---

## R12 — The Vault pack

**Decision**: no bindings; `packs/vault/pack.toml` gains no `phases` key and no
`[[skills.unsatisfiable]]` table. Its single skill, `vault-secret-access`, stays adopted and
inert, and is recorded `@unbound` by R11.

**Rationale**: the spec's assumption — in scope for the mechanism, not for new bindings. It is
also the live fixture for US2 acceptance 1 (a pack with a bound skill and a pack with an
unbound one must be distinguishable) and for FR-011 (a phase bound to no skills behaves
exactly as today), so it is load-bearing as-is and must not acquire a binding by tidiness.

Vault's five phase files must still be checked against FR-010: none may claim practice from a
skill it is not bound to. Grep confirms they do not — the "Practice is this file and the
pinned skills…" sentence appears only in the Terraform pack.

---

## Resolved unknowns

| Unknown | Resolved by |
| --- | --- |
| Where assembly happens | R1 — `core/packs/agents.py` |
| Deterministic order | R2 — manifest declaration order, AGENTS.md first |
| Manifest binding syntax | R3 — `[[skills]].phases` (+ FR-007 reconciliation item) |
| FR-009's "whole" | R4 — `INSTRUCTION_BUDGET_BYTES = 256 KiB`, refuse never truncate |
| FR-017 check location | R5 — `load_packs`, after the whole set registers |
| What "the registry offers" excludes | R6 — the eval lane; declaration text scoped accordingly |
| SC-002's measurable rule | R7 — variable `validation` blocks |
| Skill/instruction content conflict | R8 — content precedence stated in the phase file |
| What re-qualification scores | R9 — the assembled instruction, via the production path |
| PR recommendation set | R10 — all skills bound to any phase; manifest-derived |
| Delivered-vs-present record | R11 — two records; per-phase pins must start being written |
| Vault | R12 — mechanism only, no bindings |
