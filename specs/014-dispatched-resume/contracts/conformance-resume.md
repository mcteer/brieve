# Conformance: Wire resume into the dispatched path

**Feature**: `specs/014-dispatched-resume` | **Date**: 2026-07-30 | **Status**: **In force —
every row below passes against the live enclave**

## Row status, as of the implementation run of 2026-07-30

This table is at the top of the file on purpose. **This feature exists because a claim outran
its evidence**, so a contract listing rows without saying which ones run would be the same
defect in the document that records it.

| Row | State | Evidence |
| --- | --- | --- |
| Disrupt and complete, exactly once | **In force** | 400 bracketed steps, allocation killed at step 3 by the scheduler, exactly 400 `TOOL_OUTCOME` events across both allocations, distinct credential ids, `RUN_RESUMED` attempt 1. `test_dispatched_resume.py`, 5m03s |
| A fresh dispatch is not a resume | **In force** | Same file, 6m45s. The id-collision pair: the flag on a finished run does not re-enter its work; the same identifiers with no flag produce no `RUN_RESUMED`, so nothing inferred a resume |
| Fresh authority, nothing crosses | **In force** | Credential distinctness inside the exactly-once row; the no-secret sweep over `grants` and `checkpoints` against the LIVE tables in `test_dispatched_no_secret_sweep.py` |
| Re-observe, both directions, live | **In force** | `test_dispatched_reobservation.py`. Real Vault, the shipped `VaultWriteObserver`; each direction arranges the product's state and cleans up. Landed → 2 invocations; not landed → 3 |
| Suspension names the product | **In force** | `test_dispatched_suspension_cycle.py`. Suspends awaiting `terraform`, files an index row carrying roles/packs/steps, exits **zero** |
| The sweeper revives it | **In force** | Same file, 1m30s for the pair. `record_probe("terraform", reachable=True)` → the sweeper re-dispatches with no human action, recorded as attempt 2. **The 009 sweeper's first end-to-end demonstration** |
| The cap is terminal | **In force** | `test_dispatched_cap_is_terminal.py`, 6 dispatches. Exactly five revivals, then STOPPED `resume_attempts_exhausted` with exit 0, then the sweeper drops the exhausted candidate and never revives it again |
| Expired consent stops, terminally | **In force** | `test_dispatched_grant_expiry.py`, 6m30s. Stops with the reason, zero further steps, zero invocations; a re-issued grant revives nothing |
| Fencing holds through dispatch | **In force** | `test_dispatched_fencing.py`. A resume dispatched under a still-running incumbent: 401 invocations for 400 steps, lease held by the successor, two issuances |
| `RUN_RESUMED` is in the trail | **In force** | `test_run_resumed_in_trail.py`. 1-based across a sequence of three, ordered first, and the hash chain verifies across allocation boundaries |

## Break fixtures — applied, watched to fail, reverted

| Fixture | Row that caught it | Outcome |
| --- | --- | --- |
| The entrypoint ignores the `resume` flag | suspension cycle | **Caught**, 1m46s: "the revival was not recorded" — no `RUN_RESUMED` at all, because the dispatch started fresh |
| The grant load is skipped and consent fabricated | grant expiry | **Caught**, 4.6s: the run continued under lapsed consent (`run_state=None` where `stopped` was required) |
| The attempt is counted **before** the ownership claim | `test_resume_cap.py`, `test_resume_claims_before_observing.py` | **Caught** instantly by three rows, two of them the ones named for it |
| The cap is read from dispatch metadata | cap-is-terminal | **Not exercised.** The other three were, and this one costs a seven-minute row to demonstrate a property already asserted structurally: `resume_run` has no parameter to pass a cap through, and `test_resume_cap.py::test_the_cap_cannot_be_supplied_by_a_caller` reads the signature. Recorded as a gap rather than implied to be done |

**A note on the third fixture.** The contract described it as "the fencing row burns attempts
it must not", which reads as though a superseded claimant could burn one. It cannot:
`RunLease.acquire()` is an unconditional supersede and never fails for a loser. The property
is real and the mechanism is a claim that *errors* — an unreachable store — and the rows drive
it that way.

## What the fencing row establishes, precisely

**At most one in-flight call survives the supersede**, not zero. The lease is asserted before
a handler runs, so a call already past the check completes; you cannot un-invoke work that is
already executing. A row demanding zero would fail forever while describing a correct platform
as broken. The bound is `steps + 1`, which still separates working fencing from absent fencing
by a factor of a hundred — an unfenced incumbent runs on to the end of its own step list.

The point of this contract is its lane: **every row here runs through a real dispatch**, in
the merge-blocking enclave lane beside 005's existing rows (clarify Q2). The feature exists
because function-level rows were mistaken for these, so this contract's rows are defined by
what they drive — the scheduler — not by what they call.

## The dispatch-level rows

| Row | Asserts | Via |
| --- | --- | --- |
| Disrupt and complete, exactly once | A multi-step dispatched run killed mid-flight resumes in a new allocation and completes, with every already-completed step showing exactly one execution across the whole run (SC-001) | `nomad alloc stop` on a multi-step run; sweep; count effects |
| Fresh authority, nothing crosses | The resumed allocation manufactured its own authority; zero credential material in checkpoints **or the grants table** (SC-002/003) | The 005 no-secret sweep, extended to `grants` |
| Re-observe, both directions, live | An interrupted `vault_write` whose effect landed is not re-executed; one whose effect did not land proceeds — both against real Vault with the shipped observer (SC-004/004a, clarify Q3) | Arrange each external state at the probe path before resuming |
| Suspension names the product | An open `terraform_apply` intent resumes to `CANNOT_DETERMINE` and suspends awaiting `terraform` — the product, not the tool (SC-005) | D5 harness: the fixture observer answers CANNOT_DETERMINE by design |
| The sweeper revives it | `record_probe("terraform", reachable=True)` → the suspended run re-dispatches with no human action (SC-006) | The 009 sweep, end to end for the first time |
| The cap is terminal | A flapping dependency revives the run exactly `RESUME_ATTEMPT_CAP` times; the next suspension is a STOPPED with `resume_attempts_exhausted`, and it never suspends again (SC-006a) | Flap the D5 harness in a loop |
| Expired consent stops, terminally | A resume under a lapsed grant stops with the reason recorded, zero subsequent steps; a renewed grant revives nothing (SC-007) | Short-TTL grant; wait; sweep |
| Fencing holds through dispatch | A superseded allocation's tool calls and state writes are rejected — zero side effects (SC-008) | Overlap old and new allocations deliberately |
| A fresh dispatch is not a resume | The same identifiers without the `resume` flag start fresh and skip nothing (FR-002, the id-collision edge case) | Dispatch with a used run_id, flag unset |
| `RUN_RESUMED` is in the trail | Every revival appears with its attempt number and outcome, before its consequences (FR-017) | Read the trail through the evidence path |

## The re-scoping obligation (FR-020)

The moment these rows are in force, `specs/005-durable-execution/contracts/conformance-durability.md`'s
scope note — *"every row above asserts `resume_run()` the library function"* — is **replaced**
with a pointer here, and `ROADMAP.md` gap 0a closes. Any property that remains function-only
keeps its scope note. Leaving the note after the rows land would be the inverse defect:
evidence outrunning the claim.

## What these rows do not prove

- **Recovery under real product outages.** The suspension harness uses the terraform fixture
  product because stopping Vault would take the trust fabric down with it (D5). A real
  product outage exercises the same code path with worse timing; the rows prove the path,
  not the chaos.
- **The cap's value is right.** Five is a starting constant (D3). The rows prove exhaustion
  is terminal and recorded — not that five is the number an operator wants.
- **Cross-feature resume.** These rows resume runs this feature's harness started. A run
  checkpointed by an older build resuming under a newer one is a compatibility claim nobody
  has made yet.

## Break fixtures worth naming

- The entrypoint ignores the `resume` flag → the exactly-once row fails on a double effect.
- The grant load is skipped → the expired-consent row completes when it must stop.
- The count increments before the lease claim → the fencing row burns attempts it must not.
- The cap check reads dispatch metadata → a crafted dispatch raises its own cap; the
  cap-is-terminal row must catch the fifth-plus revival.

## Who runs these

| Where the change comes from | What covers these rows |
| --- | --- |
| Same-repo branch or pull request | The enclave lane. Required checks — same as 005's durability rows |
| Fork pull request | The agent harness in the IDE, per `AGENTS.md` |
