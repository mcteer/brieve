# Phase 0 Research: Capability Packs and Eval Gates

**Feature**: `specs/013-capability-packs` | **Date**: 2026-07-29

Three findings and twelve decisions. The findings came from reading the shipped code, which
is this repository's habit and has paid every time.

---

## Findings

### F1 — The entrypoint names the line this feature replaces

`src/surfaces/dispatch/entrypoint.py` builds its registry by hand and says so:

> *"Hardcoded here because the real toolset arrives with capability packs, which are a
> later feature. When they land, this is the line they replace."*

A previous feature left a signpost pointing at this one. Worth recording because it means
the pack seam's insertion point is already identified and already justified — the work is to
replace three `registry.register` calls with a loader, not to find where they should go.

### F2 — `risk_class` is in the glossary and nowhere in the code

The glossary defines it — *"per-tool classification: read | write | destructive |
secret-touching. Drives approval and plan-gate requirements"* — and `ToolRegistration`
carries `product_mode`, `product`, `product_action`, `repeatable`, and `observer`, but no
risk class. **Nothing in this platform has ever known how dangerous a tool is.**

That has been harmless while every tool was `echo`. It stops being harmless the moment a
pack declares a tool that deletes infrastructure, which is the first thing a Terraform or
Vault pack does. The field is additive and defaulted, so it is a small change — but it is
the difference between a pack manifest that *declares* risk and a platform that *knows* it.

### F3 — There is no approval audit event to be confused with

`AuditEventType` has no approval member; `core/approvals/types.py` is a Protocol and two
doubles, with no event of its own. So FR-015's requirement — that the trail distinguish a
model gate from a human approval — cannot be met by *adding a distinction to an existing
pair*, because the pair does not exist yet.

This is easier than expected and worth stating so nobody looks for the missing half: adding
`MODEL_GATE` establishes the distinction unilaterally, and when human approvals gain their
own event later, the two are already separate rather than needing to be untangled.

---

## Decisions

### D1 — The judge regress resolves to a human-labeled seed set

**Decision**: the first judge is qualified by scoring it against **`evals/seed/`** — a set of
verdicts labelled by a person, checked into the repository, reviewed like code. Every
subsequent judge is qualified by a judge that was itself qualified, chaining back to the
seed. **ADR-0052** records it.

**Rationale**: the spec bounded three options and forbade the implicit answer. Of the three:

- A **human-labeled seed set** terminates, and terminates *inside* this repository. The
  authority is a person's judgement, visible in a diff, reviewable, and revisable through
  the same process as anything else.
- **External attestation** terminates too, but by importing trust from something this
  platform cannot inspect — which is precisely the move Principle IX ("a claim that cannot
  be reconciled to a record is a liability") is written against.
- A **declared floor** is honest about being arbitrary, and that is its problem: it makes
  the root of the entire gate chain a thing nobody can argue with, which is how a governance
  control becomes a formality.

The seed set is small, boring work and it is the only option whose authority anyone can
check. **The regress terminates at a human, which is where it should terminate.**

**Cost, stated**: the seed set is a maintenance obligation. It must grow as the judge suite
grows, and a seed set that stops being representative silently weakens every gate above it.
ADR-0052 records that obligation rather than leaving it implied.

### D2 — A pack is a manifest plus content on disk, verified by digest

**Decision**: `packs/<name>/pack.toml` declares the pack; `skills/` and `evals/` hold its
content. The manifest records a digest for every content file, and loading verifies it.

**Rationale**: Principle VI — content is files, not a service. The digest is what makes
"pinned" (ADR-0030) checkable rather than asserted: a skill whose bytes changed without its
pin changing is exactly the ungated drift Principle VIII exists to stop, and it is invisible
without a hash.

**Alternatives**: an installable package (rejected — a distribution mechanism for content
that never leaves the repository, and it would put product knowledge inside the Python
package tree); a database (rejected — an operated component for files).

### D3 — `packs/` lives at the repository root, not under `src/`

**Decision**: as above.

**Rationale**: Principle I says the core stays product-blind. Putting `packs/terraform` in
the Python package tree would ship Terraform knowledge inside the distribution whose whole
claim is that it has none. Root-level `packs/` also makes SC-002 (`zero core modules name a
product`) trivially inspectable — the check is "does anything under `src/core` mention
terraform or vault", and content living elsewhere means the answer stays no.

### D4 — Loading is a seam: `PackLoader` protocol, filesystem implementation

**Decision**: `PackLoader` with `FilesystemPackLoader`, following the 011/012 discipline —
a protocol, a real implementation, and an in-memory one for hermetic rows.

**Rationale**: every hermetic row that needs a pack should not need a directory. It is also
what lets the "two packs load side by side and neither leaks" row (SC-012) run without the
filesystem.

### D5 — The Qualified Model Matrix is a control-plane record

**Decision**: cells live in Vault at `harness-authority/data/model-matrix`, read the way
010 reads ceilings — operator-authored, read-only to runs, refused loudly when absent.

**Rationale**: a matrix cell is an *authorization fact*: it says a definition may use a
model for a role. That is the same kind of thing as a ceiling, it is authored by the same
people, and it must be un-widenable from inside a run for the same reason. Putting it in the
repository would make it a code change, which sounds stricter and is worse — it would mean
qualifying a model requires a deploy, and the pressure to skip that is exactly how
auto-tracking gets reinvented.

**Alternatives**: in-repo TOML (rejected, above); Postgres (rejected — runs can write to
Postgres, and this must be read-only to them).

### D6 — Binding-map validation happens at definition time and again at run start

**Decision**: FR-009 says definition time. This does it **twice** — once when a definition
is registered, and once when a run resolves its binding — and the second is not redundant.

**Rationale**: a cell can be *withdrawn*. A model deprecated, a suite regressed, a cell
pulled after a bad result — and the definition that pinned it is still sitting in the
registry. Validating only at definition time would let a withdrawn cell keep running because
nothing re-asked. This is the same reasoning that makes 010 resolve a ceiling per run rather
than caching it.

### D7 — Fallback is a search over qualified cells, and stopping is the default

**Decision**: when a pinned cell is unavailable, search the matrix for another qualified
cell for the same (pack, role). Take it, and record the fallback as an audit event. If none
exists, **stop the run with the reason recorded** — never proceed unqualified, never proceed
silently.

**Rationale**: FR-010, and the constitution's own wording ("fallback only to another
qualified cell — recorded — or the run stops with the reason recorded"). The recording is
the load-bearing half: a fallback nobody can see is a definition that does not describe what
ran.

### D8 — The four gates are suites over recorded cases; scoring is a seam

**Decision**: each suite is a set of cases with expected outcomes. `Scorer` is a protocol:
`FixtureScorer` replays a recorded response, `LiveModelScorer` calls a provider. The
blocking lane uses fixtures; `@pytest.mark.live_model` uses the provider.

**Rationale**: the spec's clarification. The seam is what makes "the gate machinery is real
even when the substrate is a recording" true rather than aspirational — the suites, the
thresholds, and the refusals are identical in both lanes, and only the scorer differs.

**The cost, restated where it will be read**: a cell qualified by `FixtureScorer` is
qualified against a recording. `contracts/conformance-packs.md` records per cell which
scorer qualified it, and SC-013 asserts no cell is recorded without that.

### D9 — Skill promotion requires all three checks, and the injection lens is a real check

**Decision**: `promotion.py` refuses unless provenance verifies (the pinned commit exists
upstream and the content hashes to what was recorded), the injection lens passes, and the
evals pass. The injection lens is a pattern-based check over skill content for
instruction-shaped text targeting the agent — attempts to override system instructions,
exfiltrate context, or redirect tool use.

**Rationale**: ADR-0004 names all three; two of three is a supply chain with a hole. The
lens is deliberately pattern-based rather than model-scored: a model-scored lens would make
promotion depend on a model, which would need a qualified cell, which needs the gates to
have run — a second regress, and one with no seed set to terminate it.

**Honest limit**: a pattern-based lens catches the known shapes and not novel phrasing. It
is recorded as a floor rather than a guarantee, and the human review ADR-0004 also requires
is what covers the rest.

### D10 — Competency tiers bound workflow selection, not tool access

**Decision**: a tier restricts which **workflows** a definition may run. Tool access stays
governed by the ceiling.

**Rationale**: ADR-0044's disjointness rule — no rule duplicated across engines. If a tier
also restricted tools, the same question ("may this agent call `apply`?") would have two
answers from two mechanisms, and they would eventually disagree. The ceiling answers about
tools; the tier answers about *composition*, which nothing else answers about.

### D11 — Retrieval telemetry is a counter, not a store

**Decision**: aggregate retrieval targets — what was looked up, how often — emitted as
telemetry, not written to a new table.

**Rationale**: Principle VI ("nothing blocking that could be a library, a signed cache, or
an async emitter"). ADR-0031 wants the *ranking*, and a counter over OTel gives it without a
new store. It is also read at a lifecycle review rather than by a run, so nothing depends on
it being queryable in-process.

### D12 — Two audit additions, and the second is the interesting one

**Decision**: `MODEL_GATE` for a model verdict that gated a step, and `MATRIX_FALLBACK` for
D7's recorded fallback.

**Rationale**: FR-015 requires the trail to distinguish a model gate from a human approval,
and F3 found there is no approval event to be confused with — so this establishes the
distinction rather than repairing it. `MATRIX_FALLBACK` is separate from `MODEL_GATE`
because they answer different questions: one is "a model decided something", the other is
"the model that ran was not the model that was pinned", and an investigator looking for the
second should not have to filter the first.

---

## Resolved unknowns

All spec markers were resolved by the clarification session. The technical unknowns — where
the matrix lives (D5), how loading works (D2/D4), how the regress terminates (D1), and what
the scoring seam looks like (D8) — are resolved above.
