# Conformance: Wire resume into the dispatched path

**Feature**: `specs/014-dispatched-resume` | **Date**: 2026-07-29 | **Status**: Planned

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
