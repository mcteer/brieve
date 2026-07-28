# Feature Specification: MCP Surface

**Feature Branch**: `spec/009-mcp-surface`

**Path**: `specs/009-mcp-surface/spec.md`

**Created**: 2026-07-27

**Status**: Draft

**Input**: User description: "The MCP function, with CI coverage. Second of ADR-0033's four transports and the persistent service coding IDEs talk to. Scope includes the dependency health checks and the resume sweeper decided in ADR-0049, the continuous evidence-stream verification 008 deferred here, and the second CI lane that runs the enclave rows."

## Traceability *(mandatory)*

| Field | Value |
| --- | --- |
| **Requirements (R1–R17)** | R15 (four transports, one authorization core — and the first pass where **parity is assertable**). R2 / R3 (per-task authority: the surface authenticates and the subject flows onward, as in 008). R7 (fail-closed — a known-down dependency refuses *before* execution). R4 / R10 / R13 (evidence: the trail is now verified continuously rather than only at bring-up). R16 (sealed core — `RunState` changes shape). |
| **ADRs touched** | ADR-0033 (four transports; **the parity row becomes claimable here**), ADR-0049 (**Proposed** — consent to start is consent to finish; dependencies monitored, not escalated; this feature is where it is proven or amended), ADR-0026 (partially superseded by 0049 — `PARKED` goes), ADR-0048 (a suspended run's container ends; resumption is a new allocation with a new identity), ADR-0035 (evidence integrity, verified continuously). |
| **Evidence class** | Attestation-relevant and audit-critical. Two distinct reasons: it is a second identity-bearing surface, and it is the first component that *watches* the estate rather than acting in it — a health checker that lies about a dependency changes what agents are permitted to attempt. |

## Clarifications

### Session 2026-07-27

- Q: Why is MCP second rather than the CLI? → A: It is the surface with users already waiting — coding IDEs — and it is the one ADR-0049 needs to exist. The dependency health checks and the resume sweeper both require a long-lived home, and every other component in this platform is deliberately ephemeral. Doing MCP second gets the second transport *and* the service ADR-0049 assumes, in one pass.
- Q: Does this feature claim the four-transport parity row? → A: **Yes, and it must.** 008 refused it because parity is a property between transports and there was one; refusing it a second time when there are two would stop being rigour and start being avoidance. `specs/008-northbound-api/contracts/operations.snapshot.json` exists precisely so this comparison is against something recorded.
- Q: ADR-0049 is still Proposed. Is that a problem? → A: It is the point. The decision was left Proposed deliberately — "I'd hate to say it's accepted until we actually build it and see how testing goes." This feature builds it. It ends with ADR-0049 **Accepted, amended, or withdrawn on evidence**, and a feature that quietly leaves it Proposed has failed a requirement rather than merely deferred one.
- Q: Is the resume sweeper a human in the loop? → A: No — it is the mechanism that makes humans *not* be in the loop. A suspended run names the dependency it could not reach; the sweeper resumes it when that dependency recovers. No run polls, and nobody is told to press anything.
- Q: Why does the CI lane need its own feature rather than being a chore? → A: Because it is the only thing that closes a gap this repository has recorded twice and enlarged once. 005 recorded that no required check covers the durability rows; 008 added nine more enclave rows to the same uncovered set. The mechanism protecting them is an instruction in `AGENTS.md` that the agent harness follows — which is only as good as that instruction being obeyed.

- Q: "Equivalent audit events" — equivalent how? Identical would be false, since the transport differs. → A: **Same event types, same order, same subject, same decision fields; transport recorded as a field rather than as a structural difference.** Left vague this would be the easiest row in the feature to pass dishonestly: a comparison that only checks "both produced some audit" is satisfied by two surfaces that agree about nothing.
- Q: What is the granularity of a dependency? A product, an endpoint, a workspace? → A: **A named product, as the tool registry already names it.** Finer granularity is tempting and wrong here: per-workspace health would mean the checker enumerating a customer's estate, which is a much larger claim on their environment than "can we reach this product at all". FR-006 says products for that reason.
- Q: Who observes a dependency recovering — the sweeper polling, or the health checker pushing? → A: **The health checker owns reachability; the sweeper reads what it recorded.** One component decides what "healthy" means. Two would drift, and a run resumed against a dependency one of them thinks is down is exactly the failure suspension exists to prevent.
- Q: Does the MCP service authenticate to the API as itself or as the calling user? → A: **As the calling user.** MCP is a transport, not a principal — an agent acting on someone's behalf. A service account here would collapse every caller into one subject and destroy the non-repudiation the whole delegation chain exists for. This is the same reason FR-001 routes it through 008's interface rather than around it.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The same operation, through a second surface, gets the same answer (Priority: P1)

Someone invokes an operation through MCP that they could have invoked through the API. The
verdict is the same, the audit events are equivalent, and that equivalence is checked rather
than believed.

**Why this priority**: This is the row ADR-0033 has been owed since 008, and the reason the
transports were split into separate features at all. Four surfaces is where authorization
architectures usually go wrong — each acquires its own notion of who the caller is and its
own subtly different checks, and the classic outcome is an API that permits what the UI
forbids, found by an attacker or an auditor rather than a test.

**Independent Test**: Perform every operation in the recorded operation set through both
transports as the same subject; assert identical verdicts and equivalent audit events.

**Acceptance Scenarios**:

1. **Given** an operation available on both transports, **When** the same subject invokes it
   on each, **Then** both produce the same verdict.
2. **Given** the same pair of invocations, **When** the audit trail is read, **Then** the
   events are equivalent — differing in transport, not in what was decided.
3. **Given** an operation added to one transport and not the other, **Then** that is
   detected rather than discovered later.
4. **Given** MCP, **When** its authorization path is inspected, **Then** it reaches the same
   core as the API rather than a parallel one.

---

### User Story 2 - A run waiting on a broken dependency resumes without anyone noticing (Priority: P1)

A run cannot reach a product it needs. It records which dependency, suspends, and its
container ends. When the dependency recovers, the run resumes in a new allocation. Nobody is
prompted, and nothing is lost.

**Why this priority**: This is ADR-0049's central claim, and the alternative is what makes
the platform unusable at scale — one shared outage becoming thousands of individual people
being asked to intervene in runs they did not start.

**Independent Test**: Make a dependency unreachable mid-run; assert the run suspends naming
that dependency and its container exits. Restore the dependency; assert the sweeper resumes
the run in a **new** allocation and it completes.

**Acceptance Scenarios**:

1. **Given** a run whose next step needs an unreachable dependency, **When** it cannot
   determine the outcome, **Then** it suspends recording that dependency by name.
2. **Given** a suspended run, **When** its state is inspected, **Then** no container is
   running for it — a suspended run is a record, not an idle process holding a slot.
3. **Given** the dependency recovering, **When** the sweeper next runs, **Then** the run
   resumes in a new allocation with a new attested identity.
4. **Given** a resumed run, **When** it proceeds, **Then** it re-authenticates rather than
   replaying any pre-suspension credential.
5. **Given** a dependency that stays down, **When** the run's maximum duration is reached,
   **Then** the run stops with the reason recorded — the existing ceiling, not a new one.
6. **Given** any suspension, **Then** no human is notified or asked to act.

---

### User Story 3 - A tool call against a known-dead dependency is refused before it runs (Priority: P1)

An agent attempts an action against a product the harness knows is unreachable. The call is
denied before execution rather than attempted and observed to fail.

**Why this priority**: Not an optimisation. Attempting a call against a dead dependency
writes an intent record that must later be resolved by re-observation — against the same
dead dependency. The bracket that exists to make interrupted steps resolvable becomes the
thing that cannot be resolved.

**Independent Test**: Mark a dependency unhealthy; attempt a tool call against it; assert
the denial happens before execution, that no intent record is written, and that the denial
is audited.

**Acceptance Scenarios**:

1. **Given** a dependency known to be down, **When** a tool call against it is attempted,
   **Then** it is denied before execution.
2. **Given** that denial, **When** the trail is read, **Then** it is distinguishable from a
   policy denial — an operator must be able to tell "not allowed" from "not reachable".
3. **Given** that denial, **Then** no intent record was written.
4. **Given** the refusal path, **When** it is inspected, **Then** it runs inside the
   governed pipeline rather than beside it as a pre-check of its own.

---

### User Story 4 - The agent does the part it still can (Priority: P2)

A dependency is down. Rather than failing outright, the agent completes the work that does
not require it and returns that to the requester, saying plainly what it could not do.

**Why this priority**: A refusal that produces nothing wastes work the agent could have
done. Writing the Terraform and handing it back with "the workspace is unreachable" is a
legitimate outcome, and it is what a competent colleague would do.

**Independent Test**: With a dependency down, run a task whose plan-producing half needs
nothing from it; assert the output is returned and names what was not attempted.

**Acceptance Scenarios**:

1. **Given** a task with a reachable-and-unreachable split, **When** the dependency is down,
   **Then** the reachable part completes and is returned.
2. **Given** that result, **Then** it states which dependency was unavailable and what was
   therefore not attempted.
3. **Given** that result, **Then** it is not presented as a completed action.

---

### User Story 5 - The evidence trail is checked while the system is running (Priority: P2)

Stream integrity is verified continuously rather than only when someone brings the enclave
up.

**Why this priority**: 008 shipped the checker and called it from `make enclave-verify`,
which covers bring-up and not the running estate. A tamper-detection mechanism that only
runs when an operator happens to restart something detects tampering on a schedule the
tamperer chooses.

**Independent Test**: Tamper with a stream while the service runs; assert the verification
reports it without any operator action.

**Acceptance Scenarios**:

1. **Given** a running service, **When** a stream is truncated, **Then** the verification
   reports it without an operator running anything.
2. **Given** an untampered store, **Then** it reports clean — a check that always fires gets
   disabled.
3. **Given** a finding, **Then** it is surfaced where an operator will see it rather than
   only recorded.

---

### User Story 6 - CI runs the rows a human currently has to remember (Priority: P1)

A second CI lane stands up the enclave and runs the rows the fork-safe lane cannot.

**Why this priority**: The constitution says a blocking row with no automated runner must
name who runs it, and this repository has named the agent harness twice — for 005's seven
durability rows and again for 008's nine enclave rows. That is an instruction being
followed, not a control. Sixteen merge-blocking rows currently depend on it.

**Independent Test**: Open a pull request that breaks an enclave row; assert the lane fails
and the merge is blocked without a human having run anything.

**Acceptance Scenarios**:

1. **Given** a pull request from a branch in this repository, **When** CI runs, **Then** the
   enclave lane stands up the stack and runs the enclave rows.
2. **Given** a change that breaks an enclave row, **Then** the lane fails.
3. **Given** a pull request from a **fork**, **Then** the fast lane still runs and the
   enclave lane does not — it needs a licence secret, and a lane that exposed one to fork
   code would be a worse problem than the gap it closes.
4. **Given** the enclave lane, **When** its result is examined, **Then** a failure to stand
   up the enclave reads as a failure, never as a pass.

### Edge Cases

- What happens when the health checker itself cannot reach a dependency it is checking? It
  reports unknown, and unknown is treated as unhealthy. Guessing reachable is how a dead
  dependency gets called anyway.
- What happens when a dependency flaps? Suspension and resumption must not amplify it into
  a loop that consumes a run's whole duration budget.
- Can the sweeper resume a run whose grant has since been revoked? No. Revocation is
  unilateral and immediate (Principle IV); a resumed run manufactures fresh authority and
  fails to obtain it.
- What happens when two sweeper instances run at once? The same single-writer fencing 005
  established governs — a resumed run supersedes, and the loser's writes are rejected.
- Does the MCP service hold standing credentials? No. It is an allocation like everything
  else and presents its own attested identity.
- Does a suspended run hold a lease or a slot? No. Its container ends.
- What happens if the parity comparison finds a difference? The feature is not done. Parity
  is the row this feature exists to make claimable.
- Does anything here pause a run awaiting a human? No. That is ADR-0049's entire subject.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: MCP MUST be a client of the same authorization core as the API, reaching it
  through the interface 008 exposes rather than through a parallel path.
- **FR-002**: Human callers MUST authenticate against the organization's OIDC provider and
  machines by workload identity federation. No static credential, on any surface, ever.
- **FR-002a**: MCP MUST reach the authorization core **as the calling user**, never as
  itself. It is a transport, not a principal. A service account here would collapse every
  caller into one subject and destroy the non-repudiation the delegation chain exists for —
  and it would do so invisibly, because everything would still work.
- **FR-003**: The same operation invoked on MCP and on the API by the same subject MUST
  produce the same verdict and equivalent audit events, **asserted as a conformance row**.
- **FR-003a**: "Equivalent" MUST mean: same event types, in the same order, naming the same
  subject, carrying the same decision fields — with the transport recorded as a *field*
  rather than appearing as a structural difference. Without this the parity row is the
  easiest check in the feature to pass dishonestly, since "both produced some audit" is
  satisfied by two surfaces that agree about nothing.
- **FR-004**: This feature MUST claim the four-transport surface parity row. Deferring it a
  second time is not available: two transports exist, and the comparison is possible.
- **FR-005**: An operation present on one transport and absent from the other MUST be
  detected by a check rather than by review.
- **FR-006**: The harness MUST monitor the reachability of the products agents operate, at
  the granularity of a **named product** as the tool registry names it, and MUST treat an
  unknown result as unhealthy. Finer granularity — per workspace, per endpoint — would
  require the checker to enumerate a customer's estate, which is a far larger claim on
  their environment than asking whether a product answers at all.
- **FR-006a**: Reachability MUST have exactly one owner: the health checker records it and
  everything else reads what it recorded. Two components deciding what "healthy" means will
  drift, and a run resumed against a dependency the other one believes is down is precisely
  the failure suspension exists to prevent.
- **FR-007**: A tool call against a dependency known to be unreachable MUST be denied
  **before execution**, and MUST NOT write an intent record.
- **FR-008**: That denial MUST be distinguishable in the audit trail from a policy denial.
- **FR-009**: The dependency refusal MUST run inside the governed pipeline, not as a
  pre-check beside it. A second refusal path is a second authorization path.
- **FR-010**: A run whose step outcome cannot be determined because a dependency is
  unreachable MUST suspend, recording that dependency by name.
- **FR-011**: A suspended run's container MUST end. A suspended run is a record, not a
  process holding a slot.
- **FR-012**: A sweeper MUST resume suspended runs when their named dependency recovers,
  in a **new allocation** with a new attested identity, re-authenticating rather than
  replaying.
- **FR-013**: Suspension MUST expire against the run's existing maximum duration. No new
  ceiling, and no timeout that grants by default.
- **FR-014**: Nothing in this feature may notify, prompt, or wait on a human during a run.
- **FR-015**: `RunState.PARKED` and the parking path MUST be removed, per ADR-0049
  superseding ADR-0026. Suspension pending a named dependency replaces it.
- **FR-016**: An agent whose dependency is unavailable MUST be able to return the work it
  could complete, stating what it did not attempt and not presenting it as done.
- **FR-017**: Evidence-stream integrity MUST be verified continuously by the persistent
  service, not only at bring-up, and findings MUST be surfaced to an operator.
- **FR-018**: A second CI lane MUST stand up the enclave and run the enclave-marked rows on
  pull requests from this repository.
- **FR-019**: The enclave lane MUST NOT run for pull requests from forks, and the fork-safe
  fast lane MUST continue to run for them.
- **FR-020**: A failure to stand up the enclave in CI MUST read as a failure, never as a
  pass or a skip.
- **FR-021**: ADR-0049 MUST be resolved by this feature — Accepted, amended, or withdrawn on
  the evidence of building it. Leaving it Proposed is a failure of this requirement.
- **FR-022**: The conformance contracts naming the agent harness as responsible party MUST
  be updated to reflect which rows CI now covers, and which (if any) still depend on a
  human.

### Key Entities

- **Dependency health record**: What the harness believes about a product's reachability,
  and when it last checked. Unknown is unhealthy.
- **Suspended run**: A record naming the dependency a run is waiting on. Not a process.
- **Sweeper**: What resumes suspended runs on recovery. The reason no human is in the loop.
- **Parity comparison**: The assertion between transports — same verdict, equivalent audit
  events — measured against the recorded operation set.
- **Enclave CI lane**: The second workflow, licence-bearing and therefore not fork-safe.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of operations in the recorded set produce identical verdicts across both
  transports; zero differ.
- **SC-002**: 100% of paired invocations produce equivalent audit events, where equivalence
  is same types, same order, same subject, same decision fields.
- **SC-002a**: 100% of MCP-originated operations name the calling user as subject; zero name
  the MCP service.
- **SC-003**: An operation present on one transport and absent from the other is detected in
  100% of cases.
- **SC-004**: 100% of tool calls against a known-unhealthy dependency are denied before
  execution; zero write an intent record.
- **SC-005**: 100% of dependency denials are distinguishable in the trail from policy
  denials.
- **SC-006**: 100% of runs suspended on an unreachable dependency name that dependency; zero
  leave a container running.
- **SC-007**: 100% of suspended runs whose dependency recovers are resumed by the sweeper in
  a new allocation; zero replay a pre-suspension credential.
- **SC-008**: Zero runs are paused, prompted, or blocked awaiting a human.
- **SC-009**: Zero occurrences of `PARKED` remain in the tree.
- **SC-010**: Stream tampering is reported by the running service in 100% of cases, with
  zero false positives on an untampered store.
- **SC-011**: 100% of enclave rows run in CI for non-fork pull requests; zero run for fork
  pull requests.
- **SC-012**: A CI run whose enclave fails to come up reports failure in 100% of cases.
- **SC-013**: ADR-0049's status is not "Proposed" when this feature lands.

## Assumptions

- **This feature is large, and the size is the user's call rather than mine to reduce
  unilaterally.** It carries a transport, two ADR-0049 mechanisms, continuous verification,
  and a CI lane. A natural phasing is: the CI lane first (it protects everything after it),
  then the MCP transport and parity, then the health checks and sweeper. Recorded here so
  the option is visible during planning rather than discovered during implementation.
- **MCP is the first deliberately persistent component.** Everything else is ephemeral by
  design — ADR-0049 makes a run's container ending part of the guarantee. The asymmetry is
  the reason the sweeper and health checks live here, and it is worth being explicit that
  a long-lived service is a new shape for this platform rather than more of the same.
- The dependency health checks concern **products agents operate**, not the platform's own
  Vault and Postgres. Those failing is a different class of problem and is out of scope.
- **A production `IdentityFabric` still does not exist** (`ROADMAP.md`, Unassigned). This
  feature inherits that, as 008 did. Nothing here is proven against a real identity source.
- The parity comparison is against 008's committed operation snapshot. If that snapshot has
  drifted from the API, parity is measuring the wrong thing and the drift is the first bug.
- The enclave CI lane will be slower and less reliable than the fast lane, because it stands
  up real infrastructure. It is still the only thing that turns sixteen merge-blocking rows
  from an instruction into a control.

## Out of scope

- CLI and portal transports — each its own spec, both over the API.
- Capability packs and eval gates — a separate feature, and unnumbered until specified.
- Multi-region or DR topology.
- Row-level security on the evidence store (`ROADMAP.md`).
- A production `IdentityFabric` (`ROADMAP.md`, Unassigned).
