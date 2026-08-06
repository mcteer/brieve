# Feature Specification: A model says what to do, not only what to use

**Feature Branch**: `spec/040-model-supplied-arguments`

**Created**: 2026-08-06

**Status**: Draft

**Input**: Measured against merged main — 020 put a model in the loop for *which* capability runs and left *what it runs with* to the platform, which supplies the same fixed values to every capability a model names.

## Traceability *(mandatory)*

| Field | Value |
| --- | --- |
| **Requirements (R1–R17)** | **R5, R11 (total interception)** — what a model may *say* widens; what it may *do* does not, and the governed entry stays the only one. **R4, R13 (evidence)** — what a model asked for must be recoverable, and what it asked *with* must not become evidence it was never meant to be. **R7 (fail-closed)** — a malformed request is refused and re-asked, never executed. R16 (sealed core — durability gains a field, additively) |
| **ADRs touched** | **ADR-0026** (the intent/result bracket — an intent must now carry enough to repeat the act it precedes), ADR-0022/ADR-0039 (**consumed, not revisited** — which model may answer is unchanged; only the shape of the answer moves), ADR-0047 (a passing stub is worse than a missing one, and this feature has an unusually available one), ADR-0051 (redaction of tool arguments — the rule this feature must break exactly once and no further), ADR-0065 (**why this is its own feature**: it was planned as a consequence of code mode, which was decided against; the finding is independent and outlived it) |
| **Evidence class** | **attestation-relevant, and it moves in two directions.** The trail gains nothing: what a model named is already recorded and what it named it *with* stays out, deliberately. What changes is that the **control plane** begins holding a model's own words so an interrupted act can be repeated faithfully — the first place raw model output rests durably anywhere |

## Clarifications

### Session 2026-08-06

- Q: Does this feature introduce authorization over *what* a model asks for, or only carry the request through? → A: Carry through only — each capability enforces its own rules as it does today; argument-level policy is deferred.
- Q: How large may a request be, and what happens when it is too large? → A: A stated platform default, which a capability may raise for itself where it declares its other properties; over it the answer is refused and re-asked, and the refusal records the size and never the content.
- Q: When is a kept request released? → A: Kept indefinitely until something deletes it. A configurable retention policy belongs in admin configuration and is owed, not built here — so this feature must leave the request removable rather than load-bearing.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — A model says what it wants done (Priority: P1)

A model choosing a capability also states what to do with it — which path to write, which value to set, which workspace to plan against. The platform performs the act; the model describes it.

**Why this priority**: This is the entire gap. Every capability that takes any input is, today, reachable by a model in name only — it can be named and cannot be directed. A platform whose model chooses the verb and never the object can automate almost nothing.

**Independent Test**: Give a model-driven run a capability that acts on something specified, let the model choose it, and confirm the act happened against what the **model** named rather than against a fixed value the platform supplied.

**Acceptance Scenarios**:

1. **Given** a run whose model names a capability and states what to do with it, **When** the step runs, **Then** the act is performed with what the model stated.
2. **Given** two runs whose models state different things for the same capability, **When** both run, **Then** the two acts differ accordingly — the platform is not substituting one value for both.
3. **Given** a capability that takes nothing, **When** a model names it, **Then** it runs exactly as it does today.

---

### User Story 2 — An interrupted act is repeated faithfully (Priority: P1)

A run disrupted partway is revived, and a step whose act had not landed is performed again — with **what the model asked for the first time**, not with an empty request and not by asking the model again.

**Why this priority**: The platform's central durability claim is that it re-observes rather than re-executes, and where it must re-run, it re-runs *the same thing*. Today that holds for free, because what a capability runs with is a constant the platform can always reproduce. The moment it comes from a model, reproducing it requires having kept it — and a revival that repeats an act with nothing in it is worse than one that fails, because it looks like it worked.

**Independent Test**: Interrupt a run at a step whose request came from a model, revive it, and confirm the repeat carries the same request and consulted no model to get it.

**Acceptance Scenarios**:

1. **Given** a disrupted run with an unfinished act at a step, **When** it is revived, **Then** the act is repeated with what the model originally asked for.
2. **Given** that revival, **When** the record is read, **Then** no model was consulted a second time for that step.
3. **Given** a run disrupted before this feature's information existed, **When** it is revived, **Then** it behaves exactly as it does today rather than failing.

---

### User Story 3 — What a model asked with does not become permanent evidence (Priority: P1)

A model's request is kept in one place, and the permanent record continues to say **what** was named and **who** named it, and not what it was named with. **It is kept until something removes it** — the platform does not expire it on its own, and saying so plainly is part of the requirement, because an unstated retention is one nobody can hold the platform to.

**Why this priority**: The permanent record is the one place a leaked secret cannot be taken back from, and a model may have read one out of an earlier result before composing its next request. The platform already refuses to write a model's words there beyond the name of what it chose, and that refusal was argued rather than assumed. This feature forces the material to be kept *somewhere*; it must not be allowed to drift into the place it was kept out of.

**Independent Test**: Complete a step whose request came from a model, then read every durable record the platform wrote and confirm the request appears in exactly one of them — and that removing it from that one place leaves everything else about the act intact.

**Acceptance Scenarios**:

1. **Given** a step whose request came from a model, **When** every record it produced is read, **Then** the request itself appears in exactly one place and that place is not the permanent record.
2. **Given** the permanent record for that step, **When** it is read, **Then** it says what was named, by which model, and how it was decided — and nothing about what it was named with.
3. **Given** a revival of that step, **When** the revival's own record is read, **Then** it too carries none of the request.
4. **Given** a completed act whose request is removed, **When** the run's records are read, **Then** everything else about the act is intact and the removal has broken nothing.

---

### User Story 4 — A malformed request is refused, never performed (Priority: P1)

A model that states something the platform cannot act on is asked again, within the same bound that already applies to naming something it may not use. It is never partially performed and never performed with the malformed parts dropped.

**Why this priority**: Widening what a model may say widens what it can get wrong. A model that could previously only fail by naming the wrong thing can now fail by describing the right thing badly — a new failure mode against a bound that was written for the old one. Guessing at a malformed request is how a platform performs an act nobody asked for.

**Independent Test**: Have a model state something malformed, and confirm the step re-asks rather than acting, and that exhausting the re-asks ends the run rather than proceeding.

**Acceptance Scenarios**:

1. **Given** a model that states something unusable, **When** the step resolves, **Then** it is re-asked rather than acted upon.
2. **Given** repeated unusable answers, **When** the bound is exhausted, **Then** the run ends in a recorded terminal state rather than acting on the last one.
3. **Given** a run whose model names capabilities that take nothing, **When** it runs, **Then** it behaves identically before and after this change.

---

### User Story 5 — Nothing that already worked has to be rewritten (Priority: P2)

Every scripted answer that stands in for a model in the merge lane keeps meaning exactly what it means today, and every act already recorded stays repeatable.

**Why this priority**: The rows that prove model-driven runs work at all are driven by scripted answers, and runs in flight carry records written before this change. A widening that requires every existing caller to move is a blast radius nobody measured, and one that invalidates records in flight breaks revival for work already underway.

**Independent Test**: Run the existing model-driven suites unchanged, and revive a run whose records predate this feature.

**Acceptance Scenarios**:

1. **Given** a scripted answer written before this change, **When** it is used, **Then** it means exactly what it meant before.
2. **Given** a record written before this change, **When** it is read back, **Then** it is usable and distinguishable from one that genuinely asked for nothing.

---

### Edge Cases

- **A capability that takes nothing at all.** Naming it must stay exactly as cheap and exactly as valid as it is today; "asked for nothing" is a legitimate answer, not a malformed one.
- **A model asks for something the capability itself forbids.** Permission to reach the capability is decided where it is decided today; whether *this* request is acceptable is the capability's own business, and it refuses as it already does. A permitted name with a target the capability rejects must refuse for the reason that is actually true rather than being reported as a permission failure.
- **A request that makes the act fail on its own terms.** Distinct from a malformed request and from a refused one: the platform understood it, was permitted to perform it, and the act failed. Three situations, three records.
- **The same capability named twice in one run with different requests.** Two acts, two records, and the second must not be mistaken for a repeat of the first.
- **A record written before this feature, revived after it.** It asked for nothing, which is true and must not be confused with information having been lost.
- **A request larger than its capability accepts.** Refused and re-asked, never truncated, and the refusal records how big it was rather than what it said. A capability that legitimately needs more raises its own bound; a capability that needs a short path is not given room for a file.

## Requirements *(mandatory)*

### Functional Requirements

**Saying it**

- **FR-001**: A model MUST be able to state **what to do** with a capability it names, not only which capability to name.
- **FR-002**: The platform MUST perform the act. Widening what a model may say MUST NOT become a second way for a model to act, and the shape of a governed step MUST NOT change: the model answers, the platform performs, and the same record is written around it.
- **FR-003**: Everything that decides whether an act may happen MUST keep deciding it, unchanged. A model stating a request MUST NOT widen what the run may reach. **Permission continues to be decided by which capability was named, not by what was asked for**: the platform carries the request to the capability, and the capability enforces its own rules exactly as it does today.

**Meaning it later**

- **FR-004**: What a model asked for MUST survive an interruption. A revived step that repeats an unfinished act MUST repeat it with **what the model originally asked for**.
- **FR-005**: A revived step MUST NOT consult a model again to recover the request. Asking again could produce a different one, and repeating a different act while claiming to have observed the first is re-execution wearing observation's clothes.
- **FR-006**: What a model asked for MUST be kept in **exactly one** durable place, and that place MUST NOT be the permanent record. The permanent record MUST continue to carry what was named and MUST NOT gain what it was named with.
- **FR-007**: The platform MUST bound how large a request may be, with a **stated default** that applies to every capability. A capability whose legitimate requests are larger MUST be able to raise the bound **for itself**, declared where its other properties are declared — which is a property of the capability, not a contract the platform enforces about the request's shape (see Clarifications).
- **FR-007c**: A request over its capability's bound MUST be refused and re-asked, never truncated. Truncating would perform a different act from the one described, which is worse than performing none.
- **FR-007d**: The refusal for an oversized request MUST record **the size and never the content**, on the platform's existing precedent for a message it declined to accept. Recording the content would let a record the platform cannot take back grow at whatever rate a request can be refused.
- **FR-007a**: What a model asked for MUST be **removable** without damaging anything else the platform relies on. It is kept until something removes it, and the platform expires nothing on its own — so a retention policy must be able to act on it later without the act's own accounting depending on it still being there.
- **FR-007b**: The retention of what a model asked for MUST be **stated** where an operator can find it. An unstated retention is one nobody can hold the platform to, and this material is a model's own words.

**Getting it wrong**

- **FR-008**: A request the platform cannot act on MUST be re-asked within the bound that already governs an unusable answer, and MUST NOT be acted upon.
- **FR-009**: A malformed request, a refused one, and one that was performed and failed MUST be distinguishable in the record.

**Not breaking what works**

- **FR-010**: Every scripted answer that exists today MUST keep meaning exactly what it means today.
- **FR-011**: Every record written before this change MUST stay readable and usable, and MUST be distinguishable from one that genuinely asked for nothing.
- **FR-012**: A capability that takes nothing MUST behave identically before and after this change.

**Not shipping the same defect a third time**

- **FR-013**: The platform MUST have a merge-blocking check that every capability it defines is either reachable by a run or **recorded as deliberately unreachable**. Two capabilities have shipped unreachable with passing checks; a property nobody watches is one that stops holding.

### Key Entities

- **Request** — what a model states it wants done with a capability. New, and the thing this feature exists for.
- **Answer** — what a model returns when asked what to do at a step. Today a name; after this, a name and a request.
- **Unfinished act** — the record that an act was about to happen and has not been confirmed to have finished. Must now carry enough to repeat the act faithfully.
- **Permanent record** — what the platform can never take back. Gains nothing here, and that is a requirement rather than an omission.
- **Capability inventory** — what the platform defines against what a run can actually reach. Not currently compared by anything.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A model-driven run performs an act against a target the **model** named, demonstrated by naming two different targets and observing two different outcomes.
- **SC-002**: **100% of the acts a model directs are decided by the same authority that decides every other act.** No new path, since one is the property the platform's central claim rests on.
- **SC-003**: An interrupted act is repeated with the original request, demonstrated by interrupting one and comparing — and demonstrated against **every** durable store the platform supports, since one of them keeps this information without being asked to.
- **SC-004**: A revived step consults no model, demonstrated by counting.
- **SC-005**: What a model asked for is recoverable from exactly one durable place and from **no** permanent record, demonstrated by looking in every one of them.
- **SC-005a**: Removing what a model asked for leaves the act's own accounting intact, demonstrated by removing it and then reading everything else about the act.
- **SC-006a**: An oversized request is refused and re-asked rather than truncated, and the refusal record carries its size and none of its content — demonstrated by looking.
- **SC-006b**: A capability that raised its own bound accepts a request a capability that did not would refuse, demonstrated by sending the same request to both.
- **SC-006**: An unusable request is re-asked rather than acted upon, and exhausting the re-asks ends the run — both demonstrated, since a bound that is never reached is not demonstrated by the path that does not reach it.
- **SC-007**: Every scripted answer written before this change produces the identical result after it, demonstrated across all existing model-driven suites without editing any of them.
- **SC-008**: A record written before this change is revivable after it.
- **SC-009**: Every capability the platform defines is either reachable or recorded as deliberately unreachable, and the check fails when one is neither.

## Assumptions

- **The design is carried, not re-opened.** 039 planned this as a consequence of code mode and was superseded ([ADR-0065](../../docs/adr/0065-code-mode-is-decided-against.md)). Its findings were measured against merged main and stand on their own: what a model may *answer* widens while what it may *do* does not; the alternative — handing the model the capabilities directly — was rejected because it moves the act inside the model's own turn and bypasses the bounded re-ask, the revival honesty, the per-step record and the answer-not-act contract. That alternative stays rejected and its unused machinery stays an open gap rather than being closed as a side effect here.
- **Permission is unchanged and out of scope.** Which capabilities a run may reach, and which model may answer for it, are decided by records that already exist. This changes what an answer *contains*, never what it *unlocks*.
- **The keeping is unbounded in time, and that is stated rather than hidden.** Measured: nothing in the platform deletes this class of record today — no expiry, no purge, no policy — so a request would persist for as long as the store does. This feature does not build a retention control and **does** owe one: it is a business decision an operator must be able to make, it belongs in administrative configuration alongside the other things that surface is accumulating, and it is recorded as owed rather than assumed away. What this feature must do is leave the material **removable** (FR-007a) and its retention **stated** (FR-007b), so the control can be added later without unpicking this one.
- **The permanent record's existing rule is correct and stays.** That it carries what was named and not what it was named with was argued when it was written, not defaulted into. This feature is the first thing to press on that rule and must not be the thing that erodes it.
- **A per-capability size bound is not the per-capability shape contract that was ruled out.** Registration already carries properties of a capability beside its handler, and a size is one more of those. What was ruled out is the platform holding a contract about a request's *shape* and deciding malformed centrally; each capability still decides what it can use. The two answers use different mechanisms and do not collide.
- **The reachability check is scoped to the platform's own capabilities.** It compares what the platform defines against what a run can reach. It says nothing about capabilities that might arrive from elsewhere, which is a different question with its own record.

## Deferred

Recorded so nobody re-derives why these are absent:

- **Letting a model perform acts directly** rather than answering with what it wants done. It is the rejected alternative above, it would give the platform's unused capability-mapping machinery its first caller, and it changes what a governed step *is* — which deserves its own record rather than arriving as a side effect.
- **Repeating part of an act rather than all of it.** An unfinished act is repeated whole. Anything finer requires marking progress inside an act, which nothing here needs.
- **Authorization over what a model asks for.** Permission stays a decision about *which* capability was named. Deciding which values a definition may use needs a policy vocabulary and a way for a ceiling to express it, and the platform has neither — the machinery that would carry it exists (a governance decision already receives the request) and nothing consults it, which is where it stays until something needs it.
- **Which capabilities any given run may reach.** Configuration design, deferred by earlier features and still deferred.
- **A configurable retention policy for what a model asked for.** Owed, not absent by accident. It is a business decision expressed in an administrative surface, and that surface does not exist yet — it is now wanted by customer-supplied sources, by endorsement of those sources, and by this. Three callers is the signal that the surface is its own feature rather than a field on somebody else's.
- **Capabilities supplied from outside the platform.** Recorded on the roadmap as customer-supplied context and sources; this feature's reachability check is deliberately about the platform's own.
