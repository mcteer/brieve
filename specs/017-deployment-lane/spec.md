# Feature Specification: A deployment lane — every deployed process is proven to run

**Feature Branch**: `spec/017-deployment-lane`

**Created**: 2026-07-31

**Status**: Draft

**Input**: User description: "A deployment lane — the served surfaces are stood up and each is proven to answer, so `build()` stops being the one code path nothing runs. Closes ROADMAP gap 0d, raised 2026-07-31 and claimed as the next feature. This is a GATE CLASS that does not exist, in the same sense 012's accessibility lane was: every existing lane asserts something about a process the test itself constructs, and this one asserts something about a process the deployment constructs."

## Traceability *(mandatory)*

| Field | Value |
| --- | --- |
| **Requirements (R1–R17)** | **R4** (evidence over claims — the whole of this feature. Every existing gate is evidence about a process the test built; none is evidence about the process a deployment runs, and the difference has now been paid for five times). |
| **ADRs touched** | **ADR-0047** (governs directly — a gate that cannot assert its guarantee must skip citing its deferring record rather than assert a weaker thing. This feature is the inverse case: gates that *passed* while the guarantee was absent, because they asserted about the wrong object). **ADR-0048** (the substrate this asserts against — a surface's identity is attested by the scheduler, and an assembly that asks for the wrong role fails at login rather than at a request). **ADR-0033** (the transports being asserted — the parity gate compares what the surfaces *offer*; this asserts that they *run*). **ADR-0025** (adjacency vs containment — a row reaching a surface from the host and one reaching it from inside an allocation are asserting different things, and which is correct is a clarification below). **None superseded, none amended.** |
| **Evidence class** | **Operational, and about the gates themselves.** This adds no records to the audit trail and changes no authority decision. What it changes is the meaning of a green run: today "all gates pass" is compatible with a process that has never started. |

## Clarifications

### Session 2026-07-31

- Q: The spec said "three served surfaces", but the dispatched run entrypoint has its own
  assembly and three of the five known instances of this failure class lived there. Is it
  in scope? → A: **Yes, in scope.** A gate excluding it would miss the majority of the
  defects motivating the feature.
- Q: SC-004 promised a "bounded, stated time" without stating one. Per-process or
  whole-gate? → A: **Per-process.** Each deployed process has its own wait; the gate has no
  total it is judged against. A whole-gate budget would report one slow process as the gate
  overrunning, which is the misattribution FR-004 exists to prevent.
- Q: What does the gate do about intermittent failure — retry, or not? → A: **No retry,
  ever.** This gate exists because a defect hid behind gates that passed; a retry policy is
  how it would hide again. A process that reached a working state on the second attempt did
  not reach it on the first, and that is the defect.

### Analysis pass 1 — 2026-07-31

- **FR-005 was fail-open.** Coverage keyed on a process opting in, so a definition added
  without enrolling was invisible: the gate could not fail for a process it never knew
  about. FR-005a inverts the default — every definition is a subject or an explicit,
  reasoned exclusion. A coverage mechanism that could not see a gap would have reproduced
  this feature's own subject matter one level up.
- **SC-008 had no way to be met.** It claimed the gate is deterministic while nothing ran it
  twice. Refusing retries (FR-014) without evidence of stability is a decision taken on
  hope, so SC-008 now requires demonstration.
- **US5 was P1 and sat after a P3 story.** Moved above US3; the identifier is unchanged
  because the task list references it.

### Analysis pass 2 — 2026-07-31

- **The determinism check could not have been built as written.** Pass 1 added it as a row
  in the package the gate runs, so running the gate from inside the gate recursed without
  bound. Moved one level out, into the runner. Pass 1's own remediation introduced this.
- **SC-006 and SC-008 are verified once at implementation, not by a recurring gate.** A
  Linux runner cannot check the macOS half of SC-006, and repeating the whole gate on every
  invocation would double the lane. The plan's "no named human runner is owed" is true of
  the rows and broader than what is true of these two criteria; the contract now says which
  is which.
- **Proving the directory is collected must not commit a failing row.** A deliberately red
  row on a branch whose lane is merge-blocking blocks every push until someone removes it.
  The probe now lives and dies inside one working session.

### Analysis pass 3 — 2026-07-31

- **The rows would have been collected before the surfaces existed.** Two individually
  correct decisions collided: name the directory in a lane at birth, and stand the surfaces
  up only after the batch job releases its reservation. Together they put the rows in a
  pytest line that runs before anything is deployed, so the gate would have failed on
  **every** invocation — an always-red gate being as useless as an always-green one, and
  quicker to get disabled. The runner script is now the lane that enumerates these rows, and
  it is the final line of `make conformance`, so ordering is a property of recipe position
  rather than of a workflow file nobody runs locally.
- **`--repeat` repeats the assertions, not bring-up.** SC-008 is about the gate's
  determinism; re-deploying each pass would measure the scheduler instead.
- Two wordings that named no referent: "the same verdict" as what, and "count rows" against
  which baseline. Both now say.

### Analysis pass 4 — 2026-07-31

- **The surfaces had no lifecycle, so the gate starved the checks it must not disturb.**
  Pass 3 moved the runner into the recipe without saying what happens to the processes it
  starts. They persisted, and on the *next* invocation held reservations while the
  conformance batch job tried to place — verbatim the failure `portal-up`'s header records.
  Invisible on a fresh automated runner, which gets one invocation; visible on a developer's
  second run. The gate's lifecycle (FR-007a) now requires it to leave spare capacity as it
  found it, and the
  runner stops only what it started, so a developer's own surfaces are left alone.
- **`harness_covered_by` was checked for one process out of two.** The contract claims
  coverage-elsewhere is checkable rather than assumed; for `mcp` it was assumed. Every target
  is resolved now.
- Two measurement wordings sharpened: the pre-existing row comparison uses collection counts
  rather than a full run on `main`, and FR-001 gets an assertion rather than resting on
  construction.

### Analysis pass 5 — 2026-07-31

- **Teardown had no failure path.** Pass 4 gave the gate a lifecycle and said "on success or
  failure", which destroys the allocation a developer needs to diagnose a red run — the
  captured stderr tail is often not enough, since the Vault-role refusal that motivated this
  feature appeared mid-log rather than at its end. The gate now leaves things standing on
  failure and says so, and a *failed* teardown fails the gate — swallowed, it returns the
  defect silently, reported green by the mechanism built to prevent it. (Both landed as
  separate sub-requirements and were consolidated in pass 6.)
- The first pass to find no HIGH. Passes 1–4 each found something that would have produced a
  gate that could not work; this one found two gaps in the failure path, both in the corner
  those four fixes kept adding to.

### Analysis pass 6 — 2026-07-31

- **Two MUSTs contradicted each other.** "Anything it starts, it MUST stop" and "on failure
  it MUST leave what it started running" were both requirements, and a reader following the
  first alone would build the unconditional teardown pass 5 had just removed.
- **The failure carve-out reintroduced the starvation it was carved out of.** Leaving
  processes standing after a failure means the *next* invocation meets them at the point the
  merge-blocking checks need capacity — before the gate, which runs last, can reclaim it.
  Locally that is the normal case, because the gate is re-run precisely when it failed.
- **Consolidated rather than patched.** Three sub-requirements accreted across two passes,
  each fixing the last one's defect, and the third introduced a contradiction with the
  first. FR-007a is now one requirement covering start, teardown-on-pass, leave-on-fail,
  early reclamation, and teardown failure — the corner is stated once instead of amended
  again.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A deployed process that cannot start fails the merge (Priority: P1)

A contributor changes something the served process depends on — a credential role name, an
environment variable a deployment definition supplies, a collaborator's constructor, the
order two migrations run in. Every existing gate passes, because every existing gate builds
the application itself with substitutes. The gate stands the surface up, the surface fails to
reach its trust fabric, and the run goes red naming the surface and the reason.

**Why this priority**: This is the gap. On 2026-07-31 the northbound API was found never to
have served a request in a deployed enclave — its assembly asked for a credential role bound
to a different job, so every login was refused and the process died during start-up. It was
found by a person running the bring-up script by hand. Without this story nothing else in the
feature matters, because the remaining stories all refine an assertion that does not exist.

**Independent Test**: Break one surface's assembly deliberately — point it at a credential
role that does not exist — and confirm the gate fails, names that surface, and reports why.
Then confirm the unbroken tree passes. Delivers the whole of the feature's value on its own.

**Acceptance Scenarios**:

1. **Given** a tree where every surface's assembly is correct, **When** the gate runs,
   **Then** every process reaches a working state within its own wait and the gate passes.
2. **Given** a surface whose assembly names a credential it cannot obtain, **When** the gate
   runs, **Then** the gate fails, names that surface, and surfaces the process's own error
   rather than only a timeout.
3. **Given** a surface that starts but never becomes ready, **When** the bounded wait
   elapses, **Then** the gate fails rather than hanging, and reports what that surface last
   said.

---

### User Story 2 - A process that starts without its dependencies is not counted as working (Priority: P1)

A surface starts, accepts connections, and answers — but never reached the trust fabric, or
holds no store connection, or read none of its configuration. A liveness check cannot tell
this apart from a healthy process. The gate asserts something only a correctly assembled
surface can produce.

**Why this priority**: Also P1, and inseparable from Story 1 in value. A gate that only proved
a port was open would have passed throughout the entire period the API could not start,
because a process that exits is indistinguishable from one that is slow to a checker that
retries. This is the difference between a gate and the appearance of one, which is what
ADR-0047 exists to prevent.

**Independent Test**: Start a surface with its trust fabric reachable but its own credential
unobtainable, and confirm the gate fails — even though the process is running and answering.

**Acceptance Scenarios**:

1. **Given** a surface that is running and accepting connections but obtained no credential,
   **When** the gate asserts against it, **Then** the gate fails.
2. **Given** a correctly assembled surface, **When** the gate asserts against it, **Then**
   the response distinguishes it from a process that read no configuration.
3. **Given** an unauthenticated request to a surface that requires identity, **When** the
   gate asserts against it, **Then** the refusal carries that surface's own reason rather
   than a generic rejection any process could produce.

---

### User Story 5 - The dispatched process is proven to run, not just to have run (Priority: P1)

A run is dispatched on demand rather than staying up. It has an assembly exactly as a served
surface does — it obtains its own attested identity, resolves authority, and writes evidence
— and it is where most of the known instances of this failure class have lived. The gate
causes one to be dispatched and watches it reach a working state.

**Why this priority**: P1, on the evidence rather than on symmetry. Of the five occasions
this failure class has been found, three were in the dispatched path: a resume operation with
no production caller, a sweeper that had not dispatched since the surface that owns it
shipped, and an observer the protocol could not call. A gate over long-lived surfaces alone
would have caught two of five, and the feature exists because of all five.

**Independent Test**: Break the dispatched process's assembly and confirm the gate fails —
distinguishing it from a run that was never dispatched at all.

**Acceptance Scenarios**:

1. **Given** a correctly assembled dispatched process, **When** the gate causes one to be
   dispatched, **Then** it reaches a working state within a bounded time and the gate passes.
2. **Given** a dispatched process whose assembly cannot obtain its identity, **When** the
   gate dispatches one, **Then** the gate fails and reports that process's own error.
3. **Given** a dispatch that never starts, **When** the bounded wait elapses, **Then** the
   gate fails and distinguishes "never dispatched" from "dispatched and failed".
4. **Given** records left by an earlier successful run, **When** the gate runs against a
   process that can no longer start, **Then** the gate fails — a prior run's evidence MUST
   NOT satisfy it.

---

### User Story 3 - The rule covers every deployed process, including the one already covered (Priority: P2)

Four processes are deployed — three that stay up and one dispatched on demand. One of them
already has a check of this kind, written after the same failure. The rule applies to all of
them by construction, so a process added later is covered without anyone remembering to add
it.

**Why this priority**: The existing check proves the shape works; what it does not do is
generalize. Leaving it a special case means the next process repeats the discovery. P2 rather
than P1 because a gate covering some of the processes is worth having on the day it lands,
and the rest can follow.

**Independent Test**: Add a deployed process with no assembly at all and confirm the gate
fails without anyone having written a check for it.

**Acceptance Scenarios**:

1. **Given** the set of deployed processes, **When** the gate runs, **Then** every one of
   them is asserted against, with none silently absent from the set.
2. **Given** a process newly added to the deployment, **When** the gate runs without any
   check being written for it, **Then** the gate covers it or fails for not knowing how.

---

### User Story 4 - A contributor can run the gate before pushing (Priority: P3)

Someone working locally can stand the surfaces up and run the same assertions the automated
run will make, and get the same answer.

**Why this priority**: Valuable and not load-bearing. The gap this feature closes is that the
automated run never did it; a contributor who could run it locally but does not is no worse
off than today. P3 because it must not distort the gate's design — a rule that only holds
where a developer remembers to run it is the situation being replaced.

**Independent Test**: Run the gate on a developer machine against a local deployment and
confirm it produces the same verdict the automated run produces for the same tree.

**Acceptance Scenarios**:

1. **Given** a local deployment with the surfaces up, **When** a contributor runs the gate,
   **Then** it reaches the same verdict as the automated run for the same tree.
2. **Given** a local deployment with the surfaces **not** up, **When** a contributor runs the
   gate, **Then** it fails with an instruction rather than passing or erroring obscurely.

---

### Edge Cases

- **A surface is slow rather than broken.** Bring-up installs dependencies before serving.
  The wait must be long enough that a healthy start is never reported as a failure, and
  bounded so a hung one fails the gate rather than the job's own timeout.
- **A surface crashes and is restarted.** A failed process is restarted automatically, so a
  surface can be *running* at the moment it is observed and have failed three times already.
  Observing the current state is not the same as observing a successful start.
- **The gate observes a surface from somewhere the surface is not reachable.** Where the
  assertion runs from is a real constraint rather than an implementation detail — see the
  assumption recorded about it.
- **The unbroken tree passes for the wrong reason.** A gate that would also pass against a
  deliberately broken surface asserts nothing. Whether that is demonstrated is a decision,
  not an afterthought — the repository has an established practice of break fixtures.
- **The deployment's resource envelope cannot fit the surfaces alongside what already runs.**
  Adding services at bring-up has previously left the merge-blocking checks unplaceable,
  which is worse than the gap being closed.
- **A dispatched process leaves records that outlive it.** A run that succeeded last week
  left evidence behind. A gate reading that evidence would pass against a process that can no
  longer start at all — which is the same mistake as a liveness check, one layer over.
- **A surface has no unauthenticated behaviour to assert against.** If every path requires an
  identity, the assertion needs an identity — a dependency on an external provider inside a
  merge gate.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The gate MUST exercise every deployed process using the same definitions a
  deployment uses, not a test-specific variant of them.
- **FR-002**: The gate MUST assert, for each deployed process, that it reached a working
  state within a wait stated **for that process**, and MUST fail rather than wait
  indefinitely. Each wait MUST be long enough that a healthy start is never reported as a
  failure — dependency installation precedes serving — and short enough that a hung process
  fails the gate rather than the surrounding job's own timeout.
- **FR-003**: The gate MUST assert something only a process that completed its assembly can
  produce. A response obtainable from a process holding no credentials and no configuration
  MUST NOT satisfy the gate.
- **FR-004**: On failure, the gate MUST report the failing process and that process's own
  account of what went wrong, rather than only that an assertion did not hold.
- **FR-005**: The gate MUST cover every deployed process by construction, so a process added
  to the deployment is covered without a check being written for it — or the gate MUST fail
  for not knowing how to cover it.
- **FR-005a**: Coverage MUST fail closed on **discovery**, not only on assertion. Every
  process definition in the deployment MUST either be a subject of the gate or be
  **explicitly excluded with a recorded reason**; a definition that is neither MUST fail the
  gate. A scheme where a process becomes a subject only by opting in is fail-open — the
  process nobody remembered to enrol is exactly the one nobody remembered to cover, and a
  gate that cannot see it reproduces this feature's own subject matter one level up.
- **FR-006**: The gate MUST NOT pass when a deployed process is absent, unschedulable, or
  repeatedly restarting. A process that never ran is a failure, never a skip.
- **FR-007**: The gate MUST NOT reduce the coverage of the existing merge-blocking gates, and
  MUST NOT prevent them running — including by consuming the resources they need.
- **FR-007a**: **The gate owns a lifecycle for the processes it starts, and the whole of it
  is stated here.** Three sub-requirements were patched into this paragraph across two
  analysis passes and ended up contradicting each other, so it is one requirement now:

  1. **Start.** The gate reuses any process already running and starts only what is missing,
     recording which ones it started. A process a contributor brought up themselves is not
     the gate's to manage.
  2. **On a passing run, stop exactly what it started.** Spare capacity returns to what it
     was. Otherwise those reservations starve the merge-blocking checks on the *next* run —
     a failure that passes on a fresh automated runner, which gets one invocation, and
     appears only on a reused one.
  3. **On a failing run, leave them standing and say so.** The allocation is what someone
     needs to diagnose the failure, and a captured log tail is often not enough — the
     credential refusal that motivated this feature appeared mid-log, not at its end. A
     failing gate blocks the merge, so nothing that recurs depends on that capacity yet.
  4. **Clear leftovers early, not late.** Because (3) leaves processes running, the *next*
     invocation must reclaim that capacity **before** the merge-blocking checks need it —
     and the gate itself runs last, which is too late. Locally a prior failure is the normal
     case: the gate gets re-run *because* it failed.
  5. **A failure to stop what it started fails the gate.** Swallowed, it returns the
     processes to persisting and the next run to being starved — reported green by the
     mechanism built to prevent exactly that.

  Clauses 2 and 3 are the pair that must be read together: an unqualified "always stop"
  destroys evidence, and an unqualified "always leave" starves the next run. Neither alone
  is correct, which is why they are no longer separate requirements.

- **FR-008**: The gate MUST be runnable by a contributor against a local deployment and reach
  the same verdict as the automated run for the same tree.
- **FR-009**: The gate MUST distinguish "the surface refused this request" from "nothing
  answered", and MUST treat only the first as evidence the surface is working.
- **FR-010**: Where the gate cannot assert a process's behaviour without a credential it has
  no way to obtain in an automated run, it MUST record that limit in the conformance contract
  rather than assert a weaker claim as though it were the intended one (ADR-0047).
- **FR-011**: The existing check asserting that one service is reached MUST be brought under
  the same rule rather than left as an exception — or the reason it remains separate MUST be
  recorded.
- **FR-012**: The gate MUST fail when a deployed process's assembly is deliberately broken,
  and this MUST be demonstrated rather than assumed.
- **FR-013**: The gate MUST assert against the dispatched process by causing one to be
  dispatched and observing it reach a working state — not by inspecting a previous run's
  records, which a process that no longer starts would still leave behind.
- **FR-014**: The gate MUST NOT retry a failed assertion, and MUST NOT treat a later attempt
  as superseding an earlier failure. A process that reached a working state on a second
  attempt did not reach it on the first, and that difference is a defect rather than noise
  to be absorbed.

### Key Entities

- **Deployed process**: Any process the deployment runs from its own definition, as opposed
  to a library a test constructs. The set of them is the gate's subject. Two shapes, and the
  rule is the same for both because the failure is:
  - **Served surface** — stays up and answers something that talks to it.
  - **Dispatched process** — starts on demand, does its work, and exits. It has an assembly
    exactly as a served surface does, and three of the five known instances of this failure
    class lived in it.
- **Working state**: The condition of having completed assembly and done the thing the
  process exists to do. For a served surface that is answering; for a dispatched process it
  is running to completion. Distinct from *running*, which a process that assembled nothing
  can also be in, and distinct from *exited*, which a process that failed immediately also
  is.
- **Assembly**: The step constructing a surface's real collaborators from its environment.
  The one code path with no coverage by construction, because every test builds substitutes
  instead.
- **Assertion of reach**: A claim that the deployed process, under its own identity, arrived
  at a capability — as opposed to a claim that the capability works, which the existing gates
  already make.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A process whose assembly cannot obtain its credentials fails the gate, and the
  failure names that process. Demonstrated against a deliberately broken assembly, not
  argued.
- **SC-002**: A process that is running but completed no assembly fails the gate. This is the criterion distinguishing this gate from a liveness check, and
  the one a naive implementation will not meet.
- **SC-003**: Every deployed process is covered, of both shapes. A process present in the
  deployment and absent from the gate's subjects is itself a failure — **including one the
  gate was never told about**, which is the case a subject list built by opting in cannot
  detect.
- **SC-004**: **Each** deployed process reaches a working state within its own stated wait,
  and one that does not produces a failure naming that process. The gate is **not** judged
  against a total: a single budget for the whole gate would report whichever process was slow
  as the gate overrunning, which is the misattribution FR-004 exists to prevent. A total may
  be reported as an observation; it is not a threshold.
- **SC-005**: Every merge-blocking gate that ran before this feature still runs afterwards,
  and none becomes unschedulable.
- **SC-006**: A contributor running the gate locally against the same tree reaches the same
  verdict as the automated run.
- **SC-008**: The gate produces the same verdict on repeated runs against an unchanged tree,
  **demonstrated by running it more than once rather than asserted**. A gate that sometimes
  fails a correct tree would be retried, and retrying is what returns this whole class of
  defect to invisibility — so intermittency in the gate is a defect **in the gate**, tracked
  as one, and not a reason to relax FR-014. Refusing retries without evidence that the gate
  is stable would be a decision taken on hope.
- **SC-007**: The five previously-found instances of this failure class are each assessed
  against the gate by inspection, and the assessment is recorded — **including any the gate
  would not have caught**, which bounds the claim rather than inflating it.

## Assumptions

- **The gate asserts reach, not correctness.** A collaborator wired to the *wrong* place
  still assembles and still answers. What this closes is the class where a collaborator is
  wired to *nothing*. Any statement that this feature proves the deployment correct would be
  an overstatement, and the conformance contract should say so.
- **The deployed processes are those the deployment currently defines** — three served
  surfaces and one dispatched. Adding a fifth is not in scope; being covered when one is
  added is (FR-005).
- **The existing bring-up script is the mechanism for standing surfaces up.** This feature
  introduces no second way to deploy them; a rule asserting against a deployment path nobody
  uses would assert nothing.
- **An automated run cannot obtain a human identity from an external provider.** Federated
  sign-in was configured against a real provider on 2026-07-31, but a merge gate depending on
  a third party's availability trades one flaky class for another. The gate is assumed to
  assert against behaviour reachable without a valid end-user token, which is why FR-003 and
  FR-009 are phrased around refusals rather than successes.
- **Where the assertion runs from is constrained by the container runtime.** A surface using
  host networking is reachable from the scheduler's host — which on a Linux runner is the
  runner, and on a developer's Mac is a virtual machine the developer's shell is not inside.
  A gate assuming the developer's shell could reach it would satisfy FR-008 in the automated
  run and fail locally for a reason unrelated to the tree. The repository already
  distinguishes checks that run on the host from checks that run inside an allocation, and
  this feature is assumed to use that distinction rather than invent one.
- **This gate does not replace the existing service-reach check; it generalizes it.** That
  check found a real defect and its shape is the precedent (FR-011).
- **Refusing to retry accepts a cost, knowingly.** Infrastructure noise will occasionally
  block a merge that would have passed. That is accepted because the alternative reintroduces
  the failure mode the feature exists to close: an assembly failing one start in three goes
  green on the retry and nobody learns. The mitigation is generous per-process waits
  (SC-004), so a slow start is never noise in the first place.
