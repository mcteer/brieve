# Feature Specification: The admin console — governance configuration leaves Terraform

**Feature Branch**: `spec/044-admin-governance-console`

**Created**: 2026-08-07

**Status**: Draft

**Input**: Measured against merged main (`d30f771`). An administrator should be able to
configure the platform — LLM-as-a-judge, the model bound to each role, product connections —
from an interface rather than by holding estate credentials and running a Terraform apply.

## Traceability *(mandatory)*

| Field | Value |
| --- | --- |
| **Requirements (R1–R17)** | **R2, R3 (authority per task)** — an administrator's authority is their own, not the platform's, and the console never holds more than the person operating it. **R7 (fail-closed)** — a configuration that cannot be read is not an empty configuration; a change that cannot be gated is not applied. **R4, R13 (evidence)** — every proposed change, every approval, and every refusal is a record, and the trail answers *who asked for what, and who decided*. **R5, R11 (total interception)** — the console adds no path to a governance record that is not the governed one |
| **ADRs touched** | **ADR-0016** (quorum on authority changes — the mechanism this feature makes reachable by a person rather than only by an operator), **ADR-0026** (the governance/assembly split this feature deliberately moves the line of, which is why it needs a record of its own), **ADR-0039** (the closed role vocabulary the ask does not match), **ADR-0022** (the Qualified Model Matrix an admin would bind against), **ADR-0025** (registry isolation — a dispatched run must not reach this write path), **ADR-0033** (surface parity, if the console is reachable from more than one transport), **ADR-0047** (a passing stub — acute here, because an "applied" that queued nothing looks identical to success), **ADR-0067** (a model does not judge its own output — the judge toggle's constraint), 043 (`relevance_cell`) and 042 (the published protected set) as the two records that motivated it |
| **Evidence class** | **attestation-relevant.** A configuration change is an authority change: it alters which model may answer, which may judge, and what the platform will assert to a person. The record of who requested it and who approved it is the evidence that the estate's posture was chosen rather than drifted into |

## What is true today, measured

**Every governance record is a Terraform apply.** The `harness-authority` mount holds
`ask-bindings` (which qualified cell answers, per source, plus 043's `relevance_cell`),
`model-matrix`, `protected-policies`, `definition-bindings`, `harness-ceilings`,
`role-bindings`, `policies` and `claim-mappings`. Changing any of them requires estate
credentials and a `terraform apply`.

**The person who knows the answer is not the person who holds the credential.** Deciding which
model should judge relevance is a judgement about model quality and cost. Holding the token
that can rewrite an agent's ceiling is an infrastructure privilege. Today they must be the same
person.

**A governed write path already exists.** `authority_submit.py` submits a claim-mapping change
and maps Vault's three native outcomes — queued for approval, applied, denied. The surface
*requests*; the trust fabric *decides*. This feature extends that shape rather than inventing
one.

**And its gate does not cover its path.** `authority_controlled_path` defaults to
`harness-authority/data/claim-mappings`. `controlled_paths` in the trust-fabric module lists
five paths — `sys/policies/acl/agent-ceiling-*`, the workload auth backend's `role/*`,
`agent-registry/register`, `identity/entity/*`, `sys/policies/acl/authority-change-*` — and
that KV path is not among them. The variable's description asserts gating the fabric does not
attach. Additionally `control_groups_enabled = var.quorum_policy != null`, and the development
default is null, so no gate is configured in dev at all. **Whether that is a defect or a
deliberate deferral is something this feature must establish and state, because it is the
mechanism the console depends on.**

**There is no `admin` role.** `ROLE_VISIBILITY` knows `operator` and `compliance-analyst`.
Creating a third role is a change to the governance vocabulary, and claim-to-role mapping is
itself gated — so the admin role's existence is an authority change of the same kind the
console requests.

**The role vocabulary does not match the ask.** ADR-0039's closed set is
`ask / plan / write / judge / summarize`. The ask names `research / plan / write / validate`:
two exist, two do not.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — An administrator sees the platform's posture (Priority: P1)

An administrator signs in and reads what the platform is currently configured to do: which
model answers, which judges, whether the relevance gate is on, which cells are qualified, and
which policies are protected. No estate credentials, no `terraform state show`.

**Why this priority**: Every later story is a change to something. An interface that can change
what it cannot display is one an administrator operates blind — and reading is independently
valuable: today there is no way to see the estate's posture without infrastructure access.

**Independent Test**: Sign in as an administrator, read the current configuration, and compare
it against the records in the trust fabric. Confirm the two agree, that no secret value is
shown, and that the read is recorded.

**Acceptance Scenarios**:

1. **Given** an authenticated administrator, **When** they open the console, **Then** the
   current governance configuration is displayed as it is in the trust fabric.
2. **Given** a configuration the platform cannot read, **When** the console loads, **Then** it
   reports that the configuration is unavailable — never an empty or default configuration.
3. **Given** any configuration read, **When** it returns, **Then** no credential, key, or
   secret value appears, and the read is recorded against the administrator.
4. **Given** a person who is not an administrator, **When** they request the console, **Then**
   they are refused and the refusal is recorded.

---

### User Story 2 — A change is proposed, and the trust fabric decides (Priority: P1)

An administrator changes which model is bound to a role. The console submits the change; the
trust fabric approves, queues it for quorum, or refuses. The console reports which happened
and never claims more than the fabric said.

**Why this priority**: This is the feature. It is also where the platform is most likely to
lie: an interface that reports "saved" for a change that was queued — or for one that went
nowhere — is worse than no interface, because it manufactures confidence in a posture that was
never applied.

**Independent Test**: Propose a binding change with a quorum configured; confirm it is reported
as pending and is not in force. Approve it out of band; confirm it takes effect. Propose one
that policy refuses; confirm refusal is reported as refusal.

**Acceptance Scenarios**:

1. **Given** a proposed change and a configured quorum, **When** it is submitted, **Then** it is
   reported as **awaiting approval** and the platform's behaviour is unchanged until approved.
2. **Given** a proposed change the fabric applies directly, **When** it is submitted, **Then** it
   is reported as applied, and reading the configuration back shows it.
3. **Given** a change the fabric refuses, **When** it is submitted, **Then** it is reported as
   **refused** — distinguishable from pending, and never as success.
4. **Given** any of the three outcomes, **When** it is reached, **Then** a record names the
   administrator, what was requested, and what the fabric decided.
5. **Given** a change proposing an unqualified cell, **When** it is submitted, **Then** it is
   refused before reaching the fabric — the console does not offer a binding the matrix cannot
   support.

---

### User Story 3 — The judge can be turned off, and the platform says so (Priority: P1)

An administrator disables LLM-as-a-judge. Answers that would have been judged still answer, and
each one **discloses that its relevance was not checked**.

**Why this priority**: The setting the maintainer named first, and the one that decides the
shape of every toggle after it. Answering silently would reintroduce gap 0g by configuration;
declining outright would mean an administrator turning off a check has turned off answering.

**Independent Test**: Disable the gate; ask a question that would have been judged; confirm the
answer arrives carrying the disclosure, and that the record shows the gate was off by an
administrator's decision rather than by failure.

**Acceptance Scenarios**:

1. **Given** the relevance gate is disabled, **When** a question is answered, **Then** the
   answer carries a visible disclosure that relevance was not checked.
2. **Given** the gate is disabled, **When** an answer is recorded, **Then** the record
   distinguishes *an administrator disabled this* from *the judge could not be reached*.
3. **Given** the gate is enabled again, **When** the next question is answered, **Then** the
   disclosure is absent and the gate runs — no restart required.
4. **Given** the gate is disabled, **When** an administrator views the console, **Then** the
   disabled state is visible without being looked for.

---

### User Story 4 — The console cannot be reached by an agent (Priority: P1)

A dispatched run cannot read or write governance configuration through this path, in any
wording, including via an instruction planted in a subject.

**Why this priority**: This is the feature's safety case. The console is a new write path to
exactly the records Principle IV says agents are structurally excluded from managing, and
ADR-0025 made a run observably unable to write what bounds it.

**Independent Test**: From a dispatched run, attempt to reach the console's read and write
paths in several ways. Confirm every attempt refuses, that the refusal is the platform's rather
than the model declining, and that a row fails if the exclusion is removed.

**Acceptance Scenarios**:

1. **Given** a dispatched run, **When** it attempts a configuration write, **Then** it is
   refused and the attempt is recorded.
2. **Given** an instruction planted in a subject naming this path, **When** a run analyses it,
   **Then** the instruction is recorded as an attempt and changes nothing.
3. **Given** the exclusion is removed, **When** the suite runs, **Then** a row fails — the
   safety case can lose.

---

### User Story 5 — Terraform stays the source of truth it already is (Priority: P2)

A record changed through the console and a record changed through Terraform do not disagree
silently. Whichever wrote last is visible as having written last.

**Why this priority**: Two writers, one record. The failure is not a conflict — it is a
*silent* conflict, where an administrator's change is reverted by the next apply and nobody
learns until behaviour changes.

**Independent Test**: Change a value through the console; run the estate's apply; observe what
happens to the value and confirm the outcome is visible rather than discovered later.

**Acceptance Scenarios**:

1. **Given** a value changed through the console, **When** the estate is applied, **Then** the
   outcome — preserved or overwritten — is observable rather than silent.
2. **Given** any configuration record, **When** it is displayed, **Then** its provenance says
   whether it was last set through the console or by an apply.

---

### Edge Cases

- **The quorum is not configured** (the development default): a change has no gate to pass, so
  it applies immediately. The console must say so rather than implying an approval happened —
  an unnamed absence of gating is how a development posture reaches production unnoticed.
- **The approver set is empty or unreachable**: a change that can never be approved must not sit
  as "pending" indefinitely with no way to learn that; it is reported as un-approvable.
- **An administrator disables the judge while an answer is in flight**: the answer completes
  under the configuration in force when it started, and its record says which.
- **A binding names a cell that is withdrawn after the binding is made**: existing behaviour
  (the run stops with the reason recorded) is unchanged; the console surfaces the withdrawal.
- **Two administrators change the same record concurrently**: the second sees that the record
  moved rather than overwriting silently.
- **The console is asked for a setting the platform does not have**: nothing is invented — an
  unimplemented setting is absent, not shown disabled.
- **A configuration read succeeds and a write path is unavailable**: reading works and the
  console says changes cannot currently be submitted, rather than accepting one that goes
  nowhere.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: An authenticated administrator MUST be able to read the platform's current
  governance configuration without holding estate credentials.
- **FR-002**: Configuration that cannot be read MUST be reported as unavailable, never as empty
  or default — an unreadable record and a permissive one are different states.
- **FR-003**: No credential, key, or secret value MAY appear in any configuration the console
  displays.
- **FR-004**: Every configuration read MUST be recorded against the person who made it.
- **FR-005**: A configuration change MUST be submitted as a **request** decided by the trust
  fabric, never applied by the interface itself.
- **FR-006**: The three outcomes — applied, awaiting approval, refused — MUST be reported
  distinctly, and a change awaiting approval MUST NOT be reported as applied.
- **FR-007**: Where no approval gate is configured, the console MUST disclose that the change
  took effect ungated rather than implying it was approved.
- **FR-008**: Every requested change MUST be recorded with the requester, the record, the
  requested value, and the fabric's decision — including refusals.
- **FR-009**: The console MUST NOT offer a binding the Qualified Model Matrix does not support,
  and MUST refuse one submitted anyway.
- **FR-010**: An administrator MUST be able to enable and disable the relevance judge.
- **FR-011**: With the judge disabled, an answer that would have been judged MUST still be
  produced and MUST carry a visible disclosure that its relevance was not checked.
- **FR-012**: The record of such an answer MUST distinguish *disabled by an administrator* from
  *the judge could not be reached*.
- **FR-013**: A configuration change MUST take effect without restarting a surface.
- **FR-014**: A dispatched run MUST NOT be able to read or write governance configuration
  through this path; the exclusion MUST be structural rather than a rule a model is asked to
  follow.
- **FR-015**: A row MUST exist that **fails** when the exclusion in FR-014 is removed.
- **FR-016**: The `admin` role MUST be established through the platform's existing gated
  authority-change mechanism, not asserted by configuration the console itself controls.
- **FR-017**: An administrator MUST NOT be able to grant themselves the admin role through the
  console.
- **FR-018**: The role names the interface presents MUST map onto ADR-0039's closed vocabulary,
  and where a presented name has no counterpart, the feature MUST either widen the vocabulary by
  amendment or drop the name — never silently introduce an unbacked role.
- **FR-019**: A record's provenance MUST say whether it was last set through the console or by
  an estate apply.
- **FR-020**: Where the console and an estate apply write the same record, the outcome MUST be
  observable rather than silent.
- **FR-021**: The interface MUST hold no governance logic: what is permitted is decided by the
  platform and the trust fabric, and the interface renders the result.
- **FR-022**: Settings the platform does not implement MUST be absent from the console rather
  than displayed as unavailable or disabled.
- **FR-023**: The feature MUST establish whether the existing claim-mapping write path is
  gated by the configured Control Group, and MUST state the answer rather than assuming it.

### Key Entities

- **Governance configuration**: the readable state of what the platform is permitted to do —
  bindings, qualified cells, gate toggles, protected records.
- **Configuration change request**: a proposed change, its requester, its target record, and
  the fabric's decision.
- **Administrator**: a person holding a role that permits reading and requesting governance
  changes, and which they cannot grant themselves.
- **Gate toggle**: a named platform check an administrator may enable or disable, with the
  disclosed consequence of disabling it.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An administrator can state the platform's current answering and judging posture
  from the console alone, without estate access.
- **SC-002**: 100% of configuration changes are decided by the trust fabric; zero are applied by
  the interface.
- **SC-003**: A change awaiting approval is never reported as applied, and is not in force until
  approved — asserted with a case that would pass if the outcomes were collapsed.
- **SC-004**: Zero credentials, keys, or secret values appear in any console response.
- **SC-005**: Every read, every requested change, and every refusal appears in the trail with
  its requester.
- **SC-006**: With the judge disabled, 100% of answers that would have been judged carry the
  disclosure, and zero are silently unjudged.
- **SC-007**: The safety case can lose: removing the agent exclusion makes a row fail.
- **SC-008**: 100% of attempts by a dispatched run to reach configuration refuse, across
  wordings and including one planted in a subject.
- **SC-009**: An administrator cannot grant themselves the admin role, in 100% of attempts.
- **SC-010**: Every role name the console presents resolves to a role the platform implements.
- **SC-011**: A configuration change is in force for the next request without a restart.
- **SC-012**: Where the console and an estate apply disagree about a record, the disagreement is
  visible in the console rather than discovered through changed behaviour.

## Assumptions

- **The trust fabric decides; the console asks.** This feature does not build an approval
  workflow — ADR-0016's Control Groups are it. What is new is that a person without estate
  credentials can originate the request.
- **The existing gated write path is the shape to extend**, not a second mechanism. Whether its
  configured gate actually covers its path is FR-023's question and is answered by this feature
  rather than assumed by it.
- **The portal remains a thin client.** No governance decision is made in the browser; the
  console renders what the platform and the fabric decide.
- **Terraform remains able to write these records.** This feature does not remove the estate
  path; it adds a governed one for a different person, and FR-019/FR-020 keep the two honest.
- **The judge toggle's semantics are settled here for every future toggle**: disclose rather
  than suppress, on 033's precedent — a disclosure appearing only past a threshold trains
  readers that silence means complete.
- **Not every operator-authored record is in scope.** Ceilings, definition bindings and the
  protected set are governance an estate owns; the console's first scope is the settings the
  maintainer named — the judge, role bindings, and product connections — with the rest
  reachable by the same mechanism once the shape is proven.
- **Product connection configuration (TFE, workload Vault) is in scope as configuration**, not
  as credential entry: values that are secrets continue to live in the trust store and are
  referenced, never displayed or entered through the console.
