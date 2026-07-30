# Contract: Durability conformance lane

**Feature**: `specs/005-durable-execution`
**Status**: Planned
**Depends on**: Constitution Quality Gates; ADR-0024; ADR-0026; ADR-0047

## Purpose

Define the durability rows and record that they are **in force** from the moment this feature
lands (ADR-0047). Until then they are absent — never stubbed green.

## Command

```text
make conformance
```

Runs `tests/conformance` with the local enclave available. The durability rows require Vault and
Postgres; `make dev-up` is a prerequisite for them, not an alternative to them.

## Rows in force (all seven)

| Row | Asserts | Spec |
| --- | --- | --- |
| Kill / resume | A disrupted run resumes and completes; already-completed steps show exactly one execution across the whole run | FR-006, SC-001 |
| Re-authenticate, never replay | Resume manufactures fresh authority; no checkpoint contains credential material; a pre-disruption credential is not honoured | FR-003/004, SC-002/003 |
| Re-observe, never re-execute | An interrupted non-repeatable step is resolved against observed external state, in both directions | FR-006/007, SC-005 |
| Fencing against double resume | A superseded holder's tool calls and checkpoint writes are rejected; zero side effects, zero state mutation | FR-009, SC-006 |
| **Stop** on grant expiry | Resume under expired consent **stops** with the reason recorded and zero subsequent steps. Terminal — renewed consent does **not** revive it | FR-005, SC-004 |

### What these rows assert, and what they do not (recorded 2026-07-29)

**Every row above asserts `resume_run()` — the library function — and none of them asserts
that a dispatched run reaches it.** The distinction was invisible until 013 traced the path,
and it matters because the table reads as a claim about the deployed system.

The chain is closed except at its last link. A trust-fabric outage mid-run calls
`suspend_for_dependency` (`core/hooks/authority.py`), so `SUSPENDED` is reachable in
production. The MCP service's supervisory loop sweeps on dependency recovery and
re-dispatches. The sweeper carries `step_index` from the suspended-run index, the dispatcher
puts it in Nomad metadata, and the jobspec maps it to `RUN_STEP_INDEX`. **Then
`src/surfaces/dispatch/entrypoint.py` never reads it, and never calls `resume_run`** — it
calls `start_governed_run` and its step loop begins at zero.

So "a disrupted run resumes and completes; already-completed steps show exactly one execution"
is demonstrated of the function and not of the path a dispatch actually takes. `resume_run` has
**no caller anywhere in `src/`**.

**Why this is not a live defect today**, stated so the severity is not overread: the fixture
toolset is `echo`, which is repeatable and has no external effect; `record_intent` and
`record_result` are `ON CONFLICT DO NOTHING`, so re-recording a bracket is a no-op; and
dispatched tool invocation is opt-in (`RUN_INVOKE_TOOLS`), set today only by 013's conformance
row. Redoing steps currently costs nothing observable, which is why five features did not
notice.

**Why 013 made it consequential.** The Vault pack declares `vault_write` as non-repeatable
with an observer, precisely because replaying a check-and-set write is wrong. The observer
exists so an interrupted write is resolved *by observation* — and nothing on the dispatched
path consults it. The first feature to dispatch real write work inherits a resumed run that
re-executes from step zero with no re-observation.

**Owed:** wiring `resume_run` into the entrypoint, and a row asserting the property end to end
through a *dispatch* rather than through a function call. Until then these rows stay in force
for what they assert, with this note as their scope.
| Duplicate side-effect rejection | A repeated step carrying the same stable key is recognised as the same step | FR-010, SC-001 |
| Drain across upgrade | A controlled in-process handover preserves the run and its evidence | FR-015, SC-008 |

## What this row asserted before, and why it changed

It read *"Parking on grant expiry — resume under expired consent parks with zero
subsequent steps; **renewed consent permits resume**"*. That last clause was the
re-consent loop ADR-0049 supersedes: it assumed a human being asked to extend consent
mid-run, and there is no such human. A run reaching its grant's end has hit an execution
bound, and bounds are not renegotiated while the run waits.

The constitution named this row *"grant-expiry parking"* in its Quality Gates. It now says
*"grant-expiry stop"* — amended in 009 (v1.2.0) with a Sync Impact Report, in the same
change that removed `PARKED` from the sealed core. A gate row describing a state nothing
can enter is worse than a missing row: it reads as covered.

`PARKED` conflated two things. The other half — waiting on a machine condition that clears
itself — became `SUSPENDED`, which 009 introduces along with the sweeper that resumes it.
That is not this row, and deliberately so: one is a bound, the other is a wait.

## Break fixtures (FR-014)

Each row ships a fixture demonstrating it **fails** when its guarantee is weakened. Following
004's pattern, break fixtures are **self-verifying**: they construct the weakened arrangement and
assert the check raises, so they pass on a clean tree. A row whose failure nobody has observed is
a row nobody knows works.

## Provider independence

Rows are written against the seam, not an implementation (FR-012). Running them against a second
provider must require no rewriting — that is the executable form of ADR-0024's central claim.

## CI runs these rows on same-repo pull requests (as of 009)

`make conformance` runs all seven. The fast lane runs `make conformance-hermetic`, which
does not — it is fork-safe with no required secrets and cannot stand up a licensed Vault
Enterprise.

**009 added a second lane that can.** `.github/workflows/enclave.yml` installs Nomad,
Vault, and Terraform, brings the enclave up, and runs `make conformance` with the licence
supplied as a repository secret. These seven rows are now covered by a required check on
same-repo pull requests.

**Fork pull requests remain uncovered, and structurally must.** A fork-originating workflow
run cannot read repository secrets — GitHub's design, and the correct one. The lane is
conditioned on `github.event.pull_request.head.repo.full_name == github.repository` so it
does not fail every external contribution in a way indistinguishable from a real
regression.

The responsible-party record therefore narrows rather than disappears:

| Where the change comes from | What covers these seven rows |
| --- | --- |
| Same-repo branch or pull request | The enclave lane. A required check, and it fails the merge |
| Fork pull request | **The agent harness in the IDE**, per `AGENTS.md` — unchanged |

One property holds across both and was the entire safety margin when a human was the only
runner: these rows **fail loudly when the enclave is absent** rather than skipping. A false
green is not obtainable by running them in the wrong place — only by not running them.

**The grant-expiry row changed meaning, and was not deleted.** ADR-0049 supersedes the
re-consent loop it asserted: a run reaching its grant's end now stops with the reason
recorded rather than parking for a human. The row still exists and still blocks; it asserts
the inverted disposition. Deleting it would have removed the only check that a run reaching
its ceiling does anything deliberate at all.

## Honest limits

- **Single-node.** The enclave runs one Vault node and one Nomad server. Fencing and parking are
  proven against single-node behaviour; multi-node partition is not exercised. Recorded so the
  conformance claim is not read as broader than it is.
- **Drain-across-upgrade is simulated** as a controlled handover, not by upgrading a running
  deployment.
- **Parking has no consent surface.** Parked runs are observable and resumable programmatically;
  the human-facing surface is Control Groups (ADR-0016) and northbound (ADR-0033), both out of
  scope.

## Invariants

1. Conformance failures are merge-blocking for durability changes (as 004 established for the
   adapter lane).
2. These seven rows move from deferred to in force when this feature lands, and
   `contracts/conformance-adapter.md`'s deferred list is updated in the same change.
3. No row is represented by a passing stub at any point.

## Related

- [durability-seam.md](./durability-seam.md)
- [grant-and-resume.md](./grant-and-resume.md)
