# Tasks: How the platform holds a model credential

**Input**: Design documents from `/specs/027-model-credential-posture/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/conformance.md

**Tests**: included — every property here lands as a row, and the feature exists because a
posture nobody stated let three features defer it.

**Organization**: by user story. **Two orderings are load-bearing**: the constitution amendment
(T024) merges *with* this feature, not after — a plan that shipped the capability first would have
the platform contradicting its own constitution in the interval (US3's failure mode). And the
no-env-fallback row (T004) is pinned *before* the reader is wired, so the convenient wrong fix is
provably caught rather than assumed absent.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup — the measurements the design rests on

- [X] T001 Pin the reframing (research F1) as an executable note in
      `tests/component/test_model_credential.py`: a test asserting `BrokeredMaterialSource` in
      `src/core/authority/entitlements.py` still has **no production implementation** — the
      premise 027 is the first to change. It documents that this feature *establishes* the
      broker rather than reusing one; when a real broker exists it becomes a real assertion about
      what implements the protocol.
- [X] T002 Pin the static-key finding (research F2): a comment-block test in the same file
      recording that a vendor key is **not derivable** — no credential API to mint lesser
      material from — so the posture is "never persisted", not "derived". Kept executable so the
      next person tempted by response-wrapping ceremony finds the reason it buys nothing.

## Phase 2: Foundational — the reader and the record

- [X] T003 Create `src/core/authority/model_credential.py`: `BrokeredModelCredential` with
      `fetch(vendor) -> str` reading `model-credentials/<vendor>` (KV v2) **under the caller's own
      attested identity**, and a `credential_reference(vendor)` returning
      `vault:model-credentials/<vendor>@v<version>` — where `<version>` is read from **KV v2's
      `data.metadata.version`** (analysis U2: the fabric's `_kv_data` returns the `data` dict and
      the version is not in it; a `data/` read returns `{data, metadata}`, so the reader takes the
      metadata explicitly rather than assuming it "for free"). Absent/unreadable →
      `ResolutionRefused` (`credential_unavailable`). **Never caches** — no instance state
      carrying a key across calls. Module docstring carries research F1/F2: first broker, key not derivable, lives in
      `authority` because 025's never-acts rows forbid `answering` any `authority` import.
- [X] T004 [GATE:fail-closed] Register `credential_unavailable` in
      `src/core/authority/errors.py`'s `RESOLUTION_REASONS` with the distinction that earns it:
      the cell is qualified (026's checks passed) and the *credential* could not be obtained —
      distinct from `unqualified_cell` (matrix) and `fabric_unreachable` (the store itself down).
- [X] T005 [P] [GATE:fail-closed] Component rows in `tests/component/test_model_credential.py`:
      a present record fetches; the reference carries the KV version; absent refuses
      `credential_unavailable`; an unreadable store refuses distinguishably; **two fetches never
      share cached state** (mutate the backing store between calls, observe the second sees the
      change).
- [X] T006 [GATE:conformance] **SEALED CORE** — `AuditEventType.ASK_ANSWERED`'s payload in
      `src/core/audit/schema.py` gains `model_authority` (the reference — **never a value**;
      data-model.md). `MODEL_GATE` is deliberately **not** touched (plan, Complexity: no run has
      bound a real model, so a run-side field would be written and verified by nothing). Update
      `src/core/answering/record.py`'s `record_ask` to require it.
      **Principle V review: Dan McTeer, BEFORE merge** — gating this PR, per the discipline the
      just-closed review established.
- [X] T007 [P] Extend the exact-payload row in `tests/component/test_answering.py` by exactly
      `model_authority`, and annotate the pinned-digest row in `tests/unit/test_audit_chain.py`
      the way 025/026 did — the sealed-core diff and its test move together.
- [X] T008 Thread `model_authority` through every existing `record_ask` call site
      (`src/surfaces/api/ask.py`, `src/surfaces/mcp/transport.py`,
      `tests/component/test_answering.py`) with the interim value `""` and a comment naming T011
      as the task that makes it real — `make check` is the sweep that proves none was missed.

**Checkpoint**: the credential can be read and refused, and the record can carry its reference.
Nothing fetches yet on a real path.

## Phase 3: User Story 1 — a person asks and gets an answer (P1) 🎯 MVP

**Goal**: the ask path fetches a credential at task start, calls the model, records the reference,
and refuses `credential_unavailable` when it cannot — the three-refusal order intact.

**Independent test**: with a fixture credential source, an ask that resolves a cell then obtains a
credential answers and records `model_authority`; with none, it refuses `credential_unavailable`,
never calling the vendor.

- [X] T009 [US1] The provider seam, at the depth it actually lives (analysis U1 — measured: the
      key is taken at construction, not per call). `client_and_model` in
      `src/adapters/anthropic_scorer.py` gains `api_key: str | None = None` (None keeps the
      `EVAL_PROVIDER_API_KEY` env path — the eval lane's, unchanged, FR-013). Then **all three
      provider constructors** thread it: `LiveAnswerProvider.__init__` and
      `LiveEstateProvider.__init__` in `src/adapters/anthropic_answering.py` gain
      `api_key: str | None = None` and pass it to `client_and_model`; the `LiveModelScorer` path
      in `anthropic_scorer.py` likewise. `test_gates_live.py` constructs all of them — the sweep
      that proves none was missed. No production caller relies on the env branch.
- [X] T010 [US1] Wire the fetch into `src/surfaces/api/ask.py`: **after** `authorise_ask`
      resolves a cell and **before** the provider is built, `estate_answer_for` and the guidance
      branch obtain the credential through an injected `credential_source` (default `None` =
      refuse `credential_unavailable`); the built provider carries the fetched key; the answered
      record sets `model_authority` to the reference (SC-005, FR-007). Order: cell → credential →
      vendor, three refusals recorded via `record_ask` (SC-006, SC-008).
- [X] T011 [US1] `build_router`/`create_app` gain `credential_source`; **`served.py` gains the
      provider construction it does not have today** (analysis C1 — measured: it wires
      `ask_authority` and deliberately no provider): per ask, fetch the key through
      `BrokeredModelCredential`, then construct `LiveAnswerProvider(model, api_key=key)` (and the
      estate provider likewise), used and dropped — no surface attribute ever holds a key.
      **The fetch is per ASK, not per surface construction** (analysis P4-2): a `served.py` that
      built one reader result and reused it across asks would pass T005's isolated no-cache row
      and still hold a key too long. `McpTransport` gains the same `credential_source`. Parity by
      construction (ADR-0033).
- [X] T012 [US1] Fixture plumbing in `tests/harness/api_fixtures.py`: `surface_under_test` gains
      `credential_source`, shared by both surfaces; add `available_credential(key=...)` (a source
      returning a fixed key + reference) and the default `None`. **The default refuses** — a
      fixture that auto-supplied a key would rebuild the loophole 026's fixture work exists to
      prevent, one layer down.
- [X] T013 [US1] [GATE:fail-closed] The headline row in
      `tests/conformance/answering/test_model_credential_posture.py`: with a qualified cell and
      **no** credential source, the ask refuses `credential_unavailable` and the provider is
      **never called** (counted at a `CountingProvider`); with a source, it answers and the record
      carries the reference. **And two asks produce two fetches** (analysis P4-2) — a counting
      credential source observes one read per ask, so a surface caching a key across asks fails
      here rather than only under a live enclave.
- [X] T014 [US1] [GATE:fail-closed] **The no-env-fallback row**, same file — and it is the row
      three features' silence would have needed: set `EVAL_PROVIDER_API_KEY` in the environment,
      arrange a qualified cell and **no** credential source, and assert the ask **still refuses
      `credential_unavailable`**. A production path that fell back to the env key would pass every
      other row and fail only this one.
- [X] T015 [US1] [GATE:conformance] The three-refusal row: `unqualified_cell` (no matrix cell) ≠
      `credential_unavailable` (cell green, no credential) ≠ `provider_unavailable` (credential in
      hand, vendor raises), each recorded with its disposition, in the fixed order (SC-006).
- [X] T016 [US1] [GATE:no-secret-leak] The never-persisted/never-leaked row: a full answered ask,
      then assert the key value appears in **no** trail payload, **no** returned response body, and
      the record carries the `vault:model-credentials/...@v<n>` reference instead. The asker's
      `subject_user_id` is present beside it (SC-004a — as-platform, but for-whom is answerable).
- [X] T016a [US1] Thread `credential_source` to the run path's fetch site (pass-2 P2-2 —
      measured: `_run_task` in `src/surfaces/dispatch/entrypoint.py:353` already holds
      `credentials` and an identity fabric, and `resolve_bound_model` → `build_chooser` at
      line ~409 is where a non-fixture model would need a key). For a non-fixture resolved model,
      fetch through `BrokeredModelCredential` under the allocation's own identity **after**
      `resolve_bound_model` validates the cell and **before** `build_chooser`, and pass the key
      explicitly — never ambient env. A fixture model fetches nothing (the existing path,
      unchanged). This is the run half of "both paths, one reader"; without it T017 asserts a
      call site that does not exist.
- [ ] T016b [US1] [GATE:conformance] The run-path fetch, **behaviourally, in the enclave lane**
      (analysis P4-1 — `_run_task` needs an attested workload identity, so this cannot be
      hermetic; it belongs beside `test_dispatched_end_to_end.py`'s enclave rows): a dispatched
      run binding a **non-fixture** model fetches through `BrokeredModelCredential` before
      `build_chooser`, and a fixture model fetches nothing. **Owed by name where the enclave lane
      is run — Dan McTeer.** T017 asserts the reader is shared by inspection; this asserts the run
      half actually fetches.
- [X] T017 [US1] [GATE:conformance] Both-paths-one-**credential-mechanism**, as a **hermetic
      import/AST row** (analysis P4-1 — the run path only runs under `@pytest.mark.enclave`, so a
      single conformance row cannot exercise both halves). The *providers* differ by path and
      always have (`LiveAnswerProvider` vs `ModelChooser` — unifying them is not the design). What
      is one is the **credential reader**: this row parses `served.py`/`ask.py` and
      `entrypoint.py` and asserts both name `BrokeredModelCredential` and no other credential
      source — the "one reader" claim, checkable without running either path (SC-002, FR-003,
      scoped to the credential). The *behavioural* run-path half is T016a's, in the enclave lane.

**Checkpoint**: the MVP — an ask obtains a credential per task, records its reference, and refuses
without one, on both surfaces, never leaking and never falling back.

## Phase 4: User Story 2 — revocation takes effect without a restart (P2)

**Goal**: removing the credential from the store refuses the next ask, same process.

**Independent test**: a working source, then a source whose backing record is deleted mid-session
→ the next ask refuses `credential_unavailable`, no restart.

- [X] T018 [US2] [GATE:conformance] The revocation row in the same file: a source over a mutable
      backing store answers; delete the record; the **next** ask refuses `credential_unavailable`
      with no re-construction of the surface (SC-003). The moment is locatable — the last answered
      record and the first refused one are adjacent in the trail.
- [X] T019 [P] [US2] The in-flight row: a task that already fetched **completes** on the authority
      it holds even if the store is emptied after the fetch — revocation binds the *next* task,
      exactly like every per-task grant (contract: "what these rows refuse to assert"). This
      guards against a fix that reached back into a running task to satisfy revocation too
      literally.

**Checkpoint**: revocation is a store operation with immediate effect on new work and no effect on
committed work.

## Phase 5: User Story 3 — the platform can say what its posture is (P3)

**Goal**: ADR-0058, constitution v1.4.0, and a check that the running system agrees — all in this
PR.

**Independent test**: the constitution describes brokering; a deployment contradicting it fails a
check.

- [X] T020 [US3] Write `docs/adr/0058-model-credential-brokering.md`: the decision (broker on the
      first exception's pattern; ADR-0044's federate-or-broker rule routes models here; gateway
      and do-nothing rejected with the reasons from research). Status Accepted, dated, relating to
      ADR-0044/0022/0039/0026.
- [X] T021 [US3] Amend `.specify/memory/constitution.md` to **v1.4.0** with a Sync Impact Report.
      **Two sentences in two different paragraphs** (measured — line ~150 and line ~166 of the
      current file, not one place): the standing-credentials clause *"with exactly one named
      exception: the rotated, Control-Group-governed management token behind the TFE broker"* gains
      the model vendor credential as a second named exception with the same governance clause; and
      the workload-identity clause *"static API keys are prohibited without exception"* becomes
      *"…prohibited as workload credentials; the named exceptions above are held only in the trust
      store and delivered per task."* **Both must move together** — amending one and leaving the
      other is the contradiction this feature exists to end, in miniature. MINOR (adds/expands);
      cite ADR-0058. Bump `**Version**` and `**Last Amended**`. **Security-maintainer review: Dan
      McTeer.**
- [X] T022 [US3] [GATE:conformance] The constitution-agreement check in
      `tests/conformance/identity/test_posture_matches_constitution.py`, **scoped to what a check
      can see** (analysis U3): (a) the amended text names two exceptions; (b) no jobspec under
      `infra/jobs/` passes a vendor key as a **workload env var** — a config leak, greppable in
      HCL. It does **not** assert the runtime persistence property (a workload writing a fetched
      key to disk), which is not visible to a config grep — that is T016's job, at the trail and
      checkpoint. The cross-reference is stated so SC-007's "deployment contradicts the text" is
      honestly the config half, and SC-004/SC-005's persistence half lives where it is
      observable.
- [X] T023 [P] [US3] Update `specs/024-portal-answering/`… nothing — but DO update this feature's
      own `contracts/conformance.md` status rows as they land, and record the Principle V review
      outcome and the amendment review outcome when given.

## Phase 6: Deployment, the enclave, and the named runs

- [X] T024 [P] Terraform in `infra/modules/trust-fabric/`: a `model-credentials/<vendor>` KV path,
      granted read to `mcp-surface` and the run role — **exact-path AND glob** (020's trap, which
      026 also paid; a Vault glob does not match the empty remainder). Governance clause matching
      the first exception's in production posture.
- [X] T025 [P] Dev placeholder in `infra/environments/dev/`: seed a **clearly-marked
      non-functional** credential. **The stated outcome was wrong and is corrected here** (third
      analysis pass, measured by running it): this does NOT make `make dev-up`'s ask progression
      reach a fetch, because dev's matrix holds only `fixture:` cells and governance is checked
      before the credential — a real `ASK_MODEL` refuses `unqualified_cell` with zero store reads,
      and an unset one has no provider. Qualifying a real cell is eval-gated work this feature
      deliberately excludes (Principle VIII; spec Assumptions). The seed is kept for the two
      things it does do: the enclave readability row reads it as applied, and T030 starts from a
      wired path. **What the vendor answers to a dud is confirmed at run, not predicted.**

- [X] T026 [GATE:conformance] The readability row in `tests/conformance/identity/`: `mcp-surface`
      and the run role read `model-credentials/<vendor>` against the live fabric (as-applied,
      `test_matrix_is_readable` pattern).
- [X] T027 [P] Glossary in `docs/glossary.md`: *model credential*, *model authority*, *brokered
      material* — linking *ask binding* and the matrix vocabulary.
- [X] T028 [P] ROADMAP entry for 027: the posture, the amendment, and the standing deferrals
      (per-tenant model scope — new here — plus portal answering, corpus freshness, team scope).
- [X] T029 [GATE:conformance] `make check`, `make evals`, and the hermetic conformance sweep all
      green; then `make conformance` on a live enclave (includes T026). **Run 2026-08-02, exit 0**
      — every lane including the deployment and mcp-surface lanes that stand real surfaces up. The
      trust-fabric changes were applied **targeted to `module.trust_fabric`**: a bare apply outside
      `enclave-up` wants to replace the Vault container on pre-existing env drift, unrelated to
      this change and deliberately not applied.
- [ ] T030 The thing three features could not do (SC-001, SC-003) — **named runner: Dan McTeer.
      BLOCKED on work this spec puts out of scope, and the blocker is worth stating precisely.**

      Three preconditions (quickstart §5). Two are ready: `ASK_MODEL` now reaches both deployed
      surfaces, and the credential path is applied and readable by all three roles (T029). The
      third is **a matrix cell qualifying a real model for `ask`**, and the dev matrix holds only
      `fixture:` cells — measured, and confirmed at the live enclave after the apply.

      **That cell cannot be written by hand.** Principle VIII permits model use only through
      eval-gated promotion; hand-authoring a cell would fabricate a qualification, which is the
      one thing the matrix exists to prevent. Earning it means a clean `make evals-live` run —
      which this feature's own spec lists under *Deferred and NOT in scope*: "promoting the `ask`
      cell to `live` (which needs a clean full-lane run and is unrelated to posture)".

      **So SC-001 is not reachable inside this feature's stated scope**, and that tension was in
      the spec from the start rather than introduced by implementation. Recorded here rather than
      resolved unilaterally: qualifying the cell and writing a real vendor credential into the
      enclave are both the maintainer's calls.

---

## Dependencies

```text
Phase 1 (T001-T002, measurements)
  → Phase 2 (T003→T004→T005 ∥ T006→T007→T008)
    → Phase 3 / US1 (T009→T010→T011→T012 → T013,T014,T015,T016,T016a,T016b,T017)
      → Phase 4 / US2 (T018→T019)                    [needs the wired fetch]
      → Phase 5 / US3 (T020→T021→T022, T023)          [the amendment, gated by T022]
        → Phase 6 (T024∥T025 → T026; T027∥T028; T029→T030 last)
```

**The two load-bearing rules**:
1. **T014 before the reader is trusted** — the no-env-fallback row exists so the convenient wrong
   fix is caught, and it must be written and failing-for-the-right-reason before T010's fetch is
   relied upon.
2. **T021's amendment ships in this PR** — never a follow-up. The capability (Phase 3) and the
   constitution change (Phase 5) are one merge, or the platform contradicts itself in between.

## Parallel opportunities

- T005 ∥ (T006→T007); T001 ∥ T002.
- Within US1: T013/T014/T015/T016/T017 are rows in one file after T012 — sequential only by
  shared file, independent in logic.
- T024 ∥ T025; T027 ∥ T028.

## Implementation strategy

**MVP = Phase 3.** A person gets an answer and the credential is obtained per task, recorded by
reference, refused when absent, never leaked, never env-fallen-back. US2 proves revocation, US3
makes the posture a stated and checked fact. The named runs (T029, T030) and the two reviews
(Principle V, the amendment) are the merge gate.

## Notes

- **Gate types**: fail-closed (T004, T005, T013, T014), conformance (T006, T015, T017, T018, T022,
  T026, T029), no-secret-leak (T016). Run-path fetch: T016a (wiring, hermetic) + T016b (behaviour, enclave lane). Eval gate: none — no suite changes, no cell qualified.
- **Sealed core**: one task (T006), review gating the PR.
- **The constitution amendment is a deliverable** (T020, T021, T022), not a follow-up — the single
  most important structural fact about this feature.
- **`core.answering` gains no `authority` import** — the reader lives in `authority` and the
  surface injects it, so 025's never-acts rows stay green and meaningful.
