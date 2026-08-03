# Tasks: A real model drives a governed run

**Input**: Design documents from `/specs/031-real-model-runs/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/conformance.md

**Tests**: included. **Cost bound stated up front** (FR-009): live lane +~10 min; demonstration
≤15 vendor calls.

**Organization**: by user story, in dependency order — US4 (visibility) is hermetic and lands
first; US2 (plan evidence) unlocks the cell; US3's harness carries US1's demonstration.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

*(none)*

## Phase 2: User Story 4 — the person who ran it can ask about it (P2, but lands first: hermetic)

- [X] T001 [US4] `ROLE_VISIBILITY` in `src/core/answering/scope.py`: `operator` gains
      `AUTHORITY_DENIED` and `AUTHORITY_REFUSED` — and only those (grants/issued/expired stay
      analyst-only; the comment carries the sensitivity distinction from the spec's decision).
      Update `test_an_empty_intersection_falls_back_to_the_visible_set` in
      `tests/component/test_estate_focus.py` — the row whose docstring says its premise needs
      revisiting when this decision lands; it now asserts the intersection is non-empty and
      denials flow. Update ADR-0059's Notes with a dated line: the span is unchanged (no case
      moved), operator's visible set grew. **One commit.**
- [X] T002 [P] [US4] [GATE:fail-closed] Rows in `tests/component/test_operator_sees_denials.py`:
      operator's visible set contains exactly the two new types and none of the other authority
      records; the estate-suite agreement row still passes untouched (asserted by running it —
      no span change was the measured claim, research F5); an operator's *"Which runs were
      denied?"* through the full ask path (surface_under_test) now answers, citing a denial
      record.

**Checkpoint**: the decision is made, one commit, and the loop US4 exists to close is closable.

## Phase 3: User Story 2 — the plan cell is earned (P1)

- [ ] T003 [US2] The plan subject in `tests/evals_live/test_gates_live.py`: `must_deny` and
      `must_decline` (the tool-choice pair, and only them) are parametrized over subject roles
      `("ask", "plan")`; the answering suites stay ask-only — a plan subject there would be the
      reverse of 030's mismatch. Same majority-of-three, same thresholds. The docstring records
      why: plan-role evidence for the first plan cell earned under ADR-0059's
      evidence-matches-claim rule.
- [ ] T004 [US2] `make evals-smoke` then `make evals-live` with the plan subject — run by the
      agent (key in `.env`), exit 0 required before any cell exists anywhere. Outcome recorded in
      `infra/environments/dev/variables.tf` as a dated comment beside the ask cells: plan-role
      evidence earned; **the cell itself is never seeded there** (US3's gate).

**Checkpoint**: plan-role evidence exists; nothing anywhere binds it yet.

## Phase 4: User Story 3 — the gates never meet the live cell (P1)

- [ ] T005 [US3] `infra/bin/model-run-demo`: capture the matrix and `planner-agent`/`vault-agent`
      binding records from Vault; seed (out of band, the credential's posture — never Terraform
      state) a `vault:anthropic/claude-opus@5:plan` live cell and point the demo definitions at
      it; **restore from the captured originals in a trap** so interruption cannot strand the
      estate; prove restoration by re-reading and comparing to the capture; then run the choice
      conformance lane against the restored fixture cells. Honest limit in the script header
      (research F3): the merge gate reads `variables.tf` and cannot see a Vault-side leftover —
      the compare-to-captured check IS the enclave safety net, plus the choice lane's dispatch.
- [ ] T006 [P] [US3] [GATE:conformance] The gate half: `make conformance`'s choice lane passes
      before the demo (fixture estate) and the script's final step re-runs it after restore. The
      merge-lane row (`test_the_merge_lane_needs_no_provider`) is asserted **unchanged** —
      `git diff` clean on that file — because a demonstration that widened it would trade the
      proof for the demo.

**Checkpoint**: the harness can seed, restore, and prove — without a vendor call yet.

## Phase 5: User Story 1 — the demonstration (P1)

- [ ] T007 [US1] The two bounded runs inside `model-run-demo`: **Run 1** dispatches vault-agent
      (bound to the live cell) on a clean read-shaped task, ≤5 steps; **Run 2** dispatches
      planner-agent on a task worded toward `apply` — the ceiling 020 built to be refused in —
      expecting ≥1 refusal from the existing enforcement. Both under the existing step caps;
      terminal stops honoured (a `ChooserUnavailable` or absent credential ends the run with the
      cause, never a fixture fallback — asserted from the trail, FR-003).
- [ ] T008 [US1] The read-back, in the script: print the trail lines proving SC-001/002/005 —
      `TOOL_CHOSEN` naming `anthropic/claude-opus@5`, the run's `AUTHORITY_REFUSED`/denial for
      Run 2, and the credential exercised under the allocation's identity (the fetch that closes
      027's T016b, observed live). Then the US4 closure: ask *"Which runs were denied?"* through
      the API as the operator and require the answer to cite Run 2's refusal.
- [ ] T009 [US1] Execute `bash infra/bin/model-run-demo` against the live enclave — run by the
      agent; ≤15 vendor calls. Record the outcome (trail excerpts, restore proof, the operator's
      answer) in this feature's `contracts/conformance.md`.

**Checkpoint**: the founding promise, demonstrated and read back.

## Phase 6: Polish

- [ ] T010 [P] ROADMAP entry for 031 + contract status rows; note 027's T016b closed and where.
- [ ] T011 `make check`, `make evals`, hermetic sweep, and `make conformance` green post-demo.

---

## Dependencies

```text
Phase 2 (T001 → T002)                 [hermetic; lands first]
  → Phase 3 (T003 → T004)             [vendor: +10 min lane]
    → Phase 4 (T005 → T006)           [no vendor]
      → Phase 5 (T007 → T008 → T009)  [vendor: ≤15 calls]
        → Phase 6 (T010 ∥ T011)
```

## Notes

- **No sealed core.** The trail vocabulary is consumed; if implementation finds a payload wanting
  to grow, that is a finding to surface, not a field to add.
- **The one review**: none beyond the standing ADR-0059 note — no new ADR, no amendment.
- **What would make this fail honestly**: the model refusing to over-reach in Run 2. The task
  wording may need iteration; the bound (≤15 calls) includes that headroom, and a Run 2 with no
  refusal is reported as what happened, not massaged.
