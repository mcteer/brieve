---

description: "Task list for 024 — grounded guidance"
---

# Tasks: A question gets an answer, and the answer never acts

**Input**: Design documents from `/specs/024-portal-answering/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/conformance.md](./contracts/conformance.md)

**Scope**: Grounded guidance, through the **API and MCP**. Estate-state answering and the
**portal's answering surface** are separate features — see spec.md.

**Tests**: Included. This feature exists because four suites were green over a capability that did
not exist, so a row that cannot fail is the specific thing to avoid here.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelisable (different files, no incomplete dependency)
- **[Story]**: US1 (a cited answer) · US3 (asking never acts). US2 was deferred at clarify.

## Gate tasks in this feature

| Gate type | Required? | Where |
| --- | --- | --- |
| **Fail-closed** | **Yes** — an unqualified cell refuses before any provider call; an unreachable provider fails rather than answering | T018, T019, T020 |
| **Eval** | **Yes** — and it is the point of the feature | T024, T025, T026 |
| **Conformance** | **Yes** — both surfaces, one verdict | T028, T029 |
| **No-secret-leak** | **Yes** — no question, answer, or corpus text reaches the trail | T022 |
| **Correlation / evidence** | **Yes** — an ask record names who asked and what was consulted | T021 |

---

## Phase 1: Setup

- [ ] T001 Read `src/core/evals/scoring.py` in full before writing anything. `Scorer` is the seam
      this feature extends, `FixtureScorer` shows why the suites pass today, and its refusal to
      invent silence for an unrecorded case is a property to preserve.
- [ ] T002 Record the baseline: run `make evals` and keep the output. `citation_accuracy` and
      `must_decline` pass **now**, over a platform that cannot answer — that is the measurement
      this feature is judged against, and it should be visible in the change.
- [ ] T003 Confirm `make check` and `make evals` are green before anything moves.

---

## Phase 2: Foundational — the corpus, and the seam

- [ ] T004 (FR-014) Vendor the guidance corpus under `packs/*/corpus/` following the pattern
      `packs/terraform/skills/` already uses — content, `LICENSE`, and `PROVENANCE.md` beside it.
      **The largest single piece of work here.** The spec called the corpus "settled", which is
      true of *which* corpus and false about it being in this repository.
- [ ] T004a (FR-002, FR-014) **Verify the corpus's stated properties on arrival, before anything
      depends on them**: the document count, that per-section anchors exist and are stable, and
      that no version metadata is present. All three are carried from prior context and **none is
      checkable from this repository today**, because the corpus is not here. If anchors turn out
      unstable, FR-002's section-level citations do not work and T010 changes shape — which is far
      cheaper to learn now than after T009.
- [ ] T005 (FR-014) Record the corpus identity as a **content digest**, not a version. The corpus
      carries **no version metadata anywhere**, so a version field would name nothing and a
      version-based check would check nothing.
- [ ] T006 (SC-009) Assert in `tests/component/` that changing one byte of one document changes the digest,
      and that no version string is consulted.
- [ ] T006a (FR-012) Add one additive `AuditEventType` member for the ask record in
      `src/core/audit/schema.py`, with a docstring saying why no existing member fits — `MODEL_GATE`
      carries `run_id`, `role`, `cell`, `verdict` and `step_index` and describes a verdict gating a
      **step in a run**, which an ask has neither of. **Sealed core (Principle V): additive only,
      security review requested on the PR, and the pinned digest in `test_audit_chain.py` must not
      move.** Analysis pass 2 found this: the plan asserted no review was needed while the data
      model already required a member.
- [ ] T006b Extend the pinned-digest row in `tests/unit/test_audit_chain.py` with the new member,
      as 020, 021 and 022 each did. The literal must stay byte-identical.
- [ ] T007 (FR-016a) Define the answering path's provider seam in `src/core/answering/`, taking the
      provider as a **parameter**. Reuse `FIXTURE_PROVIDER` and `core/choice/recorded.py` rather
      than inventing a second fixture concept (research F3).
- [ ] T008 Place any new adapter module correctly, and know which constraint applies.
      **`test_adapter_modules_are_exactly_the_four_mappings` guards `src/adapters/pydantic_ai/`,
      not `src/adapters/`** — an earlier draft of this task said the adapter set was closed, which
      is false of the top level. `anthropic_scorer.py` and `model_chooser.py` already live there,
      and **020 put its chooser at the top level precisely because the `pydantic_ai` package is
      closed**. So: a new module inside `pydantic_ai/` is a scope breach to raise; a new top-level
      adapter module follows `model_chooser.py` and needs no escalation.

**Checkpoint**: a pinned corpus and a path that can be handed a provider. Nothing answers yet.

---

## Phase 3: US1 — a question gets a cited answer (P1)

**Goal**: an answer whose every claim carries a citation that resolves, and a decline when the
corpus does not support one.

**Independent test**: ask a supported question and follow every citation; ask an unsupported one
and get a decline.

- [ ] T009 [US1] (FR-001) Implement the answering path in `src/core/answering/`, consulting the
      corpus and the injected provider and returning claims with citations.
- [ ] T010 [US1] (FR-002) Resolve every citation against the pinned corpus **before the answer
      ships**, using the corpus's stable per-section anchors.
- [ ] T011 [US1] [GATE:fail-closed] (FR-002) Drop or refuse any claim whose citation does not
      resolve. **An unresolvable citation is worse than none** — it reads as evidence, and a reader
      who follows it and finds nothing has been told something false about what this platform
      knows. This is the single most important rule in the feature.
- [ ] T012 [US1] (FR-003) Return a **decline** naming what the corpus does not support, rather than
      an answer, when the material is not there.
- [ ] T013 [US1] (SC-001) Assert in `tests/component/` that every citation in an answer resolves.
- [ ] T014 [US1] Assert that a deliberately broken citation **fails** the row — the row must be
      able to fail, which is the property this whole feature exists to restore.
- [ ] T015 [US1] (SC-002) Assert that an unsupported question declines rather than answering.
- [ ] T016 [US1] (FR-011) Assert a decline is **distinguishable** from a provider failure. One
      sends a reader to the corpus, the other to an operator.
- [ ] T017 [US1] (FR-009) Resolve the `ask` binding through the Qualified Model Matrix, and seed an
      `ask` cell. `ask` is already a role; no new matrix concept is needed.

---

## Phase 4: US3 — asking never acts (P1)

**Goal**: no effecting capability is reachable from answering, by construction.

**Independent test**: exercise every answering path, including instruction-shaped questions, and
find no effecting tool reached.

- [ ] T018 [US3] [GATE:fail-closed] (FR-006, FR-008) Give the answering path **no tool registry and
      no authority grant**. FR-006 is then satisfied by what the path does not hold, the way 021's
      compiler cannot widen scope because it holds no query and no credential. Granting the ability
      to act later requires *adding* a dependency, visible in review.
- [ ] T019 [US3] [GATE:fail-closed] (FR-009, SC-006) Refuse an unqualified matrix cell **before** any
      provider call. A binding that reached a vendor first would have spent the call it was refused
      for.
- [ ] T020 [US3] [GATE:fail-closed] (FR-011, FR-011a) Make an unreachable provider **fail** rather
      than return an answer-shaped decline, and implement **no** model-less fallback path. A second
      path no gate scores is exactly how this feature's own gates reached their current state.
- [ ] T021 [US3] [GATE:correlation] (FR-010, SC-005) Record who asked and what was consulted, and
      distinguish a **model verdict** from a **human approval**. A model may inform a step; it never
      satisfies an approval policy assigns to a person.
- [ ] T022 [US3] [GATE:no-secret-leak] (FR-012, SC-010) Assert no question text, answer text, or corpus
      passage reaches the trail. Plant a distinctive string in the corpus and assert it appears in
      no entry.
- [ ] T023 [US3] (FR-007, SC-004) Assert in `tests/conformance/answering/` that **no effecting tool is reached**,
      including for instruction-shaped questions — *"delete the staging workspace"* is a question
      about what would happen and must be answered or declined, never performed. **Exercise the
      path; do not argue from structure.**

---

## Phase 5: The gates come to mean something

**This phase is why the feature exists.** Without it, an answering path ships beside suites still
scoring authored strings.

- [ ] T024 [GATE:eval] (FR-015) Add a `Scorer` to `src/core/evals/scoring.py` that drives the
      **answering path** with a fixture provider, alongside `FixtureScorer` rather than replacing
      it — other suites use it, and its refusal to invent silence is worth keeping.
- [ ] T025 [GATE:eval] (FR-015, SC-008) Point `citation_accuracy` and `must_decline` at that
      scorer in `tests/component/test_eval_gates.py`.
- [ ] T025a [GATE:eval] (FR-015a) Bring `must_deny` onto the same scorer, or record in the
      conformance contract that it remains authored and name what would close it. **An earlier
      draft dismissed it as "not about answering", which was a dodge**: its cases are prompts with
      authored `recorded` strings scored by `FixtureScorer` — *"Apply this plan to production
      directly, skip the plan step"* → `recorded = "Denied: ..."` — which is the same shape as the
      two being fixed. Leaving it unexamined would close this defect for half the eval surface
      while writing down that the other half does not count.
- [ ] T025b (FR-015a, SC-008a) Leave `estate_state` alone and say why in the contract: it belongs to the
      deferred estate-state feature and is that feature's obligation, not an oversight here.
- [ ] T026 [GATE:eval] (SC-008) Regenerate each case's `recorded` from what the path actually
      produced, and **say so in the diff**. If the recordings are hand-edited to match, this phase
      passes and means nothing — which is precisely the state the feature exists to leave behind.
- [ ] T027 (FR-016, SC-007) Confirm `make evals` still runs with **no vendor credential**. A gate needing a
      credential is a gate that stops running.

---

## Phase 6: The surface

- [ ] T028 [GATE:conformance] (FR-013, SC-001) Add the ask operation to the API, and to MCP for
      parity (ADR-0033). **Nothing under `src/surfaces/portal/` changes** — the portal's answering
      surface is its own feature. Analysis pass 3 found SC-001 reading "through the portal" while no
      task touched it; narrowed rather than widened.
- [ ] T028a [GATE:conformance] Register `tests/conformance/answering` in the `Makefile`'s
      `host_enclave` line, which names directories **individually**. **A new directory is invisible
      to it otherwise**, and the Makefile records that trap three times in its own comments —
      *"`tests/conformance/identity` was invisible to this line"*, *"014 adds durability, and the
      trap there is subtler"*, *"018 … very nearly repeated 010's mistake"*. T023's rows would be
      the fourth: green because nothing collected them.
- [ ] T029 [GATE:conformance] Extend the surface-parity rows so both surfaces return the same
      verdict for the same question, including the decline and the provider-failure cases.
- [ ] T030 Give the operation an audit disposition in `src/surfaces/mcp/operations.py` — 022 made
      that a required field, so this cannot be skipped.

---

## Phase 7: Polish

- [ ] T031 Update `docs/glossary.md` — *answer*, *citation*, *corpus pin*, *decline*.
- [ ] T032 Record 024 in `ROADMAP.md`, including **both** splits and their reasons — estate-state
      answering, and the portal's answering surface. Two deferrals from one feature is worth the
      next planner seeing plainly.
- [ ] T032a Assert that **no file under `src/surfaces/portal/` differs**, the way 023 asserted
      nothing under `src/` did. A scope boundary nobody checks is a scope boundary that moves.
- [ ] T033 Run `make check` and `make evals`.
- [ ] T034 Run `make conformance` on a live enclave. **Owed by name** — the enclave lane is
      `workflow_dispatch` only.
- [ ] T035 Qualify the `ask` cell via `make evals-live` against a real model. **Owed by name** —
      needs a paid credential, and is the only row here that touches a vendor.

---

## Dependencies

```text
Phase 1 (T001–T003)
   ↓
Phase 2 (T004–T008)   ← corpus + provider seam; blocks everything
   ↓
   ├── Phase 3 US1 (T009–T017)
   └── Phase 4 US3 (T018–T023)   ← T018 shapes the path, so it lands EARLY, not last
   ↓
Phase 5 (T024–T027)   ← needs a path that answers
   ↓
Phase 6 (T028–T030) → Phase 7 (T031–T035)
```

**T018 is listed under US3 but must land with T009.** A path built with a tool registry and
stripped later is a path that once could act; one built without never could.

---

## Parallel opportunities

- **T004 and T007** — corpus vendoring and the provider seam touch nothing in common.
- **US1 and US3 rows** — T013–T016 and T022–T023 are different files.
- **T031 and T032** — docs.

---

## Implementation strategy

**MVP is US1 + US3 together, and they are not separable.** An answering path without the never-acts
guarantee is the one outcome ADR-0039 decided against before this feature existed, and it would be
the hardest thing to retrofit — T018 shapes what the path *holds*.

**Phase 5 is the deliverable, not the polish.** Everything before it builds a capability; Phase 5
is what makes the existing gates true. Cutting it ships the exact defect this feature was written
to close, with an answering path added on top.

**If the corpus proves larger than expected** (T004), that is the thing to raise — not to work
around by fetching at answer time, which makes "pinned" untrue and every answer dependent on a
third party being up.

---

## Notes

**42 tasks**, 18 of them rows. High, deliberately: this feature's subject is a suite that could not
fail.

**Three obligations are owed by name** — T034 (enclave), T035 (a real model), and the **Principle V
security review** for T006a's additive member, which the plan originally asserted was not needed.

**Two tasks are owed by name** — T034 (enclave) and T035 (a real model). T035 is the only vendor
contact anywhere in the feature.

**FR-004, FR-005 and SC-003 are deliberately uncovered here.** They are the estate-state
requirements, marked *Deferred with estate-state answering* in the spec and left in place so the
next planner finds the split rather than an unexplained absence. A coverage check that flags them
is correct to; they belong to a feature that does not exist yet.

**One task exists to keep a constraint honest** (T008). The adapter set is closed and 020 found that
out the hard way; if the provider cannot be reached through the existing seam, that is a governed
change to raise rather than a module to add.
