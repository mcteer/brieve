# Feature Specification: The trail records who looked, or the surface stops saying it does

**Feature Branch**: `spec/022-audited-reads`

**Created**: 2026-08-01

**Status**: Draft

**Input**: Connecting a real editor to the MCP surface and asking the platform what it had just
done. The answer came back. The question left no trace.

## Traceability *(mandatory)*

| Field | Value |
| --- | --- |
| **Requirements (R1–R17)** | **R4** (evidence over claims — the subject here is the trail's own completeness, and a gap in it is invisible to everyone who trusts the trail). **R10** (observability and attestation — a record of who read what is an attestation input, not a convenience). |
| **ADRs touched** | **ADR-0035** (the load-bearing one: *"evidence access is itself audited — who reviewed which evidence, when. A meta-audit record, because the integrity of an audit trail includes knowing who read it"*. **Amended, not merely consumed.** Clarification extended that discipline past the audit plane to records **about** runs and threads, while keeping the ADR's own structural safeguard: the meta-audit goes to a separate stream, never into the chain being read — see FR-005a and FR-012). **ADR-0009** (one correlation ID joins prompt → hooks → call → run → audit entry, walkable both directions; a read that writes nothing is a step in that walk with no entry). **ADR-0033** (four transports over one authorization core — whatever is decided binds on API and MCP identically; parity currently *holds*, at zero). **ADR-0018 / ADR-0032** (the shape of the get_run_result asymmetry: the report is governed and audited, the payload it deliberately excludes is neither). **ADR-0047** (whether a new gate row binds now). |
| **Evidence class** | **Attestation-relevant, and about attestation itself.** Every prior feature added records. This one asks whether the record of *reading* those records exists — the question an auditor asks second, after "what happened", and the one this platform currently cannot answer for nine of its seventeen operations. |

## Clarifications

### Session 2026-08-01

- Q: Which operations must record a trail entry? → A: **B** — every operation touching a **run or
  thread**, reads and creations alike. Catalogue reads (`list_agent_definitions`,
  `get_agent_definition`) do not record: they disclose configuration rather than activity, and
  they are the highest-frequency reads a connected client makes.
- Q: Where does a read record live — the read object's own chain, or a separate stream? → A: **C**
  — a dedicated reader stream that **carries** the correlation id as a field. Findable by run
  without the run's own chain ever being altered by someone reading it.
- Q: What happens when a covered read's own record cannot be written? → A: **A** — the read fails,
  for all six covered operations. One posture, matching both existing precedents. Accepted cost: a
  trail outage makes runs and threads unreadable.

## What already holds, and what does not

**Holds.** The audit plane is genuinely a governed read path. `read_evidence` writes
`evidence_read`; a refused one writes `evidence_read_refused`; `reconcile_evidence` and
`get_run_report` both audit. ADR-0035's promise — that reading the evidence is itself evidence —
is kept for the evidence plane, and 021 kept it for reports. Reconciliation, mapping collection,
mapping requests, turns, and thread deletion all leave records.

**Does not hold, and was found by using the platform rather than by reading it.** Nine
operations touch runs, threads, and agent definitions and write nothing at all. Measured against
the running service on 2026-08-01, not inferred from the source:

| Operation | Returns | Trail entry |
| --- | --- | --- |
| `list_runs` | run ids, correlation ids, agent definition ids, states, timestamps | **none** |
| `get_run` | one run's record | **none** |
| `get_run_result` | **the run's result** — `payload[RESULT_KEY]`, not the whole checkpoint | **none** |
| `list_threads` | the subject's threads | **none** |
| `get_thread` | one thread and its turns | **none** |
| `create_thread` | a new thread | **none** |
| `list_agent_definitions` | the definitions available to the caller | **none** |
| `get_agent_definition` | one definition, including its bound model and tool scope | **none** |
| **`stop_run`** | **terminates a run — a write, not a read** | **none** |

`start_run` is **not** in this table. It writes nothing at the transport layer, but
`start_governed_run` writes `authority_issued` and `run_start`, so the act is recorded. Naming it
as a gap would be wrong.

**`stop_run` is in the table, and an earlier draft of this spec wrongly exempted it alongside
`start_run` — asserting coverage it called "measured" and had not measured.** The correction is
recorded rather than quietly applied, because the error is the same one the feature exists to
close, committed inside the feature that closes it. `stop_run_for` writes a `CheckpointBlob`
carrying `written_by=f"stop:{subject_user_id}"` and returns. There is no `append_event` in the stop
path and no `STOP`, `CANCEL`, or `WITHDRAW` member in `AuditEventType`. The only attribution lives
in a durability field — not hash-chained, not reachable through the governed evidence path.

**This is the worst of the nine, not one more of them.** The other eight are reads: no trace of who
looked. This is a person deliberately withdrawing consent and ending a run — the operation whose
own implementation says *"only the person who gave consent may withdraw it"* — leaving nothing a
reviewer can find.

**Three things make this worse than a missing feature.**

**The surfaces claim otherwise.** Every client that connects to the MCP surface is told, in the
instructions it receives at initialize: *"Every operation executes as the calling user and is
recorded in a tamper-evident trail."* Nine operations do not. This is the third self-description
in two days measured against the running service and found false, and the first where the
overclaim is about governance rather than capability.

**`get_run_result` inverts a protection 021 built deliberately.** `RunReport` omits the run's
result payload on purpose — the report is tenant-scoped, `get_run_result` is restricted to the
subject who started the run, and carrying the payload into the report would route around that
restriction. The reasoning is sound and the code holds it. But the operation that *does* carry
the payload records nothing about who read it. **The artifact that cannot leak the payload is
audited; the one that serves it is not.**

**A thread can be proven deleted but not created.** `THREAD_DELETED` is in the vocabulary and
`delete_thread` writes it. There is no `THREAD_CREATED` member and `create_thread` writes nothing.
The trail can show a thread ended and what was said in it, and cannot show it ever began.

**Nothing caught any of it, and one thing looked like it had.**
`tests/component/test_operations_audited.py` asserts that every operation refuses an
unauthenticated caller and that the refusal vocabulary distinguishes what the caller cannot. It
never asserts that any operation writes an entry. It is a good file doing a different job under a
name that reads like this one — which is why **thirteen** operations were added since 008 under a
guard that was watching something else. (That file's own docstring says *eleven*, and *"if a
twelfth lands"*. Its **list** is test-enforced — `listed == shipped - original` — while its **prose
count** is not, so the count drifted two behind while the list stayed correct. An earlier draft of
this spec repeated the stale number as fact.)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An auditor asks who read a run's output (Priority: P1)

An incident review needs to establish who saw the output of a run that touched production. The
run itself is fully recorded: authority issued, every hook decision, every tool outcome, the
model's choices, terminal state. The reviewer then asks the question that follows — *who read
it?* — and the platform has nothing. Not "no one": nothing. The trail does not distinguish a
payload no one opened from one read by every person in the tenant.

**Why this priority**: It is the sharpest case and the one with a real adversary. `get_run_result`
serves the run's result payload, and 021 restricted the report specifically so that payload could
not escape a subject-only boundary. An unaudited read of the protected thing makes the protection
unfalsifiable — it can be honored perfectly and no one can demonstrate that it was.

**Independent Test**: Start a run, read its result, then query the trail for that run's
correlation id and find a record naming the reader and the time. Delivers the answer to "who saw
this" for the payload that most needs it, with no other operation changed.

**Acceptance Scenarios**:

1. **Given** a completed run with a result payload, **When** the subject who started it reads the
   result, **Then** the trail carries an entry naming the reader, the run, and when — joined to
   the run's own correlation id so the read appears in the same walk as the run that produced it.
2. **Given** a caller who is not the run's subject, **When** they attempt to read the result,
   **Then** the refusal is recorded as a refusal, distinguishable in the trail from a read that
   was permitted — and the refused caller learns nothing from the response that they could not
   have learned before.
3. **Given** the same run read twice by the same person, **When** the trail is queried, **Then**
   both reads appear. A record of "has ever been read" is not a record of who read it.

---

### User Story 2 - The surfaces describe governance they actually perform (Priority: P1)

A developer connects an editor, reads the surface's instructions, and forms a belief about what
the platform records. Today that belief is wrong for eight of seventeen operations, and nothing
they could do from the client would reveal it.

**Why this priority**: Equal-first with US1 and separable from it. Whatever the coverage decision
turns out to be, the claim must match it. A narrowed claim is honest; the current claim is not.
This story is what makes the feature safe to ship even if the coverage answer is "less than
everything" — and it is the one that must not be quietly dropped if the rest proves expensive,
because an overclaim about governance is worse than an acknowledged gap.

**Independent Test**: Compare every governance claim made by both surfaces against measured
behavior of the running service, and find no claim the service does not keep.

**Acceptance Scenarios**:

1. **Given** the surface's self-description, **When** it is checked against which operations write
   trail entries, **Then** the description is true of every operation it covers.
2. **Given** a new operation added later, **When** it ships without the coverage its surface
   claims, **Then** a check fails naming the operation — the guard is on the relationship between
   claim and behavior, not a list someone must remember to edit.

---

### User Story 3 - The catalogue states each operation's disposition (Priority: P2)

Someone deciding whether a new operation needs a trail entry has no stated rule to apply, and no
way to see what the existing seventeen do without reading each handler.

**Why this priority**: Prevents recurrence, and is why this gap reached seventeen operations. It
depends on the coverage decision — there is nothing to record until the rule exists — so it
follows rather than leads.

**Independent Test**: Read one place and learn, for every operation, whether it records and why.

**Acceptance Scenarios**:

1. **Given** the operation catalogue, **When** an operation is added, **Then** its audit
   disposition is a declared property of it rather than an inference from its handler.
2. **Given** an operation declared to record, **When** it does not, **Then** a check fails.

---

### Edge Cases

- **A read that fails.** *Resolved — FR-007.* A refusal records, and the trail keeps the
  distinction the caller cannot see. A boundary probeable without trace is the case
  `EVIDENCE_READ_REFUSED` already prevents on the evidence plane.
- **A read whose audit write fails.** *Resolved — FR-007a.* The read fails. An audit write on a
  covered read is enforcement, not observation, which means a trail outage takes run and thread
  reads down with it. Both existing precedents already do this; what is new is that it now applies
  to ordinary listings, and that is the cost this feature accepts openly.
- **`list_runs` returning nothing.** *Resolved — FR-007b.* It records. An empty page discloses
  that the caller asked.
- **Volume.** *Resolved — it decided the coverage rule.* A listing called on every editor connect
  could write more entries than the runs it lists, and the trail is append-only and never sampled
  (Principle IX), so the cost is permanent. This is why the two catalogue reads are excluded; see
  Assumptions.
- **The reconciler's own reads.** *Resolved, and the safeguard already exists one layer up.*
  Measured: `emit_reconciled` appends to `audit-reconcile-{basis}` under tenant `__platform__` — a
  **third** stream, never the one it just read. So reconciling `record-access` does not grow
  `record-access`, and the recursion terminates for the same structural reason FR-005a relies on.
  **Two consequences that must be stated rather than left to inference**: the reconciler's read of
  the record-access stream writes **no** read record — it touches neither a run nor a thread under
  FR-001, and it is platform machinery rather than a caller-facing operation. And the record-access
  stream is subject to the same reconciliation as any other, which is what keeps a record of who
  looked from being the one stream nobody checks.

## Requirements *(mandatory)*

### Functional Requirements

**The decision this feature exists to make**

- **FR-001**: **An operation that touches a run or a thread MUST record a trail entry** — reads and
  creations alike. An operation that touches neither MUST NOT be required to. This is the rule, and
  it MUST be stated where someone adding an operation will apply it, decidable for an operation
  that does not yet exist by someone who did not write it.
- **FR-001a**: The rule's boundary MUST be justified where it is stated, not merely drawn. Runs and
  threads are records of *activity* — what a person asked for, what a model chose, what a tool did.
  Agent definitions are *configuration*: reading one discloses how the platform is set up, not what
  anyone did with it. A future operation is classified by which of those two it touches.
- **FR-002**: The rule MUST classify every one of the seventeen operations shipped as of this
  feature, and every classification MUST be checkable against measured behavior rather than
  asserted in prose. Under FR-001 that means **seven** operations gain records — `list_runs`,
  `get_run`, `get_run_result`, `list_threads`, `get_thread`, `create_thread`, `stop_run` — and two
  remain without: `list_agent_definitions` and `get_agent_definition`.
- **FR-002a**: `create_thread` MUST record. The trail can currently prove a thread was deleted and
  what was said in it, and cannot prove it began; a lifecycle recorded only at its end is a
  narrative with no first page.
- **FR-002b**: `stop_run` MUST record, and the entry MUST name **who** stopped the run. It touches a
  run, so FR-001 already requires it; it is stated separately because an earlier draft exempted it
  on a false premise and because it is the only **write** among the operations this feature covers.
  The record MUST go to the run's own stream — this is an act performed on the run, not a read of
  it, so FR-005a does not apply and the symmetry with `THREAD_DELETED` holds.
- **FR-003**: Reading a run's result payload MUST record who read it, which run, and when. This is
  the one operation the feature MUST cover under any rule chosen; a rule that leaves it uncovered
  MUST be rejected rather than accommodated.

**What a record of a read must contain, and must not**

- **FR-004**: A read record MUST identify the caller, the tenant, what was read, and when — with
  the same attribution every other entry carries, so it is queryable by the same governed path.
- **FR-005**: A read record MUST carry the correlation id of the thing read where one exists, so
  that holding a run id is enough to find who read it through the same governed query (ADR-0009,
  walkable both directions).
- **FR-005a**: A read record MUST NOT be appended to the chain of the thing read. Reading a run
  MUST NOT alter that run's chain — the existing evidence path already refuses this, on the
  grounds that reading evidence would otherwise write into the evidence being read, and the same
  reasoning binds here for a stronger reason: 021's `RunReport` compiles from a run's chain, so a
  read appended there would put "who read this run" inside the report of that run, including reads
  of the report itself, growing every time anyone looked.
- **FR-005b**: Read records MUST therefore live in a stream distinct from the chains they refer
  to, and that stream MUST be tenant-scoped and readable through the same governed path as any
  other evidence — a record nobody can query is not a record.
- **FR-006**: A read record MUST NOT contain the content read. Recording that a payload was read
  MUST NOT copy the payload into the trail — the trail does not egress by default and a payload
  inside it inherits neither that boundary's intent nor `get_run_result`'s subject restriction.
- **FR-007**: A refused read MUST be distinguishable in the trail from a permitted one, and the
  trail MUST preserve the distinction the caller cannot see (`no_such_record` vs `outside_tenant`,
  per the existing vocabulary). A refused read MUST record — a boundary a caller can probe without
  trace is the case `EVIDENCE_READ_REFUSED` already exists to prevent on the evidence plane.
- **FR-007a**: A covered read whose own record cannot be written MUST fail, and MUST NOT return the
  records it was asked for. This holds for all six covered **reads**, with no exception for
  listings — and a `stop_run` whose entry cannot be written MUST NOT stop the run, on the same
  grounds and matching `start_governed_run`, which already refuses when its own audit write fails.
  Seven operations, one posture. **Accepted cost, stated rather than discovered**: a trail outage makes runs and threads
  unreadable through both surfaces. An unrecorded answer is the state this feature exists to end,
  so serving one during an outage would reintroduce it at exactly the moment someone will later
  investigate.
- **FR-007c**: A refusal MUST be recorded with a reason code that is **true of why it was refused**.
  Measured, and this one already fails: `run_result_for` refuses an oversized result with
  `not_permitted`, whose stated meaning is *"the record is visible to this caller, and this action
  is not theirs"*. The caller receives 403 for a result that merely did not fit, and once this
  feature records refusals, the trail will assert a permission denial that never happened. The
  vocabulary already proves the distinction matters — `message_too_large` exists for exactly this
  shape, and `nothing_to_dispatch` carries the comment *"conflating them tells someone their access
  is fine when it is not, and tells another that it is not when it is."* A wrong status code is a
  bad answer; a wrong audit entry is false evidence.
- **FR-007b**: A covered read that returns nothing MUST still record. An empty listing discloses
  that the caller asked, and a trail that omits fruitless reads cannot show probing.

**Where it binds**

- **FR-008**: All seven covered operations MUST record identically on the API and MCP surfaces, and
  the two catalogue operations MUST record on neither (ADR-0033). Parity holds today at zero
  coverage; it MUST hold at this one.
- **FR-009**: An operation added after this feature MUST NOT be able to ship without an audit
  disposition. The check MUST fail on the operation's absence from the rule, not on a hand-kept
  list going stale.

**The claim**

- **FR-010**: Every governance claim either surface makes to a client MUST be true of the running
  service. Where the chosen coverage is narrower than "every operation", the claim MUST be
  narrowed to match, in the same change.
- **FR-011**: A check MUST fail when a surface's self-description asserts coverage the service
  does not provide. It MUST compare description to behavior; a check that compares the description
  to a second copy of itself would have passed every day this gap existed.

**Sealed core and the decision record**

- **FR-012**: ADR-0035 MUST be amended. Its current text scopes "evidence access is itself audited"
  to the audit plane, and this feature extends that discipline to records about runs and threads;
  shipping the extension in code while the ADR still describes the narrower scope would put the
  decision record behind the system (Principle X). The amendment MUST also carry forward what the
  ADR got right and this feature keeps — that the meta-audit is written to a stream separate from
  the one being read — since that is now load-bearing for a second reason (FR-005a).
- **FR-013**: Any new audit event type is sealed core (Principle V) and MUST be additive, MUST
  carry a security review request, and MUST NOT move the hash of any entry already written — the
  digest pinned in `test_audit_chain.py` is the check and MUST remain unmoved.
- **FR-014**: The feature MUST NOT weaken any existing enforcement. No refusal may become an
  allow, and no existing audit write may be removed or made conditional in the course of adding
  others.

**What this feature does not do**

- **FR-015**: This feature MUST NOT change what any operation returns, who may call it, or how it
  is authorized. It records reads; it does not re-scope them. A change to `get_run_result`'s
  subject restriction is a different decision and MUST NOT ride along with this one.

### Key Entities

- **Read record**: Evidence that someone was shown something. Caller, tenant, what, when, and the
  correlation id of the thing read. Never the content.
- **Audit disposition**: A declared property of an operation — whether it records, and under which
  rule. Belongs with the operation, not in a list kept beside it.
- **Governance claim**: A statement either surface makes to a client about what the platform
  records. Currently prose in a self-description; this feature makes it checkable.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For every one of the seventeen operations, a person can determine from one place
  whether it records a trail entry, and the answer matches the running service in every case.
- **SC-002**: Reading a run's result payload produces a trail entry naming the reader, discoverable
  through the governed read path by the run's correlation id — demonstrated against a served
  surface, not a test double.
- **SC-003**: No governance claim made by either surface is false of the running service. Verified
  by comparison against measured behavior, so the check would have failed before this feature.
- **SC-004**: Every operation in the catalogue carries a disposition, and an operation lacking one
  cannot be constructed. Verified two ways, because a required field alone is not a *named* check:
  the catalogue is asserted complete against the shipped operation set, and the failure a caller
  sees when a disposition is missing names the operation rather than a constructor argument.
- **SC-004a**: The seven covered operations answer exactly as they did before this feature to the
  same caller with the same authority — same records returned, same refusals, same status. FR-015
  is a negative requirement, and a negative requirement with no check is a hope.
- **SC-005**: The pinned entry digest is unchanged, and every entry written before this feature
  still verifies against the chain that holds it.
- **SC-006**: No read record contains content that was read. Verified by planting a
  credential-shaped value in a payload and asserting it reaches no entry.
- **SC-007**: A read refused for being outside the caller's tenant is distinguishable in the trail
  from one refused for not existing, while remaining indistinguishable to the caller.
- **SC-008**: No operation loses an audit entry it wrote before this feature.
- **SC-009**: With the trail unwritable, every one of the six covered reads refuses and returns no
  records, and `stop_run` refuses and leaves the run running — verified by making the write fail,
  not by reasoning about it.
- **SC-010**: Reading a run leaves that run's own chain byte-identical, and a report compiled for
  that run afterward carries no claim about who read it.
- **SC-011**: The two catalogue operations remain unrecorded, and a check says so deliberately —
  so that a later change making them record is a visible decision rather than a drift nobody
  notices.

## Assumptions

- **The coverage rule is decided** (clarified 2026-08-01): operations touching a run or thread
  record; catalogue reads do not. The rejected alternative worth recording is "every operation" —
  it matches today's claim verbatim and needs no narrowing, but it writes an entry every time a
  connected client fetches the agent-definition list, which for an editor is every connect. The
  trail is append-only and never sampled (Principle IX), so that cost is permanent and cannot be
  tuned away later. Configuration reads were judged not worth it; activity reads were.
- **`start_run` is covered** by `start_governed_run`'s `authority_issued` and `run_start` entries.
  Measured against the code, and confirmed present in a live trail.
- **`stop_run` is NOT covered, and an earlier version of this line said it was** — pairing it with
  `start_run` and calling the pair "measured" when only `start_run` had been checked. There is no
  audit write in the stop path at all. The correction is left visible because an assumption
  labelled *measured* that was not measured is more dangerous than an open question, and this spec
  is the wrong place to hide one. `stop_run` is now covered by FR-002b.
- **Parity holds today.** Neither surface audits these operations, so this is a coverage gap on
  both rather than a divergence between them. Confirmed by reading the shared implementation both
  transports call.
- **The existing refusal *reason codes* suffice** for refused reads. `INDISTINGUISHABLE_TO_CALLER`
  already carries the distinction FR-007 needs, and this feature consumes it rather than extending
  it. **This is not a claim that no vocabulary grows**: the feature does add a
  `RECORD_READ_REFUSED` *event type*, because the refusal of a read is a different kind of event
  from the refusal of a tool call. Reason codes are reused; event types are extended. The two were
  conflated in an earlier draft of this line.
- **No new persona or entitlement.** Read records are readable through the governed evidence path
  under the entitlements that already exist. Who may review them is ADR-0035's scope algebra, not
  a new question.
- **The finding is real and was measured**, on 2026-08-01, against a served MCP surface reached by
  an editor and by direct calls, with the trail queried directly afterward. It is not inferred
  from source reading, which is what let it survive seventeen operations and a test named as
  though it covered exactly this.
