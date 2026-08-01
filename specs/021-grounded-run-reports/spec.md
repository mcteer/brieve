# Feature Specification: A report compiles from records, or it says it could not

**Feature Branch**: `spec/021-grounded-run-reports`

**Created**: 2026-08-01

**Status**: Draft

**Input**: The last owed Quality Gate row. ADR-0018 has been Accepted since 2026-04-08 and
implemented by nothing: `RunReport` does not exist in `src/`, so the fifth eval suite ships as
an explicit skip citing the ADR that defers it.

## Traceability *(mandatory)*

| Field | Value |
| --- | --- |
| **Requirements (R1–R17)** | **R4** (evidence over claims — a report is the artifact people actually read, and the one most able to lie). **R10** (observability and attestation). Both are the pair ADR-0018 itself names. |
| **ADRs touched** | **ADR-0018** (implemented — Accepted and unbuilt for four months). **ADR-0035** (a report is a governed, tenant-scoped evidence read, and is itself audited). **ADR-0032** (attestation states its scope: a delegated run and a local loop evidence different things). **ADR-0055** (the trail has two copies; a report may compile from records whose integrity was never checked). **ADR-0033** (a requestable report is an operation, so the surface-parity row grows across API and MCP — FR-015b). **ADR-0034** (the portal is a thin client, which is *why* a human-facing report is an API operation rather than portal logic). **ADR-0047** (the owed row binds the moment this feature exists). **None amended.** |
| **Evidence class** | **Attestation-relevant, and more directly than any prior feature.** Everything before this produced records. This produces the artifact a human reads *instead of* the records — cited in change records and audit responses. A defect here is not a wrong answer, it is a plausible one. |

## What already holds, and what does not

**Holds, and it is the whole precondition.** A run now records everything a report would be
about, and all of it is hash-chained: authority issued and refused, every hook decision, tool
outcomes, model gates, matrix fallbacks, revivals, re-observed steps, and — since 020 — which
tool a model chose, which choices were refused, and whether a run ended because it named nothing
or ground through its re-choice bound. 015 added a second copy of the trail and a reconciler that
compares contents rather than claims. 014 built observers that answer *did this actually land* by
asking the product rather than trusting a record.

**Does not hold.** **There is no report.** `RunReport` appears nowhere in `src/`.
`src/core/evals/suites.py` names four suites and carries a fifth in an `OWED` dictionary whose
value says, in as many words, that a gate over it "would assert something about a thing that is
not there".

`get_run_result` exists and is deliberately *not* this: it answers what a run produced, in three
dispositions, "without the caller reading a single audit entry". A report is the other artifact —
not the output, but an account of what happened to produce it.

**Why this is the right moment.** 020 made a run worth reporting on. Before it, a report would
have described a scripted sequence: every tool the same, chosen by nobody, refused never. The
first run whose account is genuinely uncertain — a model chose, something was denied, it chose
again — is the first run a report can get *wrong* in the way ADR-0018 is about.

## Clarifications

### Session 2026-08-01

- Q: Is a report a stored snapshot or compiled on demand? → A: **Compiled on demand, never
  stored.** Every request recompiles from the records. The rejected alternative, compiling once at
  run end and storing it, would make a report a second store that can drift from the evidence it
  claims to summarise, and would quietly make "reports are presentation" false: something
  persisted is something another component can eventually read as a source.

  **Amended by the fourth clarification below.** This answer originally added that a read-back
  differing between two reports would mean *the world changed*, and that this was the finding
  rather than an inconsistency. Read-back has since moved to run end, so nothing is re-derived at
  request time and two reports now agree on **every** claim. Corrected here rather than left to
  contradict, because a superseded sentence in a clarification log is read as current.
- Q: Does read-back apply to every effect claim, or only non-repeatable ones? → A: **Wherever an
  observer exists; flagged as `unverified: no observer` where none does.** The two rejected
  answers both decide silently. Restricting to non-repeatable effects leaves every other claim
  asserted from the record with nothing saying so; requiring it everywhere promises a read-back
  for tools that have no way to perform one, which would be satisfied by writing a stub observer
  that returns success. **The absence of a read-back is a fact about the claim, so it belongs in
  the claim** — and this is the one option under which no claim is ever silently asserted.
- Q: Who may request a report? → A: **Whoever may read the evidence — tenant-scoped, not
  restricted to the run's subject.** Many personas in an organization need these: auditors,
  compliance, platform operators, the reviewer of a change record that cites one. Measured rather
  than assumed — `EvidenceQueryRequest` is bounded by `tenant_id` and carries **no subject field
  at all**, so any authenticated caller can already read any run's entries in their tenant. **A
  report therefore grants no new access; it makes legible what is already readable**, which is
  the honest framing. A subject-only rule would have been theatre the raw evidence path walks
  straight past.

  **This uncovered a leak.** `get_run_result` *is* subject-restricted (`runs.py:183` refuses
  `not_permitted` when the caller is not the run's subject) because a run's **output** is a work
  product rather than a governance record. A report carrying that payload would route around the
  restriction and become precisely what FR-009 forbids. See FR-008a.
- Q: Read-back at report time has no authority to run under. Where does it go? → A: **The
  allocation observes at run end, and the observation is recorded as evidence.** Raised by the
  plan's Constitution Check, which failed on Principle IV: `Observer.observe` takes no credential
  and `VaultWriteObserver` reads under *ambient* identity, which in a resume is the allocation's —
  attested and bounded by the run's ceiling. **At report time there is no allocation**, so a
  read-back would run under the API surface's own workload identity and hand a reader an
  observation they may hold no authority to make. An agent never exceeds its human; a report must
  not exceed its reader.

  So read-back moves to where the authority already exists. Before a run reaches a terminal state,
  the allocation asks each effect's observer and records the answer. The report then compiles that
  record like any other, and **the compiler stays pure** — it still reads nothing itself.

  **What this costs, stated rather than buried**: a report no longer detects drift *after* the run
  ended. The observation is a fact about run-end, which is when ADR-0018 says the claim is made
  ("before asserting that something completed"), but it means a product changed a week later reads
  the same as one that never changed. That is a real loss against the on-demand rationale above,
  accepted deliberately.

  **And it is still a sealed-core change** — an earlier recommendation said otherwise and was
  wrong. It does not touch the `Observer` protocol, which is what option B would have done, but
  the observation has to live somewhere, and the honest home is the hash-chained trail: one
  additive `AuditEventType` member, exactly the shape 020 added and had reviewed. Principle V
  applies.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Every claim traces to a record (Priority: P1)

Someone asks what a run did. They get a structured account — what was attempted, what ran, what
was denied, what changed — in which **every statement is populated from the run's records**, not
composed by a model and not assembled from a process's memory of itself.

**Why this priority**: it is the decision. ADR-0018's one-line summary is *reports are
presentation; attestation rests on records*, and everything else here is a property of that.

**Independent Test**: produce a report for a completed run, and for each claim in it, find the
record it came from.

**Acceptance Scenarios**:

1. **Given** a completed run, **When** a report is compiled, **Then** every claim in it
   corresponds to a record in that run's trail, and nothing appears that no record supports.
2. **Given** a run whose trail contains a denial, **When** a report is compiled, **Then** the
   denial appears — a report that omits what was refused describes a different run.
3. **Given** a run in another tenant, **When** a report is requested, **Then** it is answered
   exactly as a run that does not exist.
3a. **Given** a caller in the run's tenant who did **not** start it — an auditor, a reviewer —
   **When** they request the report, **Then** they receive it, and it contains no part of the run's
   result payload.
4. **Given** one run, **When** the fidelity gate scores its report and a person requests the same
   report, **Then** both receive the same set of claims — the gate is scoring what the person
   reads, not a variant of it.

---

### User Story 2 - A claim that cannot be reconciled is flagged, never softened (Priority: P1)

The records are incomplete or disagree. The report says so, in the place the claim would have
been, rather than rounding to the nearest confident sentence.

**Why this priority**: this is the half that makes the first half worth anything. A report that
silently omits what it could not verify is more dangerous than one that never claimed to verify
anything, because it terminates the investigation that would have found the problem.

**Independent Test**: compile a report for a run with a deliberately unresolvable record — an
intent with no result and no observer answer — and find the gap stated rather than absent.

**Acceptance Scenarios**:

1. **Given** a step whose bracket opened and never closed, **When** a report is compiled, **Then**
   it states that the step's outcome is unknown rather than reporting it as either completed or
   failed.
2. **Given** a claim that cannot be reconciled against the record, **When** the report is emitted,
   **Then** the claim is **flagged**, and the report is still emitted — an unreconcilable claim
   does not suppress the whole report.
3. **Given** a run whose evidence fails integrity verification, **When** a report is compiled,
   **Then** the report states that its own basis is unverified.

---

### User Story 3 - Read-back before a terminal claim, performed by the run (Priority: P2)

Before a run reaches a terminal state, it re-reads the authoritative state for each effect it
produced and records what it found. The report compiles those observations; it performs none
itself.

**Why this priority**: it is the specific failure ADR-0018 opens with — "applied successfully to
three workspaces" when a fourth silently failed. P2 rather than P1 because it applies only to
claims about effects, and a report that compiled faithfully and re-read nothing is already better
than what exists, which is nothing.

**Independent Test**: arrange a tool outcome recorded as allowed whose effect did not land, and
observe the report decline to claim completion.

**Acceptance Scenarios**:

1. **Given** a step recorded as allowed **and a tool with an observer**, **When** the run reaches
   a terminal state, **Then** the observer is asked under the **allocation's own attested
   identity** and the answer is recorded as evidence.
2. **Given** such an observation exists, **When** a report is compiled, **Then** the claim
   reflects what was observed rather than what the tool outcome asserted.
3. **Given** the product could not be reached at run end, **When** a report is compiled, **Then**
   the claim is flagged as unverified rather than asserted or dropped.
4. **Given** a step recorded as allowed **and a tool with no observer**, **When** a report is
   compiled, **Then** the claim carries `unverified: no observer` — visibly a record-only claim,
   never presented as product-confirmed.
5. **Given** a run that was killed and never reached a terminal state, **When** a report is
   compiled, **Then** its effect claims carry `unverified: not observed` rather than being
   asserted from the tool outcome alone.

---

### Edge Cases

- **The run is still going.** A report about an unfinished run must not read as an account of a
  finished one.
- **The run never started** — authority refused before anything ran. There is a trail, and a
  report of it is a legitimate thing to want.
- **The trail is short by design.** A resumed run's earlier steps were executed by an allocation
  that died; they carry `STEP_REOBSERVED` rather than an outcome. A report must render that as
  *observed, not re-run* rather than as a gap.
- **A model chose nothing, or exhausted its re-choice bound.** Both are terminal states 020
  introduced, and a reader will want them distinguished from a crash.
- **The report would contain a secret.** Tool arguments are hashed and secret values never enter
  the trail; a report that re-derived anything from a live product must hold the same line.
- **Two reports of the same run.** They agree, always — every claim including the observations
  compiles from append-only records, and nothing is re-read at report time. This is a stronger
  guarantee than the first clarification anticipated, and it is the deliberate cost of moving
  read-back to run end: **drift after the run ended is no longer detectable.**

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A report MUST be populated from the run's recorded evidence. No claim may originate
  anywhere else — not from a model, not from a process's memory of what it just did.
- **FR-002**: A report MUST state the run's disposition, and a report of a run still in flight
  MUST be distinguishable from a report of a finished one.
- **FR-003**: A report MUST include what was **refused**, not only what succeeded.
- **FR-004**: Every claim MUST be validated against the record before the report is emitted.
- **FR-005**: A claim that cannot be reconciled MUST be **flagged in place** — not omitted, not
  softened, and not fatal to the rest of the report.
- **FR-006**: Before a run reaches a terminal state, it MUST re-read the authoritative state for
  each effect it produced and **record the observation as evidence**. The report compiles those
  records and performs no read-back of its own.
- **FR-006a**: When the authoritative state cannot be reached, the recorded observation MUST say
  so, and the claim MUST be flagged as unverified. **An unreachable product is not evidence of
  success**, and it is not evidence of failure either.
- **FR-006b**: The observation MUST be made under the **allocation's own attested identity**,
  bounded by the run's ceiling. It MUST NOT be made by any process acting on a reader's behalf:
  a report that re-read a product would run under the surface's authority rather than the
  requester's, which is amplification and the reason this moved (Principle IV).
- **FR-006c**: A run that never reaches a terminal state records no observation, and its effect
  claims MUST carry `unverified: not observed` — distinct from both "unreachable" and "no
  observer", because a killed run and an unreachable product are different facts.
- **FR-007**: Compiling a report MUST go through the governed, tenant-scoped evidence read path,
  and the read MUST itself be audited (ADR-0035). A second, unaudited route to the same records
  would be an ungoverned read path wearing a report's clothes.
- **FR-008**: A run outside the caller's tenant MUST be answered exactly as a run that does not
  exist — the same indistinguishability the evidence read path already holds.
- **FR-008a**: A report MUST be scoped **as an evidence read is** — by tenant, not by the run's
  subject — and MUST NOT carry the run's **result payload**, which `get_run_result` restricts to
  the subject who started it. A run's governance record and its work product are scoped
  differently on purpose, and a report is the first artifact able to smuggle the second out under
  the first's rules.
- **FR-008b**: A report MUST grant **no access the caller does not already have** through the
  governed evidence path. It is a compilation of readable records, not a new privilege; if a
  report can show something `read_evidence` cannot, that is a widening and a defect.
- **FR-009**: A report MUST NOT contain secret values, and MUST NOT become a route to material
  the caller could not otherwise read.
- **FR-010**: A report MUST record whether the evidence it compiled from **verified** — the chain,
  and where a second copy exists, the reconciliation. A report compiled from records nobody
  checked is a weaker claim than one compiled from records that were, and the difference must be
  visible rather than assumed.
- **FR-011**: A report MUST attribute a chosen tool to the model that chose it, and MUST render
  020's terminal outcomes — nothing named, re-choice bound exhausted, provider unreachable — as
  the distinct endings they are.
- **FR-012**: A report MUST state its own **scope** — what it can and cannot evidence — per
  ADR-0032, rather than leaving a reader to infer that everything is covered.
- **FR-013**: The **report-fidelity eval suite** MUST be built and MUST become blocking, moving
  `report_fidelity` out of `suites.py`'s `OWED` dictionary and into the suites in force.
- **FR-013a**: The fidelity corpus MUST score claim **precision and recall** against labeled
  material events. ADR-0018 warns that this corpus "is also the thing most likely to be skipped
  under schedule pressure, which would leave the decision nominally in force and practically
  unenforced" — so a suite that cannot run MUST raise, per the discipline `suites.py` already
  enforces for the other four.
- **FR-014**: Reports MUST NOT become the source of any claim elsewhere in the platform. Nothing
  may read a report to decide anything; attestation continues to rest on records.
- **FR-014a**: A report MUST be **compiled on demand and never persisted**. No report store, no
  report identity, no retention policy — because a stored report is a second copy of the evidence
  that can drift from it, and anything persisted is eventually read as a source, which is
  precisely what FR-014 forbids.
- **FR-014b**: Two reports of the same run MUST agree on **every** claim. Observations are
  records like any other, so nothing a report says is re-derived at request time. Detecting drift
  after a run ended is explicitly **not** a property of this feature — see the third clarification
  for what that costs and why it was accepted.
- **FR-015**: A report serves **two consumers, with different purposes and the same data**: a
  person reads it as the account of what a run did, and the fidelity gate scores it. Both MUST
  consume the **same compiled object**.
- **FR-015a**: There MUST NOT be a second copy, a projection, or a gate-only variant of a
  report's content. **A gate that scores a different object from the one a person reads is not
  gating what anyone sees** — it is a correct, tested artifact standing beside the one that
  matters, which is the failure shape this platform has now found six times and named as its own
  class of ROADMAP gap.
- **FR-015b**: Because a person reads it, a report MUST be requestable. The portal is a thin
  client that consumes the API (ADR-0034), so a human-facing report is an API operation; and
  ADR-0033 binds parity across every implemented pair of transports, so MCP carries it too. **The
  surface-parity row grows by this operation** — a consequence of FR-015 rather than a separate
  choice, and the plan must treat it as owed work rather than discover it.
- **FR-015c**: The two purposes MAY differ in what they *emphasise* — a person wants what needs
  attention first, the gate wants every claim with its provenance — but neither may see a claim
  the other cannot. Prioritisation and ordering are presentation; the set of claims is not.
- **FR-016**: A run MUST observe every effect **for which an observer exists**, at run end.
- **FR-016a**: Where no observer exists, the claim MUST carry `unverified: no observer` rather
  than being asserted as complete. **The absence of a read-back is a fact about the claim**, and
  a report that omitted it would present a record-only claim and a product-confirmed one as the
  same kind of statement.
- **FR-016c**: Recording an observation MUST NOT change the run's outcome. A run that completed
  its work and then found an effect missing is a run that completed and produced a finding; making
  the observation retroactively fail the run would give a *reporting* mechanism the power to
  change what is being reported, which is FR-014 in the other direction.
- **FR-016b**: This feature MUST NOT add observers to satisfy FR-016. An observer written to
  make a claim verifiable, rather than because the product can genuinely be asked, is a stub that
  returns success — which converts an honest `unverified` into a false `confirmed` and is worse
  than the gap it closes. Observers for currently-unobservable tools are separate work with their
  own justification.

### Key Entities

- **RunReport**: a typed, structured account of one run, **compiled on demand from that run's
  records and never stored**. Every field traces to evidence; fields that could not be reconciled
  carry that status rather than a value. It has no identity of its own and no lifecycle — a
  report is not a thing that exists between requests. New.
- **Claim**: one statement in a report, together with what it was validated against and whether
  that validation succeeded. New.
- **Material event**: something in a run that a faithful report must mention — a denial, an
  executed effect, a terminal state. What the fidelity corpus labels and scores against. New.
- **Run record**: unchanged. The audit trail, the checkpoints, the brackets, and the observers'
  answers, which this feature reads and does not alter.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of claims in a report trace to a record; **0** claims originate from a model.
- **SC-002**: A run containing a denial produces a report mentioning it in 100% of cases.
- **SC-003**: An unreconcilable claim is flagged in 100% of cases, and **0** are omitted or
  softened.
- **SC-004**: Every effect whose tool has an observer is observed before the run reaches a terminal
  state, in 100% of cases; an unreachable product yields a recorded `cannot determine` rather than
  an assertion.
- **SC-004a**: **0** effect claims are asserted as complete without either a recorded observation
  or an explicit `unverified` reason — observed, unreachable, no observer, and not observed must
  together account for every one of them.
- **SC-004b**: **0** observations are performed by a report. Every one is made by the allocation
  that produced the effect, under its own attested identity — demonstrated from the trail, not
  asserted.
- **SC-005**: A report request for another tenant's run is indistinguishable from one for a
  nonexistent run — **0** discriminating signals, including message text and reason code.
- **SC-005a**: A caller who is not the run's subject can obtain its report, and **0** run result
  payloads reach them through it — the access a report grants matches the evidence path's exactly,
  neither narrower nor wider.
- **SC-006**: `report_fidelity` is a blocking suite; **0** owed Quality Gate rows remain.
- **SC-007**: The fidelity suite measures claim precision and recall, and fails rather than skips
  when it cannot run.
- **SC-008**: **0** code paths read a report to decide anything.
- **SC-009**: **0** claims are visible to one consumer and not the other — the object the gate
  scores and the object a person receives are the same compiled report, demonstrated rather than
  asserted.
- **SC-010**: Surface parity holds over the grown catalogue: the report operation yields the same
  verdict and equivalent audit events on every implemented transport.
- **SC-011**: No pre-existing conformance directory loses rows.

## Out of scope

- **Rendering.** How a report is *displayed* — portal layout, terminal formatting, PDF — is
  presentation over a typed object. This feature produces the object, makes it requestable, and
  asserts its fidelity. **Not the same as FR-015c**: which claims exist is in scope and identical
  for both consumers; how they are arranged on a screen is not.
- **Natural-language summarisation of a report.** ADR-0018 permits a report to "render,
  summarize, and prioritize", and a model may one day write prose *over* a compiled report. That
  is a separate feature with its own eval, and doing it here would blur the line the ADR draws.
- **The production report-fidelity metric.** ADR-0018 also asks for fidelity as a leading drift
  indicator in production alongside hook denial rate. That needs a deployed fleet producing
  reports; the eval gate comes first and is what the constitution's owed row names.
- **Reporting across runs.** One run, one report. Fleet-level rollups are a different artifact
  with different tenancy questions.

## Assumptions

- The records are sufficient. Every prior feature's evidence — hook decisions, outcomes, choices,
  revivals, re-observations — is assumed adequate to compile from, and where it is not, that is a
  finding this feature is expected to surface rather than work around.
- Observers are the read-back mechanism. `Observer` implementations exist for non-repeatable
  tools and are already used by resume; this feature consumes them rather than inventing a second
  way to ask "did it land".
- The evidence read path is correct and stays unchanged. This feature is a consumer of ADR-0035's
  governed read, not a modification of it.
- `get_run_result` stays as it is. A report is a different artifact from a run's output, and
  merging them would make the checkpoint payload's shape a compatibility surface — which that
  function's own docstring argues against. **They are also scoped differently on purpose** (FR-008a):
  the result is the subject's work product, the report is the tenant's governance record.
- Many personas read reports. Auditors, compliance, platform operators and change reviewers are
  the intended audience alongside the person who started the run — which is why the artifact is
  scoped to the evidence path rather than to the run's owner.
