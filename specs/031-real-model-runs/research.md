# Research: 031 — a real model drives a governed run

**Phase 0.** Measured against merged `main`, 2026-08-03.

## F1 — Everything the run needs already exists; nothing has ever exercised it together

`_chooser_for` resolves the binding, validates the cell, fetches the credential for a non-fixture
model (027, structural rows only), and builds a `ModelChooser` whose every choice passes
`invoke_tool` (020). The dev estate's three definitions all bind `fixture:` cells; the matrix's
plan cells are all fixture-qualified. The first real dispatch is therefore the first live exercise
of: binding→cell validation for a live plan cell, `BrokeredModelCredential` under `agent-run`'s
attested identity (T016b's owed half), and a paid model refusing/choosing under the ceiling.

## F2 — The plan subject slots into the existing lane shape

`test_live_suite` scores every suite under `_subject(pack, "ask")` with majority-of-three.
`must_deny`/`must_decline` are tool-choice suites — their prompts ARE over-reach and out-of-scope
shapes. Decision: parametrize the subject role for exactly those two suites (`ask` and `plan`),
leaving `citation_accuracy`/`estate_state` ask-only (they are answering suites; a plan subject
would be the reverse mismatch). Cost: 2 suites × 2 packs × ~5 cases × 3 samples ≈ +10 min.

## F3 — The demonstration's out-of-band posture, concretely

The credential set the precedent: written via Vault API, never in Terraform state, so an apply
cannot clobber it. The demonstration does the same for two records: a `plan` live cell appended
to the matrix KV record, and a demo definition-binding pointing at it. Restore = rewrite both
records from the seeded Terraform values (read back before seeding). Interruption-safe order:
capture originals → seed → run → restore in a trap. **The merge gate runs last as proof** — it
reads `variables.tf`, which never changed; the *enclave* state is proven restored by re-reading
the matrix record and comparing to the captured original, plus the gate's dispatched rows passing
against fixture cells.

Correction to the gate's reach, measured: `test_the_merge_lane_needs_no_provider` inspects
**variables.tf**, not the live Vault record — so a leftover live cell in Vault would NOT fail it.
The honest safety net for the enclave state is a check the demo script itself runs (compare
restored record to captured original) plus the choice-lane conformance runner, which reads the
live matrix and would dispatch against whatever is there. The contract states this precisely
rather than over-claiming the gate.

## F4 — The over-reach run is already authorable

`planner-agent`'s ceiling holds `echo`/`plan` while `apply` is registered — 020 built it as "the
fixture a choice can be refused in". A real model given a task nudging toward `apply` produces a
real refusal (`AUTHORITY_DENIED`/refused recording via the existing enforcement). Run 1: vault-ish
task, clean completion. Run 2: planner-agent, task worded toward apply, expect ≥1 refusal.
Bounded: `invoke_tools` runs cap steps already; demo dispatches with the existing caps.

## F5 — The visibility change does not move the suites

`operator` += `AUTHORITY_DENIED`, `AUTHORITY_REFUSED` in `ROLE_VISIBILITY`. Measured: no estate
case's expected set changes, so no `asker_role` tag changes, so ADR-0059's declared span
({operator, compliance-analyst}) is untouched and the agreement row keeps passing. What changes
behaviourally: an operator's "which runs were denied?" now reaches denial records (029's focus
maps denied→AUTHORITY_DENIED/REFUSED; the intersection is now non-empty). ADR-0059 gains a dated
note. The empty-intersection focus row in test_estate_focus (which asserts DENIED ∉ operator's
visible set) fires on this change by design — its own docstring says "this row's premise needs
revisiting" — and is updated as the deliberate step it exists to force.

## F6 — Cost bound

2 runs × ≤5 steps × 1 choice call/step + retries ≈ ≤15 calls; plus the lane's +10 min plan
subject. Stated in quickstart before anything runs.
