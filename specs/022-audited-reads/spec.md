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
| **ADRs touched** | **ADR-0035** (the load-bearing one: *"evidence access is itself audited — who reviewed which evidence, when. A meta-audit record, because the integrity of an audit trail includes knowing who read it"*. This feature decides whether that discipline stops at the audit plane or extends to records **about** runs. Likely **amended**, not merely consumed — see FR-012). **ADR-0009** (one correlation ID joins prompt → hooks → call → run → audit entry, walkable both directions; a read that writes nothing is a step in that walk with no entry). **ADR-0033** (four transports over one authorization core — whatever is decided binds on API and MCP identically; parity currently *holds*, at zero). **ADR-0018 / ADR-0032** (the shape of the get_run_result asymmetry: the report is governed and audited, the payload it deliberately excludes is neither). **ADR-0047** (whether a new gate row binds now). |
| **Evidence class** | **Attestation-relevant, and about attestation itself.** Every prior feature added records. This one asks whether the record of *reading* those records exists — the question an auditor asks second, after "what happened", and the one this platform currently cannot answer for eight of its seventeen operations. |

## What already holds, and what does not

**Holds.** The audit plane is genuinely a governed read path. `read_evidence` writes
`evidence_read`; a refused one writes `evidence_read_refused`; `reconcile_evidence` and
`get_run_report` both audit. ADR-0035's promise — that reading the evidence is itself evidence —
is kept for the evidence plane, and 021 kept it for reports. Reconciliation, mapping collection,
mapping requests, turns, and thread deletion all leave records.

**Does not hold, and was found by using the platform rather than by reading it.** Eight
operations return records about runs, threads, and agent definitions and write nothing at all.
Measured against the running service on 2026-08-01, not inferred from the source:

| Operation | Returns | Trail entry |
| --- | --- | --- |
| `list_runs` | run ids, correlation ids, agent definition ids, states, timestamps | **none** |
| `get_run` | one run's record | **none** |
| `get_run_result` | **the run's result payload** | **none** |
| `list_threads` | the subject's threads | **none** |
| `get_thread` | one thread and its turns | **none** |
| `create_thread` | a new thread | **none** |
| `list_agent_definitions` | the definitions available to the caller | **none** |
| `get_agent_definition` | one definition, including its bound model and tool scope | **none** |

`start_run` and `stop_run` are **not** in this table. They write nothing at the transport layer,
but the run itself writes `authority_issued` and `run_start`, so the act is recorded. They are
covered, and naming them as gaps would be wrong.

**Three things make this worse than a missing feature.**

**The surfaces claim otherwise.** Every client that connects to the MCP surface is told, in the
instructions it receives at initialize: *"Every operation executes as the calling user and is
recorded in a tamper-evident trail."* Eight operations do not. This is the third self-description
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
name that reads like this one — which is why eleven operations were added since 008 under a guard
that was watching something else.

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

- **A read that fails.** An operation that refuses, or one whose backing store is unavailable and
  answers 503 — does the attempt leave a record? A refusal that writes nothing means a caller can
  probe a boundary indefinitely without trace, which is precisely the pattern
  `EVIDENCE_READ_REFUSED` exists to catch on the evidence plane.
- **A read whose audit write fails.** The trail is the thing being written to; when the write
  fails, does the caller still receive the records? Principle III says enforcement that errors
  must deny. Whether an audit write is enforcement or observation is a real question, and the
  answer determines whether a trail outage takes the read path down with it.
- **`list_runs` returning nothing.** An empty page still discloses that the caller asked. Whether
  a read that returned no records is worth an entry decides whether the trail shows probing.
- **Volume.** A listing called on every editor keystroke could write more entries than the runs it
  lists. The trail is append-only and never sampled (Principle IX), so this cannot be solved by
  dropping entries — it constrains which operations are worth recording, and that constraint
  belongs in the decision rather than discovered in production.
- **The reconciler's own reads.** A meta-audit record is itself a record. Whether reading the
  trail to reconcile it writes an entry, and whether that terminates, needs stating.

## Requirements *(mandatory)*

### Functional Requirements

**The decision this feature exists to make**

- **FR-001**: The platform MUST have a stated, written rule for which operations record a trail
  entry. The rule MUST be decidable for an operation that does not yet exist, by someone who did
  not write it.
- **FR-002**: The rule MUST classify every one of the seventeen operations shipped as of this
  feature, and every classification MUST be checkable against measured behavior rather than
  asserted in prose.
- **FR-003**: Reading a run's result payload MUST record who read it, which run, and when. This is
  the one operation the feature MUST cover under any rule chosen; a rule that leaves it uncovered
  MUST be rejected rather than accommodated.

**What a record of a read must contain, and must not**

- **FR-004**: A read record MUST identify the caller, the tenant, what was read, and when — with
  the same attribution every other entry carries, so it is queryable by the same governed path.
- **FR-005**: A read record MUST join the correlation id of the thing read where one exists, so
  reading a run appears in that run's walk (ADR-0009) rather than in a parallel stream nobody
  reviews.
- **FR-006**: A read record MUST NOT contain the content read. Recording that a payload was read
  MUST NOT copy the payload into the trail — the trail does not egress by default and a payload
  inside it inherits neither that boundary's intent nor `get_run_result`'s subject restriction.
- **FR-007**: A refused read MUST be distinguishable in the trail from a permitted one, and the
  trail MUST preserve the distinction the caller cannot see (`no_such_record` vs `outside_tenant`,
  per the existing vocabulary).

**Where it binds**

- **FR-008**: Whatever is decided MUST bind identically on the API and MCP surfaces (ADR-0033).
  Parity holds today at zero coverage; it MUST hold at whatever coverage is chosen.
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

- **FR-012**: If the chosen rule extends the governed-read discipline beyond the audit plane,
  ADR-0035 MUST be amended to say so. Its current text scopes "evidence access is itself audited"
  to the audit plane; extending that discipline in code while the ADR still describes the narrower
  scope would put the decision record behind the system (Principle X).
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
- **SC-004**: An operation added without an audit disposition fails a check that names it. Verified
  by adding one and observing the failure.
- **SC-005**: The pinned entry digest is unchanged, and every entry written before this feature
  still verifies against the chain that holds it.
- **SC-006**: No read record contains content that was read. Verified by planting a
  credential-shaped value in a payload and asserting it reaches no entry.
- **SC-007**: A read refused for being outside the caller's tenant is distinguishable in the trail
  from one refused for not existing, while remaining indistinguishable to the caller.
- **SC-008**: No operation loses an audit entry it wrote before this feature.

## Assumptions

- **The coverage rule is not assumed.** Whether every operation records, or only those returning
  run-produced content, or only those crossing a subject boundary, is the central open question
  and belongs to `/speckit-clarify`. This spec asserts only that a rule must exist, must be
  decidable, must cover `get_run_result`, and must match what the surfaces claim. The volume edge
  case above is the reason the answer is not obviously "everything".
- **`start_run` and `stop_run` are covered** by the run's own `authority_issued` and `run_start`
  entries. Measured, not assumed — but if a run refuses before writing either, the coverage claim
  needs rechecking.
- **Parity holds today.** Neither surface audits these operations, so this is a coverage gap on
  both rather than a divergence between them. Confirmed by reading the shared implementation both
  transports call.
- **The existing refusal vocabulary suffices** for refused reads. `INDISTINGUISHABLE_TO_CALLER`
  already carries the distinction FR-007 needs; this feature is assumed to consume it rather than
  extend it.
- **No new persona or entitlement.** Read records are readable through the governed evidence path
  under the entitlements that already exist. Who may review them is ADR-0035's scope algebra, not
  a new question.
- **The finding is real and was measured**, on 2026-08-01, against a served MCP surface reached by
  an editor and by direct calls, with the trail queried directly afterward. It is not inferred
  from source reading, which is what let it survive seventeen operations and a test named as
  though it covered exactly this.
