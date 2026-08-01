# Implementation Plan: A question gets an answer, and the answer never acts

**Branch**: `spec/024-portal-answering` | **Date**: 2026-08-01 | **Spec**: [spec.md](./spec.md)

**Scope**: Grounded guidance only. Estate-state answering is a separate feature (clarify Q1).

## Summary

The portal can start runs and hold threads; it cannot answer anything. This adds one path from a
person's question to a cited answer, and nothing else.

**Research changed what this feature is, twice.** The spec described a capability to build beside
existing gates. In fact:

- **Neither eval scorer touches a product path.** `FixtureScorer` replays an authored string;
  `LiveModelScorer` asks a vendor directly. That is why four suites are green over a capability
  that does not exist, and it means a **third scorer** — one that drives the answering path with a
  fixture provider — is the thing that makes those gates mean anything.
- **The guidance corpus is not in this repository.** The eval cases cite live external URLs inside
  authored strings; there is nothing to resolve a citation against. Obtaining and pinning it is the
  largest single piece of work here, and the spec understated it as "settled".

Everything else is reuse: `ask` is already a role, `FIXTURE_PROVIDER` already exists, and the
never-acts guarantee is satisfied by what the answering path does **not** hold.

## Technical Context

**Language/Version**: Python 3.12.

**Primary Dependencies**: the existing provider adapter path (`pydantic-ai`) for the live lane. **No
new dependency for the blocking lane** — it drives a fixture.

**Storage**: the corpus as a vendored, pinned artifact with provenance. **No database changes.**

**Testing**: pytest; the existing eval machinery with a new `Scorer`; conformance rows across API
and MCP.

**Target Platform**: the served API surface; the portal as a thin client.

**Project Type**: governed agent runtime.

**Performance Goals**: none stated. An answer is bounded by a person's patience and a provider's
latency, neither of which this feature controls.

**Constraints**: the blocking lane must run with **no vendor credential** (FR-016). Asking must
reach **no effecting tool** (FR-006), enforced by what the path holds rather than by prompt.
Citations must resolve against the pinned corpus (FR-002). The corpus has **no version metadata**,
so change detection is content-based (FR-014).

**Scale/Scope**: one answering path, one new scorer, one vendored corpus, two eval suites
re-pointed, one API operation, one parity row.

## Constitution Check

| Principle | Verdict | Notes |
| --- | --- | --- |
| I — Build Glue Only | **Pass** | The answering path is core; the provider call stays behind the existing adapter seam, as 020's chooser does. No framework enters core. |
| II — Total Interception; One Governed Tool Layer | **Pass, and by absence.** | The answering path reaches no tool at all. It is not a second tool layer; it is a path with none — which is what makes FR-006 structural rather than a rule. |
| III — Fail-Closed | **Pass, and implicated.** | An unreachable provider **fails** rather than answering (clarify Q3). An unqualified matrix cell refuses **before** any provider call (FR-009). FR-011a forbids a model-less fallback, because a second path no gate scores is how this feature's own gates reached their current state. |
| IV — Zero Standing Credentials | **Pass** | Asking carries no authority grant and manufactures none. The answer is bounded by the corpus, not by a credential. |
| V — Sealed Core, Versioned Seams | **Pass, no review expected.** | No audit schema change, no registry change, no adapter contract change. `Scorer` gains an implementation — that protocol is a published seam and adding to it is what it is for. **If an audit event type turns out to be needed, that changes this verdict and must be raised.** |
| VI — Lean by Default | **Pass, with the corpus noted.** | No new service or store. The corpus is vendored content, following `packs/*/skills/` rather than inventing a mechanism. |
| VII — Anti-Fragmentation | **Pass, and it is the design.** | Third `Scorer` rather than a parallel harness; `FIXTURE_PROVIDER` reused rather than a second fixture concept; corpus pinned the way skills already are. |
| VIII — Eval-Gated Promotion | **Pass, and this is where it becomes load-bearing.** | Every prior model call has been an eval harness asking directly. This is the first **product** path to call a provider, which is what turns Principle VIII from advisory into the thing standing between a model and a person. |
| IX — Evidence Over Claims | **Pass, and it is the subject.** | An answer that cites nothing is the failure this platform is built against. FR-003 makes declining the required behaviour rather than the polite one. |
| X — The Decision Record Governs | **Pass, no amendment.** | ADR-0039 decided *ask answers, it never acts* before this existed and is **consumed unchanged**. ADR-0034/0033 place the operation and grow the parity row. ADR-0004's supply chain gains a second subject in the corpus. |

**Gate result**: **PASS — proceed to Phase 0.**

**One obligation**: FR-015/SC-008 — the two suites must end up scoring product output. It is the
requirement most likely to be dropped as "they already pass", and dropping it leaves this feature
having built an answering path beside gates that still score authored strings.

## Project Structure

### Documentation (this feature)

```text
specs/024-portal-answering/
├── plan.md · research.md · data-model.md · quickstart.md
├── contracts/conformance.md
├── checklists/requirements.md
└── spec.md          (tasks.md — /speckit-tasks)
```

### Source Code (repository root)

```text
src/core/answering/          # NEW — the path. Holds a corpus and a provider; no tools, no grant
src/core/evals/scoring.py    # a third Scorer that drives the answering path
src/surfaces/api/            # the ask operation
src/surfaces/mcp/            # the same operation, for parity (ADR-0033)
packs/*/corpus/              # NEW — the pinned corpus, with PROVENANCE.md beside it
packs/*/evals/               # citation_accuracy + must_decline re-pointed at product output
```

**Structure Decision**: the answering path lives in **core** and holds exactly two things — the
corpus and an injected provider. It holds **no tool registry and no authority grant**, which is how
FR-006/FR-008 are satisfied: acting later requires *adding* a dependency, visible in review. This
mirrors 021's compiler, which holds no query and no credential and therefore cannot widen scope.

## Complexity Tracking

*No Constitution Check violations.*

| Decision | Why | Alternative rejected because |
|---|---|---|
| A third `Scorer` rather than regenerating recordings | The suite scores product output, deterministically, with no credential | Live-generated recordings are a snapshot of one model on one day and need a paid credential to refresh |
| Corpus vendored with provenance | `packs/*/skills/` already does exactly this, and ADR-0004 wants a real subject | Fetching at answer time makes every answer depend on a third party being up, and makes "pinned" untrue |
