# Tasks: The admin console — governance configuration leaves Terraform

**Input**: Design documents from `specs/044-admin-governance-console/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md,
contracts/conformance-console.md, quickstart.md

**Tests**: Included — the deliverable is largely its rows (C1–C25, CL1–CL3). The write path's
rows land with the write path, not after it: an interface that can write before its refusals
exist is the gap 042 refused to ship with.

**Organization**: By user story, with one deliberate reorder: **US4's exclusion rows land in
the same phase as the first write route**, not in their own later phase. A console that can
write governance records while the dispatched-run exclusion is "next" is the platform being
configurable by the thing it governs for the length of that gap — 042's argument, one surface
over.

## Format: `[ID] [P?] [Story] Description`

## Gate Task Types *(present in this feature)*

| Gate type | Where |
| --- | --- |
| **Fail-closed** | T006 (unreadable config renders unavailable — C10), T009 (validation precedes the fabric, refusal maps as refusal — C1/C4/C8), T004 (absent field = enabled — C18, so old records never flip meaning) |
| **Conformance** | T002, T008, T010–T011, T013, T015–T016 — the C-rows; T019–T020 the CL legs |
| **Correlation / evidence** | T006 (config reads audited on the EVIDENCE_READ precedent), T009 (request/decision/refusal recorded), T012 (**no** MODEL_GATE for a gate that did not run — 040's vacuous-assertion shape avoided) |
| **Eval** | N/A per research R11 — no model output is produced; FR-009 makes ungated promotion *harder* by refusing unqualified cells at validation (stated per the template's rule) |
| **No-secret-leak** | T006/T008 (C11: no credential in any console response), T014/T015 (C25: the connection vocabulary has no credential field to fill) |

## The shape of the work

The mechanism needs a principal before it needs a page (R1): no policy grants write on any
`harness-authority` path, `authority_change` is attached to no role, and the submitter is
constructed without a token — so the trust-fabric work is Foundational and everything else
assumes it. The toggle needs no machinery because of where it lives (R4). And pending is never
applied (C2), which is the row the whole console's honesty rests on.

## Path Conventions

Single project: `src/`, `tests/`, `infra/` at repository root.

---

## Phase 1: Foundational (blocking all stories)

**Purpose**: the principal, the gate coverage, the record shapes — what every story stands on.

- [X] T001 Trust-fabric additions: `infra/modules/trust-fabric/authority-submit.tf` (new) —
      the `authority_submit` policy granting `create`/`update` on exactly the console's
      records (`claim-mappings/*`, `ask-bindings`, `product-connections`), with
      `control_group` blocks when `control_groups_enabled` (R1), attached to the **api**
      role in `auth.tf`; extend `controlled_paths` in `control-groups.tf` with the two new
      paths (Q3/FR-023a); extend `harness_authority_read` in `policies.tf` with
      `product-connections` as an **exact path, no glob** (042's 020-lesson). `terraform
      validate` clean.
- [X] T002 [P] Unit scan **C6** in `tests/unit/test_console_controlled_paths.py`: every
      record the console can write appears in `controlled_paths` — completeness against the
      module's own list, 042's V6 shape; plus the R1 regression guard — the
      `authority_submit` policy is attached to the api role, so the mechanism keeps its
      principal.
- [X] T003 [P] Generalise the submitter in `src/surfaces/api/authority_submit.py`:
      `ConfigChange` (record ∈ R2's closed set, payload, `cas`, requester) through the same
      three-outcome mapping as `ClaimMapping`; the submitter authenticates as the API's
      attested identity rather than a configured token (R1/R8); unit rows including **C3**
      (`wrap_info` present-as-null, read by truthiness — 007's shape driven directly) and
      `unknown_record` refusal.
- [X] T004 [P] [GATE:fail-closed] Binding-record field in
      `src/core/authority/ask_binding.py`: `relevance_enabled`, **absent = enabled** so
      every pre-044 record keeps its meaning; unit rows **C18** in
      `tests/unit/test_ask_binding_toggle.py`.
- [X] T005 [P] The disjoint role in `src/core/answering/scope.py`:
      `ROLE_VISIBILITY["admin"] = frozenset()` with the R6 reasoning in a comment; unit rows
      asserting **both directions** of FR-016a — admin confers no audit visibility, and
      neither existing role gains configuration authority by this change.

**Checkpoint**: the fabric has a principal, the gate covers the paths, the shapes parse — and
no route exists yet.

---

## Phase 2: US1 — An administrator sees the platform's posture (P1)

**Goal**: read without estate credentials; unavailable is never empty (FR-001–004).

**Independent Test**: sign in as an admin, compare the console against the fabric's records,
confirm no secret value and a recorded read; a non-admin is refused.

- [X] T006 [US1] Console read routes in `src/surfaces/api/console.py` (new):
      `GovernanceConfiguration` assembled per request from the fabric (bindings + toggle
      state, qualified cells, protected policies, connections, gating posture); requires
      `admin` in the resolved subject's roles (the evidence-read check pattern); an
      unreadable record renders **unavailable** (C10); every read audited with the
      administrator's identity on the EVIDENCE_READ precedent (FR-004); registered in
      `src/surfaces/api/app.py`.
- [X] T007 [US1] The portal page: `/settings` in `src/surfaces/portal/app.py` +
      `src/surfaces/portal/templates/settings.html`, through the existing relay only — the
      page renders what the API returned, including `unavailable` and the FR-023b gating
      posture, and holds no logic (C8's architecture half).
- [X] T008 [US1] [GATE:conformance] Rows **C9–C14** in
      `tests/conformance/console/test_console_read.py` (new dir): field-for-field agreement
      (C9), unavailable-not-empty (C10), [GATE:no-secret-leak] no credential in any
      response (C11), reads recorded (C12), non-admin refused and recorded — including
      `operator` and `compliance-analyst` (C13), admin's evidence read refusing exactly
      as a stranger's (C14), and **C26** — the presented role vocabulary is exactly
      ADR-0039's, asserted against the canonical constant; C9 additionally pins FR-022
      (settings shown = settings implemented) and FR-009's offer side (`qualified_cells`
      from the matrix and nothing else) (analyze C1/C2/C3).

**Checkpoint**: US1 independently testable — a read-only console, safe to ship alone.

---

## Phase 3: US2 + US4 — The fabric decides, and an agent cannot ask (P1) 🎯 the safety pair

**Goal**: changes are requested, never applied (FR-005–009); the write path and its
exclusion land together (FR-014/015/017).

**Independent Test**: propose a change with a quorum — pending, not in force; approve out of
band — in force. Propose a refused change — refused. From a dispatched run, reach nothing.

- [X] T009 [US2] The change-request route in `src/surfaces/api/console.py`: validate against
      the record's own parser **before** the fabric is asked (C1 — an unqualified cell
      refuses `unqualified_cell` with zero fabric writes); submit via T003's `ConfigChange`;
      render the three outcomes distinctly with the **ungated disclosure** when no quorum is
      configured (C2/C5, FR-006/007); CAS from the version the administrator read —
      stale answers `record_moved` (C7); refuse a claim-mapping request granting `admin` to
      the requester's own subject (`self_grant_refused`, FR-017); record every request,
      decision, and refusal (FR-008); pending shows the wrapping token's accessor and expiry
      (R11's native withdrawal).
- [X] T010 [US2] [GATE:conformance] Rows **C1–C5, C7–C8, C21** in
      `tests/conformance/console/test_console_write.py`: validation-first, the three
      outcomes never collapsed (C2 fails if they are), truthiness not membership (C3),
      refusal recorded (C4), ungated disclosed (C5), stale CAS (C7), no apply path (C8),
      self-grant refused in several wordings of "own subject" (C21).
- [X] T011 [US4] [GATE:conformance] Rows **C19, C20, C22** in
      `tests/conformance/console/test_console_exclusion.py`: a dispatched run resolves no
      tool to the console's read or write and a planted instruction records an attempt and
      changes nothing (C19); **the rigged-on construction** — with the exclusion removed,
      C19's scenario succeeds and the row fails (C20, SC-007); MCP's operation table
      contains no configuration verb (C22) — the absence as a checked fact, in the same
      phase as the write path it excludes.

**Checkpoint**: the console can change the estate, the fabric decides, and the thing the
estate governs cannot reach it. **No increment ships past this phase without all of it.**

---

## Phase 4: US3 — The judge can be turned off, and the platform says so (P1)

**Goal**: disclose, never suppress — the template for every future toggle (FR-010–013).

**Independent Test**: disable; ask; the answer carries the disclosure and the record says an
administrator decided. Re-enable; the next ask judges. No restart.

- [ ] T012 [US3] The toggle honoured in `src/surfaces/api/ask.py` and
      `src/core/answering/answer.py`: when `relevance_enabled` is false, skip judge
      resolution and judging; the answer carries the disclosure in `relevance_note`
      ("relevance was not checked: disabled by an administrator"); the record's disposition
      is `relevance_disabled_by_admin` — distinct from `relevance_unavailable` (FR-012);
      **no MODEL_GATE is written** (R4 — an event for a gate that did not run is 040's
      vacuous shape); in-flight answers complete under the binding they started with (true
      by construction; asserted, not assumed).
- [ ] T013 [US3] [GATE:conformance] Rows **C15–C17** in
      `tests/conformance/console/test_console_toggle.py`: the disclosure reaches the
      rendered response, not only the record (C15); the disposition distinction and the
      absent MODEL_GATE (C16); disable→ask→enable→ask in one process against one surface —
      no restart (C17, SC-011).

---

## Phase 5: Q4 — Product connections (P1, scope chosen over recommendation; [US2] labels because connections ride US2's mechanism)

**Goal**: locations governed like everything else; accepted ≠ reachable (FR-018a–c).

**Independent Test**: change a connection — three outcomes as ever; point it somewhere
unreachable — `unreachable`, never "applied and working"; try to enter a credential — no
field will take one.

- [ ] T014 [US2] `ProductConnection` in `src/surfaces/api/console.py`, beside its only
      consumers (R5 — the probe and the display): the record parser (product ∈
      {tfe, vault}, locations only — the vocabulary has no credential field, FR-018b), the
      reachability probe (stdlib urllib, unauthenticated health endpoints, R5), and the
      three-state `verification` rendered separately from the change outcome (FR-018c) —
      **any HTTP answer is reachable; only connection failure or timeout is `unreachable`**
      (analyze A1: TFE's ping answers 401 without a token, and 401 proves the endpoint is
      there — a probe treating non-2xx as down would read every correctly-secured TFE as
      unreachable);
      the console labels the record "not yet consumed by dispatched runs" (R5's honest
      middle, FR-022).
- [ ] T015 [US2] [GATE:conformance] Rows **C23–C25** in
      `tests/conformance/console/test_console_connections.py`: same three-outcome path
      (C23), accepted-but-unreachable renders `unreachable` and never folds into applied
      (C24), [GATE:no-secret-leak] the parser rejects fields outside the location
      vocabulary (C25).

---

## Phase 6: US5 — Terraform stays the source of truth it already is (P2)

**Goal**: two writers, zero silent disagreements (FR-019/020).

**Independent Test**: change a value in the console; apply the estate; the outcome is
visible, and provenance says who wrote last.

- [ ] T016 [US5] Provenance through the read path: the console writes `set_by:
      console/<subject>` into every record payload (T009 carries it; this task renders it) —
      "last set by" readable from the record itself in `settings.html` and the read payload;
      rows in `tests/conformance/console/test_console_provenance.py`: a Terraform-shaped
      record (no `set_by`) displays as estate-written, a console write displays its subject,
      and an estate overwrite of a console change is visible as a version bump with flipped
      provenance (SC-012) — C7's CAS rows already cover the concurrent-edit half.

---

## Phase 7: Polish & Cross-Cutting

- [ ] T017 [P] The a11y lane walks the console (**CL3**, FR-021b): `/settings` rows in
      `tests/a11y/test_wcag.py` and `tests/a11y/test_keyboard_and_screenreader.py`, behind
      the authenticated-page fixture the thread rows use — measured: today's rows visit no
      console page, so the lane would stay green while the page went unchecked.
- [ ] T018 [P] Write `docs/adr/0069-governance-configuration-is-requested-at-a-console.md`
      (Proposed): the argued move of 026's origination line, the disjoint role, the
      disclose-not-suppress template, and R1's finding that the mechanism predated any
      principal able to use it; index in `docs/adr/README.md`.
- [ ] T019 Apply the trust-fabric additions to the dev enclave and run **CL1**: the full
      request→decide cycle under the API's attested identity — applied-and-disclosed in dev
      (quorum null); then with a quorum configured, pending → out-of-band approve → in
      force. Record outcomes in `contracts/conformance-console.md`; re-seed the model
      credential if the apply clobbers it.
- [ ] T020 Run **CL2** on a served surface: disable the judge from the portal, ask, see the
      disclosure; re-enable, ask, see the gate — no restart; record the outcome in the
      contract.
- [ ] T021 [P] Run `specs/044-admin-governance-console/quickstart.md` top to bottom as
      written; fix drift in the doc, not by hand-waving the steps.
- [ ] T022 Update `ROADMAP.md` in the implementation PR: the admin-interface Next entry
      closes with the mechanism in one line, and 044's Shipped row lands (the file's own
      landing rule).

---

## Dependencies & Execution Order

- **Foundational**: T001 first (everything writes through it); T002–T005 ∥ after T001
  (T002 scans T001's files; T003–T005 are independent of each other).
- **US1**: T006 after T003+T005 (submitter shape for gating posture; the role key);
  T007 after T006; T008 after T007.
- **US2+US4 land together**: T009 after T003+T004+T006; T010 after T009; **T011 in the same
  phase** — the write path does not outlive its exclusion rows.
- **US3**: T012 after T004+T009 (the field, and the console that flips it); T013 after T012.
- **Q4**: T014 after T009 (the same route family); T015 after T014.
- **US5**: T016 after T009.
- **Polish**: T017 after T007; T018 anytime; T019 after T001+T010; T020 after T012+T019;
  T021/T022 last.

## Parallel Example

After T001: `T002 ∥ T003 ∥ T004 ∥ T005`. After T009 lands: `T010 ∥ T011 ∥ T014 ∥ T016`.

## Implementation Strategy

Foundational → US1 (read-only console — a safe, shippable MVP on its own) → **US2+US4 as one
phase** → US3 → connections → provenance → polish. The suggested MVP is Foundational + US1:
an administrator who can *see* the estate's posture without estate credentials is
independently valuable and risks nothing, because no write path exists yet. The product
arrives with Phase 3, and Phase 3 is indivisible.
