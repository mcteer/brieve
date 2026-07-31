# Feature Specification: The MCP surface gets a server

**Feature Branch**: `spec/019-mcp-server`

**Created**: 2026-07-31

**Status**: Draft

**Input**: User description: "The MCP surface gets a server — a client attaches, and the transport that has been correct for four features finally answers something. Closes ROADMAP gap 0f, raised while scoping 'connect it to Cursor.' The expected answer was networking; that is real and it is not the problem."

## Traceability *(mandatory)*

| Field | Value |
| --- | --- |
| **Requirements (R1–R17)** | **R4** (evidence over claims — the surface-parity gate is in force against a class no client can reach, so what it asserts is narrower than it reads). **R2, R3** (the calling user's identity must survive the protocol boundary; a service account here would collapse every caller into one subject and destroy non-repudiation invisibly). |
| **ADRs touched** | **ADR-0033** (four transports, one authorization core — this makes the second transport a transport rather than a class). **ADR-0034** (the portal is a thin client over the API; the same relationship must hold for a client over MCP). **ADR-0048** (conformance gates bind to the deployed artifact — the reason a row against an object is not a row against a service). **None superseded, none amended.** |
| **Evidence class** | **Attestation-relevant.** Every operation reached through this surface writes to the hash-chained trail under a subject. Whether that subject is the calling user or the server is the difference between a delegation chain and a shared account, and it is invisible at every layer above the audit entry. |

## Clarifications

### Session 2026-07-31

- Q: If static ports turn out **not** to be reachable from the developer's machine, does
  reachability stay in this feature? → A: **It stays in scope and the feature absorbs it.**
  FR-014 holds regardless of cost. The accepted risk is a networking detour delaying the three
  correctness stories; the rejected risk was shipping a seventh thing that works where nobody
  can see it, which is the shape this feature exists to end.
- Q: Can one session carry operations for more than one subject? → A: **No — one session, one
  subject, fixed at the handshake.** A different caller means a different session.
  **This does not weaken FR-013**: the subject never changes, and the credential's *validity*
  is still evaluated on every operation. Fixed identity, re-checked authority — a session is
  not a grant.
- Q: May the served transport and the supervisory loop share fate? → A: **No — they MUST be
  independently available.** A protocol failure that stopped the sweeper would silently stop
  suspended runs from resuming, which looks like a hang and is not one, and would quietly end
  ADR-0049's guarantee that consent to start a run is consent to finish it.
- Q: Which client counts for SC-001? → A: **The protocol SDK's own client, driven by an
  automated row.** A real client speaking the real protocol, in a lane on every change, so the
  guarantee keeps holding rather than having held once. Connecting an IDE by hand stays
  possible and is what FR-015's written setup is for — it is not the gate.

## What already holds, and what does not

Stated first because the gap is narrow and easy to misread as larger or smaller than it is.

**Holds.** `McpTransport` executes every operation against the governed core, as the calling
user and never as itself, resolving the same collaborators the API resolves and calling into
the same place. Fifty-six conformance rows exercise it. The surface-parity gate is in force
against it. The protocol SDK is already a declared dependency.

**Does not hold.** `McpTransport` is constructed nowhere in the shipped source — its only
caller is a test fixture. No protocol framing exists anywhere in the tree. The job named for
the surface runs the supervisory loop (health checks, the sweeper, audit egress) and never
serves the transport, which is exactly what that feature owed and delivered; the module's own
docstring said the rest was next, and the sweeper's half landed while the transport's did not.

**Why nothing noticed.** The parity gate compares the transport *class* against the API's, and
the class is correct. So parity is asserted in force between one surface that answers real
requests over a real socket and one that no client can reach.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A client attaches and the platform answers (Priority: P1)

Someone points a standards-compliant client — an IDE, or the protocol SDK's own client — at
the platform. The client completes the protocol handshake, asks what tools exist, and gets the
same set of operations the other surface exposes. Nothing about governance is visible yet;
what is established is that the surface is a surface.

**Why this priority**: Everything else in this feature is a property *of* a served surface.
Without it there is nothing to hold the other stories against, and the gap this feature closes
is precisely that this step has never happened.

**Independent Test**: Attach a real client to the running platform, complete the handshake,
and enumerate the operations. Delivers the first moment in the platform's life at which an
external client can reach the second transport.

**Acceptance Scenarios**:

1. **Given** the platform is running, **When** a client performs the protocol handshake,
   **Then** the server responds and the session is established.
2. **Given** an established session, **When** the client asks what tools are available,
   **Then** it receives the operations the transport defines, and the set matches what the
   other surface exposes.
3. **Given** the platform is running, **When** the served process starts, **Then** it
   constructs the transport with real collaborators rather than substitutes, and refuses to
   start if it cannot.

---

### User Story 2 - The call is governed, and the refusal comes from the core (Priority: P1)

The client calls an operation. Governance runs — the same governance the other surface runs,
because it is the same core — and the call either proceeds or is refused. A refusal reaches the
client as a refusal it can act on, and it comes from the governed core rather than from the
protocol layer deciding something on its own.

**Why this priority**: A surface that answers but does not govern is worse than no surface. It
would look like the platform working while being the one thing the platform exists to prevent,
and every existing row would still pass.

**Independent Test**: Call an operation that must be refused and confirm the refusal
originates in the governed core; call one that must proceed and confirm it did. Delivers the
guarantee that reaching the platform through this door is not a way around it.

**Acceptance Scenarios**:

1. **Given** a session whose caller may perform an operation, **When** they call it, **Then**
   it proceeds and its outcome returns to the client.
2. **Given** a session whose caller may **not** perform an operation, **When** they call it,
   **Then** it is refused, the refusal is the core's and not the protocol layer's, and the
   client receives a refusal rather than an unexplained failure.
3. **Given** a refusal, **When** the client inspects it, **Then** it can distinguish "you may
   not" from "the platform is broken" — two conditions that would otherwise share a shape.

---

### User Story 3 - The trail names the caller, not the server (Priority: P1)

The operation is recorded in the tamper-evident trail. The subject on that record is the person
who called, carried from their own credential through the protocol boundary into the operation
— not the server's identity, and not a shared account standing in for everyone.

**Why this priority**: This is the sharp edge and it fails silently. A server that authenticated
itself and acted on everyone's behalf would work perfectly, pass every existing row, and quietly
convert a delegation chain into a shared account. Nothing above the audit entry would show it.

**Independent Test**: Two different callers perform the same operation; the trail distinguishes
them. Delivers the non-repudiation the whole delegation chain exists for.

**Acceptance Scenarios**:

1. **Given** a caller presenting their own credential, **When** they perform an operation,
   **Then** the trail records **them** as the subject.
2. **Given** two callers with different identities, **When** each performs the same operation,
   **Then** the trail distinguishes the two and neither appears as the other or as the server.
3. **Given** a caller presenting no credential or an unacceptable one, **When** they attempt an
   operation, **Then** it is refused, and the refusal happens before any governed operation is
   entered rather than after.

---

### User Story 4 - It is reachable from where a person actually works (Priority: P2)

The developer configures their IDE with an address and it connects. Not from inside the
platform's own network, where every existing check already runs — from the machine the person
is sitting at.

**Why this priority**: Independently valuable and independently testable, but the three stories
above are the ones that make the surface correct. A correct surface unreachable from a
developer's machine is a smaller problem than a reachable surface that answers as itself.

**Independent Test**: From the developer's own machine, outside the platform's network, connect
a client and complete the handshake. Delivers the difference between "the platform works" and
"I can watch it work."

**Acceptance Scenarios**:

1. **Given** the platform is running, **When** a client on the developer's machine connects to
   the documented address, **Then** the session establishes.
2. **Given** a working connection, **When** someone follows the written setup instructions from
   nothing, **Then** they reach the same result without needing to read source.

---

### Edge Cases

- **The credential expires mid-session.** Protocol sessions are long-lived and credentials are
  not. An operation attempted with a lapsed credential must be refused as lapsed, not served
  from whatever was established at handshake time — a session is not a grant.
- **The client calls an operation that does not exist.** Refused by the protocol layer as
  unknown, and distinguishable from an operation that exists and was denied. Collapsing those
  two tells an attacker which operations exist by which error they get, and tells an honest
  caller nothing useful.
- **The client sends input the operation cannot accept.** Rejected at the boundary with a
  message naming what was wrong, before any governed operation is entered.
- **The server cannot reach its collaborators at startup.** It must fail to start rather than
  start and answer wrongly. A surface that accepts connections while unable to record evidence
  is worse than one that is plainly down.
- **Two clients connect at once.** Neither sees the other's session, subject, or results.
- **The client disconnects mid-operation.** Whatever was started remains governed and recorded;
  a dropped connection is not a way to leave an operation half-recorded.

## Requirements *(mandatory)*

### Functional Requirements

**The server exists and is assembled from real parts**

- **FR-001**: The platform MUST run a process that speaks the standard protocol of this
  surface, such that an unmodified third-party client can establish a session with it.
- **FR-002**: That process MUST construct the transport with the same real collaborators the
  other served surface constructs — the governed core, the evidence sink, the durability
  provider, the run index — and MUST NOT substitute in-memory or test doubles for any of them.
- **FR-003**: The process MUST refuse to start if it cannot obtain what it needs to serve
  correctly, and MUST say which thing was missing. A surface that starts degraded and answers
  anyway is the failure mode this requirement exists to prevent.
- **FR-004**: The assembly MUST be exercised by an automated check against the **running
  process**, not against a constructed object. This is the one path no unit test covers, and
  the reason this feature exists is that it has never been covered.

**Every operation is governed**

- **FR-005**: Every operation reachable through this surface MUST pass through the same
  governed core the other surface uses. No operation may be served by protocol-layer logic that
  reaches the underlying capability directly.
- **FR-006**: A refusal MUST originate in the governed core. The protocol layer MUST NOT decide
  that a caller may not do something; it may only report that the core decided so.
- **FR-007**: A refusal MUST reach the client as a refusal — distinguishable by the client from
  a transport failure, a malformed request, and an unknown operation.
- **FR-008**: The set of operations this surface exposes MUST match the set the other surface
  exposes, checked mechanically rather than by inspection.

**The caller's identity survives the boundary**

- **FR-009**: Every operation MUST execute under the identity of the **calling user**, derived
  from a credential that caller presented, verified the way the platform already verifies
  credentials on its other surface.
- **FR-010**: The server MUST NOT execute any operation under its own identity, under a shared
  service account, or under any subject not traceable to a specific caller.
- **FR-011**: An automated check MUST demonstrate that **two different callers are
  distinguishable in the evidence trail** after performing the same operation. A check that
  only confirms "a subject was recorded" would pass against a shared account, which is the
  defect this requirement exists to catch.
- **FR-012**: An operation attempted without an acceptable credential MUST be refused before
  the governed operation is entered.
- **FR-013**: Credential validity MUST be evaluated **per operation**, not once per session.
  A session established with a valid credential MUST NOT continue to authorize operations after
  that credential is no longer valid.
- **FR-013a**: A session MUST bind to exactly one subject, fixed when the session is
  established, and that subject MUST NOT change for the session's lifetime. A different caller
  means a different session.

  **FR-013 and FR-013a are not in tension and the distinction is the point.** *Who* the session
  belongs to is settled once; *whether they may still act* is settled every time. Reading
  "fixed at the handshake" as "verified at the handshake" would produce a session that outlives
  the credential that opened it, which is the defect FR-013 exists to prevent.

**It is reachable, and the reachability is written down**

- **FR-014**: A client running on the developer's own machine, outside the platform's internal
  network, MUST be able to establish a session.
- **FR-015**: The address, credential, and configuration a client needs MUST be documented well
  enough that someone can connect from nothing without reading source.
- **FR-015a**: The served transport and the supervisory loop MUST be **independently
  available** — a failure of either MUST NOT stop the other. The supervisory loop is what
  resumes suspended runs, and a protocol crash that stopped it would present as a hang while
  quietly ending the guarantee that consent to start a run is consent to finish it.

**The gate proves itself**

- **FR-016**: Conformance rows for this feature MUST run against the **served process**. A row
  that constructs the transport in a fixture asserts what four features have already asserted
  and is not what this feature owes.
- **FR-017**: The feature MUST include a demonstration that the governance is load-bearing:
  a client presenting a credential that must be refused, observed being refused **by the core**.
  A gate nobody has seen fail is a gate nobody knows works.
- **FR-018**: The conformance contract MUST state what these rows do not assert, as prominently
  as what they do — specifically, that a served, governed, recorded surface does not mean a
  model is choosing anything.

### Key Entities

- **Served surface**: A running process a client connects to. Distinct from the transport
  class, which is what exists today — the distinction this entire feature turns on.
- **Session**: A client's connection, established once and used for many operations. Carries
  the caller's identity; **does not** carry a standing authorization.
- **Calling user**: The person on whose behalf every operation executes. The subject the
  evidence trail records.
- **Operation**: One of the actions the transport already defines, unchanged by this feature.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The protocol SDK's own client — unmodified, speaking the real protocol —
  establishes a session, enumerates operations, and successfully calls one against the running
  platform, **driven by an automated row so the guarantee keeps holding** rather than having
  held once.
- **SC-002**: 100% of operations exposed by this surface match the set the other surface
  exposes, verified mechanically.
- **SC-003**: For every operation invoked through this surface, the evidence trail records the
  calling user as the subject — 0 records attributed to the server or to a shared account.
- **SC-004**: Two callers performing the same operation are distinguishable in the trail in
  100% of cases.
- **SC-005**: An operation that must be refused is refused, and the refusal is attributable to
  the governed core rather than to the protocol layer, demonstrated at least once with its
  output recorded.
- **SC-006**: A person following the written setup instructions connects a client from their
  own machine without reading source. Connecting an IDE this way is what FR-015 serves; it is
  not the acceptance gate, which is SC-001.
- **SC-008**: Stopping the served transport leaves the supervisory loop running, and stopping
  the supervisory loop leaves the served transport answering — demonstrated, not asserted.
- **SC-007**: No conformance row that passed before this feature stops running, measured by
  per-directory collection counts against the prior state.

## Out of scope

Stated as an explicit section because a working demonstration invites a reader to conclude more
than it shows.

- **A model choosing anything.** This serves the transport; it does not put a model in the run
  loop. A dispatched run still selects tools by a scripted sequence (ROADMAP gap 0e). A client
  attached to this surface sees governance run, refusals refuse, and evidence get written —
  which is the platform working — but the tool *choice* remains scripted, and no artifact of
  this feature may imply otherwise.
- **New operations.** The transport's operation set is unchanged. This feature serves what
  exists; adding to it would change what parity means mid-flight.
- **The remaining two transports.** ADR-0033 names four. This makes the second one real.
- **Multi-tenancy.** Out of scope here as elsewhere until its own feature.

## Assumptions

- **The transport class is correct and stays unchanged.** Fifty-six rows and a parity gate say
  so. This feature adds a server around it; if serving reveals the class is wrong, that is a
  finding worth having and belongs in this feature's record.
- **Credential verification is a solved problem to reuse, not to rebuild.** The platform already
  verifies human credentials on its other surface, against a real identity provider. This
  feature carries a subject across a protocol boundary; it does not invent a second way to
  establish one.
- **Static ports on the platform's network are reachable from the developer's machine.** The
  other served surface and the portal are addressed this way and a browser on the developer's
  machine has reached them. Stated as an assumption rather than a fact because it was inferred
  from the portal's sign-in working rather than measured for this surface. **If it is wrong,
  FR-014 becomes the largest part of this feature rather than the smallest, and it stays in
  scope anyway** — settled in Clarifications. Planning MUST measure this before scoping the
  rest, because every estimate downstream depends on the answer.
- **The supervisory loop keeps its home.** The process that runs health checks, the sweeper, and
  audit egress is load-bearing and must not stop running because a transport moved in.
- **One demonstration is enough for FR-017**, recorded with its output, on the model 018 set —
  rather than an automated fixture that manufactures a bad credential on every run.
