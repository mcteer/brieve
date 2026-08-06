# Tasks: A model says what to do, not only what to use

**Feature**: 040 | **Input**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [contracts/](contracts/)

**Organization**: by user story. Tests are required — every contract row (M1–M18) has a task, and
**every task that asserts has a task that builds**. FR-013's guard has no story because it is not
about this feature; it lives in Polish and is merge-blocking all the same.

## Gate Task Types *(present in this feature)*

| Gate type | Where |
| --- | --- |
| **Fail-closed** | T017 (malformed re-asked, exhaustion ends the run), T018 (oversize refused, never truncated), T012 (both providers or the row lies) |
| **Conformance** | every phase — `tests/conformance/choice/` beside the four suites the feature must not move |
| **Correlation / evidence** | T015 (the request rests in exactly one durable place, pinned payload sets) |
| **Eval** | **None, and that is deliberate.** No model is promoted and no cell changes; the `_SYSTEM` prompt change rides the existing fixture/live parity (`harness-owns-model-vocabulary`). |
| **No-secret-leak** | T015/T015a (trail payloads pinned to their exact key sets), T015c (retention stated, behaviour asserted) |

**Three tasks exist to prove the others can lose.** **T012a** reverts the field in-memory and
requires the Postgres leg of M7 to fail — the in-memory provider passes for free, so only the
asymmetry proves the SQL. **T017a** keeps answering malformed past the bound and requires the run
to end. **T023a** removes a ledger entry and requires the capability check to trip — a
reachability guard that cannot lose is the defect it guards against, twice shipped.

## The three layers, and why no phase closes the feature alone

1. **The answer widens** — a model can *say* name-plus-arguments (Phase 2–3).
2. **The saying survives** — the intent carries it, both stores prove it (Phase 4–5).
3. **The saying is bounded** — malformed re-asked, oversize refused, nothing leaks (Phase 5–6).

Registering the widening without durability ships the resume defect; durability without the
bounds ships unbounded model output kept indefinitely. FR-003's carry-through is what makes all
three land without any governance change.

## Path Conventions

Repo root; sources in `src/`, tests in `tests/`. Conformance rows for this feature live in
`tests/conformance/choice/test_model_supplied_arguments.py` and component resume rows in `tests/component/test_arguments_survive_revival.py`.

---

## Phase 1: Setup

- [ ] T001 Create `tests/conformance/choice/test_model_supplied_arguments.py` with a module docstring stating what it owns — *the model's answer carries
  arguments, and everything around that fact stays put* — and why it lives beside the four
  recording-driven suites it is forbidden to move: splitting them lets one be read without the
  other.
- [ ] T002 [P] Create `tests/component/test_arguments_survive_revival.py` with a module docstring naming the stub this file exists to prevent:
  the in-memory provider stores the record object, so a resume row proven against it alone passes
  whether or not the SQL was widened (`src/core/durability/memory.py:29`'s own rule, research R3).

---

## Phase 2: Foundational — the answer's shape, and every mouth that speaks it

**The structured answer type and all four `Chooser` implementations move in one change (research
R9). Nothing in Phases 3–7 can be tested until a recording can carry arguments, so the second
grammar is foundational even though its compatibility rows belong to US5.**

- [ ] T003 Define the structured answer in `src/core/choice/chooser.py`: a tool **name** and its
  **arguments** (default empty mapping). `choose()` returns it. **`record_choice`'s payload does
  not change** — six keys, and T015 pins them. The `NONE`/empty terminal answer keeps working.
- [ ] T004 Update `RecordedChooser` and `parse_recording` in `src/core/choice/recorded.py`:
  **first non-space character `[`** parses the recording as a JSON list of
  `{"tool": ..., "arguments": {...}}`; anything else splits on commas exactly as today, and **a
  bare name is a choice with no arguments** (research R8). The `"-"` terminal sentinel serves
  both grammars — one rule, and *"the run ended"* is never inferred from punctuation. The
  empty-recording default (`sorted(permitted)[0]`, `recorded.py:82`) answers with no arguments —
  the true answer for the fixture tools and load-bearing for every pre-020 dispatched row.
- [ ] T005 [P] Update the scripted chooser in `tests/harness/scripted_chooser.py` to return the
  structured answer — bare names still mean no arguments, so no existing harness caller moves.
- [ ] T006 [P] Add `max_request_bytes` to `register()` in `src/core/registry/memory.py` with
  platform default `DEFAULT_REQUEST_BYTES = 64 * 1024`, stored beside `risk_class` and
  `repeatable` and readable back from the entry (research R7). **A property of the capability,
  not a shape contract** — clarification Q1's line, held.

**Checkpoint**: a recording can say what to do. Nothing yet listens.

---

## Phase 3: US1 — A model says what it wants done (P1)

**Goal**: the act is performed with what the model stated.

**Independent test**: two recordings naming different targets produce two different acts.

- [ ] T007 [US1] Widen `ModelChooser` in `src/adapters/model_chooser.py`: `output_type` becomes
  the structured answer and `_SYSTEM` asks for a name **and arguments** — keeping `NONE` working,
  and keeping the prompt model-agnostic (`harness-owns-model-vocabulary`: phrasing failures are
  harness-protocol work, never per-model branches).
- [ ] T008 [US1] Carry the model's arguments to the governed invoke in
  `src/core/choice/bounded.py`, in place of the constant the entrypoint passes today. **This is
  the actual gap** (research R1): `_PROBE_ARGUMENTS`' own docstring calls it *"a fixture
  affordance, and it always was."*
- [ ] T009 [US1] Stop passing `_PROBE_ARGUMENTS` at `src/surfaces/dispatch/entrypoint.py:221` and
  **rewrite the constant's docstring** to its one remaining job: supplying the values a
  **pre-feature** intent's first attempt actually ran with, on revival only (research R4). A
  stale comment on this path nearly produced a phantom finding once already (039's record).
- [ ] T010 [US1] Row **M1** in `tests/conformance/choice/test_model_supplied_arguments.py`: drive **two** runs whose recordings state different targets
  for the same capability; assert the two acts differ. Two, because one act matching one request
  is indistinguishable from a constant that happens to match.
- [ ] T010a [US1] Row **M2** in `tests/conformance/choice/test_model_supplied_arguments.py`: a model-directed act traverses the identical pipeline — same
  entry, same hooks, same bracket, same records — and a denied capability refuses identically
  whether its request came from a model or the platform (FR-002, FR-003, SC-002). **State that
  argument provenance is the only difference**, so the row does not read as a stronger claim.
- [ ] T010b [US1] Row **M3** in `tests/conformance/choice/test_model_supplied_arguments.py`: byte-compare a no-argument step's records before and after
  the widening (FR-012).

**Checkpoint**: the act is the model's. An interruption still loses it.

---

## Phase 4: US2 — An interrupted act is repeated faithfully (P1)

**Goal**: a revived step re-invokes with what the model asked for, consulting no model.

**Independent test**: interrupt, revive, compare — against both stores.

- [ ] T011 [US2] [GATE:fail-closed] Carry the request through durability: add a **nullable**
  `arguments` column to `intents` in `src/core/durability/schema.sql` (NULL = pre-feature, `{}` =
  genuinely nothing — research R4, and the distinction is schema-level); add the field to
  `IntentRecord` in `src/core/durability/types.py` with a docstring stating the retention
  (kept until removed; the platform expires nothing); thread it through `bracket_call` in
  `src/core/observation/bracket.py` from its one caller — **one argument at one line**,
  `src/core/hooks/engine.py:247`, which already holds the arguments; and carry it through **all
  three** `src/core/durability/postgres.py` column lists — `record_intent`'s INSERT,
  `open_intents`' SELECT (`postgres.py:293`), `closed_intents`' (`postgres.py:323`) — where a
  defaulted field fails **silently** and `open_intents` is the one resume reads (research R3).
  **`src/core/durability/memory.py` needs no change, and that is a hazard, not a saving** — it is
  why T012 runs both providers.
- [ ] T011a [US2] Widen `already_chosen` from `{step: tool_name}` to carry the kept arguments
  beside the name — built at `src/surfaces/dispatch/entrypoint.py:814`, consumed at
  `src/core/choice/bounded.py:147` — so honouring a pending intent costs no provider call and
  re-invokes with the model's request. **NULL arguments revive with the legacy constant** (T009's
  one remaining job): the first attempt ran with those values, and repeating a different act than
  the one attempted is the defect even when the different act is emptier.
- [ ] T012 [US2] [GATE:fail-closed] Row **M7** in `tests/component/test_arguments_survive_revival.py`: interrupt a run at a step with
  non-trivial model-supplied arguments, revive, assert the re-invoke carries the same request —
  **parameterised over both durability providers, and that clause is the row** (SC-003).
- [ ] T012a [US2] **Prove M7 can fail** in `tests/component/test_arguments_survive_revival.py`: revert the field in-memory and assert the
  Postgres leg fails with an empty request while the in-memory leg passes anyway. The asymmetry
  is the finding; a row that cannot show it proves neither store.
- [ ] T013 [US2] Row **M8** in `tests/component/test_arguments_survive_revival.py`: revival consults no model — count asks across the revival
  and assert zero for the revived step (FR-005, SC-004).
- [ ] T014 [US2] Row **M12** in `tests/component/test_arguments_survive_revival.py`: build a pre-feature intent (NULL arguments), revive, assert
  the re-invoke carries the **legacy constant** and that NULL and `{}` are distinguishable end to
  end (FR-011, SC-008).

**Checkpoint**: what the model said survives. Now bound where it rests.

---

## Phase 5: US3 — What a model asked with does not become permanent evidence (P1)

**Goal**: exactly one durable home, removable, stated.

**Independent test**: read every durable record; the request is in one.

- [ ] T015 [US3] [GATE:no-secret-leak] Row **M9** in `tests/conformance/choice/test_model_supplied_arguments.py`: after a step with model-supplied
  arguments, the raw request is in `intents` and **nowhere else**. Pin `TOOL_CHOSEN` to its exact
  six keys (`run_id`, `step_index`, `attempt`, `model`, `named`, `outcome`); pin `PRE_DECISION`
  to argument keys and hashes (`redact_arguments` still runs at `engine.py:101`); assert
  `RUN_RESUMED` carries counts and the observer received only the `idempotency_key`
  (`bracket.py:88`). **The closures are asserted, not inherited** (research R5) — each holds
  because of somebody else's decision, and a claim held by inheritance stops holding when they
  revisit it.
- [ ] T015a [US3] [GATE:no-secret-leak] Record the security decision where the schema reader will
  meet it: the `arguments` column comment in `src/core/durability/schema.sql` states that this is
  the **first and only** durable store of raw model-supplied values, why (resume re-invokes; a
  hash cannot be re-invoked with), and the retention (kept until removed). On 038's precedent —
  argued under a gate, never slipped in as a field.
- [ ] T015b [US3] Row **M10** in `tests/component/test_arguments_survive_revival.py`: clear `arguments` on a **closed** bracket and assert resume
  decisions, accounting and re-observation are unchanged (FR-007a, SC-005a). **Name the unsafe
  removal in the same row**: clearing an **open** bracket's request makes its revival re-invoke
  with nothing — this feature's defect, reintroduced by policy. The row is the constraint the
  future retention control inherits: *finished acts only*.
- [ ] T015c [US3] Row **M11** in `tests/component/test_arguments_survive_revival.py`: an intent's arguments survive arbitrary elapsed time with
  no platform action — the **behaviour** of "kept until removed", never the prose (FR-007b).
  Six checks in this repository have matched comments instead of code; this is not the seventh.

**Checkpoint**: one home, bounded. Now bound what arrives.

---

## Phase 6: US4 — A malformed request is refused, never performed (P1)

**Goal**: re-asked within the existing bound; oversize refused with size, never content.

**Independent test**: malformed recording re-asks; exhaustion ends the run.

- [ ] T016 [US4] Extend `resolve_step_tool`'s bounded retry in `src/core/choice/bounded.py` to
  cover a **malformed object** — one that does not parse as name-plus-arguments — as a refusal
  fed back to the model within `DEFAULT_RECHOICE_BOUND`, distinguishable in the refusal reason
  from an unpermitted name and an unknown name (research R12). A model that could produce a valid
  word can produce an invalid object, and the existing retry was not written for that.
- [ ] T016a [US4] Enforce the size bound centrally in `src/core/choice/bounded.py`: measure the
  serialised request against the named capability's `max_request_bytes` (read from the registry,
  T006) **before** any invoke; over it, the answer joins the `refused` list with a reason
  carrying the byte count and the bound and **never the content** (FR-007d, on `TURN_REFUSED`'s
  precedent — size, not payload). **Never truncated** (FR-007c): truncation performs a different
  act from the one described, which is worse than performing none.
- [ ] T017 [US4] [GATE:fail-closed] Row **M4** in `tests/conformance/choice/test_model_supplied_arguments.py`: a malformed answer is re-asked, never
  acted on — and exhausting the bound ends the run in a recorded terminal state. **Both halves**
  (SC-006): a bound never reached is not demonstrated by the path that does not reach it.
- [ ] T017a [US4] **Prove M4's bound is a bound** in `tests/conformance/choice/test_model_supplied_arguments.py`: a recording that answers malformed
  objects past the re-choice bound must end the run, not act on the last answer.
- [ ] T018 [US4] [GATE:fail-closed] Row **M5** in `tests/conformance/choice/test_model_supplied_arguments.py`: an oversized request is refused and
  re-asked; the refusal record carries the byte count and the bound and none of the content
  (SC-006a). Read the record to assert the absence, not only the refusal.
- [ ] T018a [US4] Row **M6** in `tests/conformance/choice/test_model_supplied_arguments.py`: register two fixture capabilities, one with a raised
  `max_request_bytes`; send **the same** large request to both; one accepts, one refuses
  (SC-006b). The same request to both is the row — different requests would prove nothing about
  the bound.
- [ ] T019 [US4] Row **M17** in `tests/conformance/choice/test_model_supplied_arguments.py`: one run exercising malformed (re-asked), refused (a
  governance denial), and failed (the capability rejected the request — `tool_error`, the
  engine's existing path, research R12) — three distinguishable records (FR-009). An operator
  told the wrong one fixes the wrong thing.

**Checkpoint**: getting it wrong is bounded and legible. Now prove nothing moved.

---

## Phase 7: US5 — Nothing that already worked has to be rewritten (P2)

**Goal**: every existing recording and record means what it meant.

**Independent test**: the four suites pass unedited.

- [ ] T020 [US5] Row **M13** in `tests/conformance/choice/test_model_supplied_arguments.py`: `"plan,apply,-"` parses to exactly today's three choices — a
  bare name is a choice with **no arguments** — and the four recording-driven suites
  (`tests/conformance/choice/harness.py`, `tests/conformance/choice/test_a_model_chooses.py`,
  `tests/conformance/durability/test_model_driven_resume.py`,
  `tests/conformance/reports/test_the_run_observes.py`) pass **unedited** (FR-010, SC-007).
  Check the diff, not only the run: an edited suite is the blast radius arriving through the
  test tree.
- [ ] T021 [US5] Row **M14** in `tests/conformance/choice/test_model_supplied_arguments.py`: a `[`-prefixed recording carries structured choices and the
  `"-"` terminal sentinel works in both grammars (FR-001's fixture path).
- [ ] T022 [US5] Row **M15** in `tests/conformance/choice/test_model_supplied_arguments.py`: one run naming one capability at two steps with different
  requests — two intents, two acts, the second not mistaken for a repeat of the first. **This is
  R2's claim measured rather than remembered**: no programs means steps already key distinctly,
  and this row is what keeps that true by observation.

**Checkpoint**: compatibility proven, not presumed.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T023 [GATE:conformance] Build the capability inventory in
  `tests/unit/capability_inventory.py` and its row **M16** in
  `tests/unit/test_capability_inventory.py`: every capability name `core` defines is registered
  in the assembled registry or listed in `DELIBERATELY_UNREACHABLE` with a reason and a record —
  `run_program` citing ADR-0065, `read_subject`/`author_file`/`open_proposal` citing the
  successor feature by name and date (research R10). The AST sweep of `src/core` for tool-name
  constants and `register(` literals keeps the ledger itself honest; the residual (a capability
  defined in a shape the sweep does not recognise) is stated in the ledger's docstring rather
  than hidden.
- [ ] T023a **Prove M16 can fail** in `tests/unit/test_capability_inventory.py`: remove a name
  from the ledger in-memory and assert the check trips. Two features shipped unreachable
  capabilities behind green rows; a guard that cannot lose is the same defect wearing a
  checkmark (SC-009).
- [ ] T024 Row **M18** in `tests/conformance/choice/test_model_supplied_arguments.py`, **enclave-marked**: dispatch a run whose recording carries a
  structured choice through the real path — Nomad meta → environment → `build_chooser` → the
  allocation — and assert the act happened against the model-named target. Every other row could
  pass while this one was false, which is the state two prior features shipped in
  (`verify-the-production-caller`).
- [ ] T025 Run quickstart Scenarios A–E and G hermetically, then **F** against the enclave
  (`make dev-up`), per `specs/040-model-supplied-arguments/quickstart.md` — including M7's
  prove-it-can-fail leg, which is the one most worth watching fail.
- [ ] T026 [P] Update `ROADMAP.md`: 020's row gains a note that the model chose the tool while
  the platform supplied every argument until 040; the authoring trio's ledger entry is the
  pointer the successor feature consumes.
- [ ] T027 Run `make check` **and** the hermetic conformance lane. The local gate does not
  collect `tests/conformance/` (`local-gate-is-not-the-fast-lane`), so a green `make check` says
  nothing about any row in this feature.

---

## Dependencies

```text
Phase 1 (Setup)
   └─> Phase 2 (Foundational: the answer type, both grammars, all four choosers, the registry property)
          ├─> Phase 3 (US1 — the act is the model's)
          │      ├─> Phase 4 (US2 — it survives revival)      ─┐
          │      │      └─> Phase 5 (US3 — one durable home)   ├─> Phase 8 (Polish, incl. enclave)
          │      └─> Phase 6 (US4 — bounded and legible)      ─┤
          └─> Phase 7 (US5 — nothing moved)                   ─┘
```

**Phase 5 depends on Phase 4** (the home must exist before its bounds are proven). **Phases 6 and
7 depend only on Phases 2–3** and run parallel to 4–5.

## Parallel opportunities

- **Phase 1**: T001, T002 together.
- **Phase 2**: T005 and T006 beside T003/T004 (different trees; T004 needs T003).
- **Phase 3**: T007 and T008 different trees; T009 after T008; M-rows T010–T010b together after.
- **Phases 4+6+7**: independent of each other once Phase 3 lands — durability, bounds, and
  compatibility are different trees.
- **Phase 8**: T023/T023a and T026 beside the rest; T024/T025 last.

## Implementation strategy

**MVP is Phases 1–3**: a model's stated request reaches the act, hermetically proven. **It is not
shippable alone** — an interruption at any model-directed step revives with an empty request, so
Phase 4 is not optional polish; it is the half of the feature that keeps the platform's central
durability claim true once the arguments are the model's (research R3). Ship at the Phase 5
checkpoint or not at all.

**Phase 6 is where the security posture is enforced** and Phase 5 where it is proven: one durable
home, pinned payloads, removability with the unsafe case named. Those two phases are the review
Principle V's three sealed touches carry.

**T023 is the task that outlives the feature.** The ledger converts this repository's
twice-shipped defect — capabilities built, proven, unreachable — from something found by accident
into something a merge cannot pass silently. Its entry for the authoring trio is deliberately a
pointer at the next feature: consuming it is how 041 starts.

## Notes

- **18 contract rows (M1–M18), 38 tasks**, and every asserting task names the row it asserts.
- No task edits any of the four recording-driven suites; T020 asserts the diff stays empty.
- The `_SYSTEM` prompt change (T007) rides the fixture/live parity — no per-model branches, per
  `harness-owns-model-vocabulary`.
