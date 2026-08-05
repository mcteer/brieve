# Feature Specification: The intake gauntlet

**Feature Branch**: `037-intake-gauntlet`

**Created**: 2026-08-05

**Status**: Draft

**Input**: User description: "let's move to automated skill intake" — scoped to all seven of ADR-0053's stages after the maintainer was shown that three of its named dependencies do not exist.

## Traceability *(mandatory)*

| Field | Value |
| --- | --- |
| **Requirements (R1–R17)** | **R4 (evidence over claims)** — the feature's output *is* evidence, and its central risk is producing evidence nobody can trust. **R6 (eval-gated promotion)** — the analyzer is itself promotable content and must be gated like any other. **R7 (fail-closed)** — every stage blocks rather than passes a candidate along. R5/R11 (interception — the analysis agent runs under a ceiling like any agent). R16 (sealed core — the audit vocabulary grows) |
| **ADRs touched** | **ADR-0053** (**Proposed** — the gauntlet; this feature decides its status), **ADR-0004** (the discipline being automated: pinned, provenance-checked, injection-reviewed, eval-passed), **ADR-0038** (**the hardened untrusted-content isolation tier, which does not exist and must be built here**), **ADR-0052** (how a judge is qualified — the analyzer inherits this pattern), ADR-0043 (a model verdict may gate and never approves), ADR-0021 (restricted and air-gapped estates), ADR-0030 (pinned versus consulted), ADR-0047 (a passing stub is worse than a missing one) |
| **Evidence class** | **attestation-relevant, and the feature is evidence machinery.** A reviewer's decision will rest on what this produces. An analyzer that under-flags produces a review that has been *reassured* rather than informed, which is worse than no automation at all — and that failure is silent by construction |

## Clarifications

### Session 2026-08-05

- Q: What is the detonation range made of? ADR-0053 names the development-grade identity stand-in, which is test-only today. → A: **A purpose-built range, not the test fake.** The fake is guarded by a merge-blocking rule requiring every conformance row that uses it to declare what failure it injects; promoting it to production would mean weakening a guard to reuse a convenience, which is the same shape as taking a dependency and loosening the licence gate to accommodate it. The range is an operated component with a stated posture — no real authority, no estate reachability, canary-seeded, fully audited — and being operated, it carries a named trigger in a decision record (Principle VI).
- Q: Where does the analyzer's qualification terminate? → A: **Its own seed set, on ADR-0052's mechanism but with its own floor.** Human-labelled hostile cases checked into the repository, reviewed like code, with a mechanical floor that FAILS rather than warns. The mechanism is inherited; the floor is not. ADR-0052's floor is calibrated to answering suites, and intake's failure modes are attack classes — redirection, exfiltration, encoded payloads, content aimed at the reviewer — so reusing that shape would measure the wrong thing at the right threshold.
- Q: If the gauntlet is unavailable, may a skill still be adopted by hand? → A: **Yes, and taking the manual path is itself recorded.** A pipeline whose absence blocks all adoption has become a dependency of the supply chain it protects — an availability problem presenting as a security control, and one that pushes people toward editing the pin directly, which leaves no record at all. The manual path stays and using it is evidence: who, when, which skill, and why the pipeline was unavailable. A bypass that is recorded can be reviewed for becoming routine; a bypass that is forbidden becomes invisible.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Upstream moves, and the platform notices (Priority: P1)

Upstream publishes a new version of an adopted skill. Rather than waiting for a person to notice, the platform detects the change against its recorded pin, computes the exact delta, and opens a version-bump proposal carrying the diff and its provenance. Nobody has read anything yet; the candidate is not adopted; nothing has been promoted. What has changed is that the work is *queued with its evidence attached* instead of waiting to be discovered.

**Why this priority**: It is the half of the feature that carries no new risk. No model reads the candidate, so the injection hazard the rest of the feature is built around is simply not present — and it already removes the latency cost ADR-0004 named as one of its two durable costs. It is also independently useful: if every later stage were abandoned, this alone would improve intake.

**Independent Test**: Move a pinned upstream commit, run the poller, and confirm a proposal appears carrying the delta and the recorded provenance, with nothing promoted and no model invoked.

**Acceptance Scenarios**:

1. **Given** a pinned skill whose upstream has not moved, **When** the poller runs, **Then** nothing is proposed and the check itself is recorded — "we looked and nothing changed" is a finding.
2. **Given** a pinned skill whose upstream has moved, **When** the poller runs, **Then** a proposal is opened carrying the exact delta against the pinned commit and the provenance of both versions.
3. **Given** an upstream that cannot be reached, **When** the poller runs, **Then** it reports the failure and proposes nothing — an unreachable upstream is not evidence of no change.
4. **Given** an estate with no outbound access, **When** intake runs against an imported bundle, **Then** the same pipeline produces the same proposal shape from the snapshot.

---

### User Story 2 — The candidate is read adversarially, by something that cannot act (Priority: P1)

A proposed change is analyzed before a person spends attention on it. The analysis runs in an isolated tier, under the narrowest ceiling in the fleet: it may read the delta and write one artifact — a structured report — and nothing else. Candidate text enters as data, never as instruction. The analyzer emits a verdict, and any flag short-circuits to the human with findings attached.

**Why this priority**: This is where the feature earns its name and where it can do the most harm. Pointing a model at hostile-by-assumption content is the attack surface the review exists to guard, so the containment is the deliverable — not the analysis.

**Independent Test**: Run the analyzer against a candidate containing an instruction aimed at the analyzer itself, and confirm the instruction has no reachable effect: the ceiling offers nothing to redirect *to*, the verdict is emitted, and the attempt is recorded.

**Acceptance Scenarios**:

1. **Given** a candidate carrying text addressed to the analyzer, **When** it is analyzed, **Then** the text is treated as data, the analyzer's behaviour is unchanged, and the attempt appears in the record.
2. **Given** an analyzer that attempts anything outside its ceiling, **When** it does so, **Then** the attempt is refused and recorded, exactly as any agent's would be.
3. **Given** an analysis that cannot complete, **When** the stage ends, **Then** the candidate is blocked rather than passed along.
4. **Given** any analyzer flag, **When** the stage ends, **Then** the candidate short-circuits to the human with findings attached and no later stage runs.

---

### User Story 3 — The candidate is detonated, and watched from outside (Priority: P1)

A candidate that reads clean is executed against a fixed task corpus in an isolated range, alongside the currently pinned version, and their behaviour is compared: what each attempted, what was denied, what the governance floor caught. The range is seeded with canaries so exfiltration or echo is caught mechanically rather than by a reader noticing. **The thing executing the candidate and the thing observing it are separate identities in separate processes**, and the observer reads the run's records from outside rather than reading candidate output into its own context.

**Why this priority**: The separation is the load-bearing property of the whole feature. An observer that ingests candidate output *is* the injection surface the gauntlet exists to inspect — a feature that gets every other stage right and collapses these two has built the vulnerability it was meant to prevent.

**Independent Test**: Detonate a candidate seeded to exfiltrate a canary, and confirm the canary is caught by the observer reading records from outside, with the specimen and observer holding distinct identities throughout.

**Acceptance Scenarios**:

1. **Given** a candidate and its pinned predecessor, **When** both run against the corpus, **Then** their behaviours are compared and the differences are reported.
2. **Given** a candidate that touches a canary, **When** it is detonated, **Then** the canary is reported without any person having to notice it.
3. **Given** a detonation run, **When** the observer produces its report, **Then** no candidate-authored content has entered the observer's context.
4. **Given** a detonation that cannot run, **When** the stage ends, **Then** the candidate is blocked — a detonation that did not happen is not a clean one.

---

### User Story 4 — The analyzer is itself gated (Priority: P1)

The analyzer is executed content like any other, so it is qualified before it is trusted and re-qualified as it changes: scored against a corpus of deliberately hostile candidates, held to a rate of what it must catch, held to a budget for what it may falsely flag, and checked for drift toward leniency over time.

**Why this priority**: P1 and not lower, because an unqualified analyzer is the ungated input to every intake decision above it. ADR-0052 settled the same problem for judges — the regress terminates at human-labelled cases in the repository — and an analyzer nobody re-qualifies reproduces exactly the failure that record was written against. **A lenient analyzer fails silently**: it produces clean reports, the reviews get faster, and nothing looks wrong.

**Independent Test**: Score the analyzer against the hostile corpus and confirm the must-flag rate and false-positive budget are enforced, and that a deliberately weakened analyzer fails the gate.

**Acceptance Scenarios**:

1. **Given** the hostile corpus, **When** the analyzer is scored, **Then** it must flag at least the required share and may falsely flag no more than the budget allows.
2. **Given** an analyzer weakened to flag less, **When** it is scored, **Then** the gate fails.
3. **Given** a change to the analyzer, **When** promotion is attempted without re-scoring, **Then** promotion is refused.
4. **Given** scores over time, **When** leniency drifts, **Then** the drift is detectable rather than absorbed.

---

### User Story 5 — The reviewer decides, on better evidence (Priority: P1)

A person opens the proposal and finds a package: what changed, what the analyzer found, how the candidate behaved against the corpus compared with the version in production, and whether any canary moved. They accept or reject. **Nothing the pipeline produced decided anything.** The accepted skill still lands in warn mode before enforce mode, as it does today.

**Why this priority**: This is the sentence the whole feature is measured against — the pipeline decides what a reviewer reads, never whether a skill promotes. A feature that quietly becomes an approval mechanism has replaced a slow human gate with a fast machine one, which is strictly worse than the status quo it was built to improve.

**Independent Test**: Confirm that no pipeline outcome can promote a skill, and that a human acceptance is required and recorded distinctly from every machine verdict in the package.

**Acceptance Scenarios**:

1. **Given** a candidate that passed every stage, **When** no person has accepted it, **Then** it is not promoted.
2. **Given** the record of a promotion, **When** it is read, **Then** the human acceptance is distinguishable from every machine verdict that preceded it.
3. **Given** an accepted candidate, **When** it is promoted, **Then** it lands in warn mode before enforce mode.

---

### Edge Cases

- **Upstream moves twice before review.** A second change arriving while a proposal is open must not silently replace the candidate under review — the reviewer would accept evidence describing different bytes.
- **The delta is enormous.** Analysis cost is proportional to upstream motion; an upstream that restructures its whole repository produces a delta no cheaper than the corpus. The pipeline must behave predictably rather than unboundedly.
- **The candidate is not text.** A skill bump that changes binary or non-instruction content is outside what an injection lens can read, and "the lens found nothing" must not read as "there is nothing to find".
- **The analyzer and the detonation disagree.** A clean read followed by hostile behaviour is the most interesting outcome the pipeline can produce and must reach the reviewer as such, not be reconciled away.
- **Canary content appears legitimately.** A skill that discusses secrets or credentials in ordinary documentation will trip naive canary detection; the false-positive budget exists for this and must be measured against realistic content.
- **The pipeline itself is unavailable.** Intake must remain possible by hand — a pipeline whose absence blocks all adoption has become a dependency of the supply chain it protects.
- **Upstream is compromised at the source.** Provenance proves which bytes upstream published, never that upstream was uncompromised when it published them.

## Requirements *(mandatory)*

### Functional Requirements

**Detection and proposal**

- **FR-001**: The platform MUST detect that a pinned upstream has moved, without an inbound network surface, and MUST work identically for estates that reach upstream through a proxy and for estates that receive an imported snapshot.
- **FR-002**: A check that finds no change MUST be recorded. "We looked and nothing had moved" is the evidence that the pin is being maintained rather than merely old.
- **FR-003**: A failure to reach upstream MUST be reported as a failure and MUST NOT be reported as no change.
- **FR-004**: A proposal MUST carry the exact delta against the recorded pin and the provenance of both versions, and MUST NOT promote anything.
- **FR-004a**: A proposal MUST state **which stages have run**. Detection alone produces a *detection proposal*; it becomes the full evidence package as later stages complete. An artifact whose analysis and detonation fields are simply absent reads as clean, and "no analysis has run" is a materially different claim from "analysis found nothing" — conflating them is the reassurance failure FR-027 exists to prevent, arriving through the shape of the artifact rather than through its wording.
- **FR-004b**: A proposal whose candidate has been superseded MUST be marked stale and MUST NOT be acceptable. Detection of supersession is required, not implied by identifying candidates by digest — the digest makes drift *visible*, and this makes it *refuse*.
- **FR-005**: A proposal whose candidate changes while it is open MUST NOT silently carry forward evidence produced about the earlier bytes.

**Containment of the analysis**

- **FR-006**: The analysis MUST run in an isolated tier intended for untrusted content, which does not exist today and is part of this feature.
- **FR-007**: The analysis agent MUST hold a ceiling that permits reading the delta and producing one report artifact, and nothing else — no product capability, and no egress beyond the pinned source.
- **FR-008**: Candidate content MUST enter the analysis as data rather than as instruction, and the analyzer MUST emit only a structured verdict.
- **FR-009**: The containment MUST hold structurally rather than by instruction: an analyzer that *is* successfully redirected MUST have nothing reachable to be redirected to. This MUST be asserted, not asserted-about.
- **FR-010**: Any analyzer flag MUST short-circuit to the human with findings attached, and no later stage may run.

**Detonation**

- **FR-011**: A clean candidate MUST be executed against a fixed task corpus alongside the currently pinned version, and their behaviours compared. The corpus does not exist today and is part of this feature.
- **FR-012**: The range MUST hold no real authority, reach no real estate, and MUST be seeded with canary material so that exfiltration or echo is detected mechanically.
- **FR-013**: The component executing the candidate and the component observing it MUST be separate identities in separate processes, and the observer MUST derive its findings from the run's records rather than from candidate output.
- **FR-014**: A detonation that cannot complete MUST block the candidate. A stage that did not run has said nothing.
- **FR-015**: The detonation range MUST be a purpose-built component with a stated posture — no real authority, no reachability to any real estate, canary-seeded, fully audited — and MUST NOT be the test-only authority fake.
- **FR-015a**: The test-only authority fake MUST remain test-only, and the rule requiring every conformance row using it to declare what failure it injects MUST NOT be weakened to accommodate this feature. Reusing it would trade a guard for a convenience.
- **FR-015b**: Being an operated component, the range MUST carry a named trigger in a decision record (Principle VI), and its posture MUST be reviewable rather than implied by what it happens to be built from.

**The analyzer as gated content**

- **FR-016**: The analyzer MUST be qualified against a corpus of deliberately hostile candidates before it is trusted, and re-qualified when it changes.
- **FR-017**: Qualification MUST enforce a minimum share of hostile cases caught and a maximum share of benign cases falsely flagged, both stated as numbers rather than as judgement.
- **FR-018**: Drift toward leniency MUST be detectable over time rather than absorbed silently.
- **FR-019**: The hostile corpus MUST cover redirection, exfiltration, encoded payloads, and content aimed at the reviewer rather than at the agent.
- **FR-020**: The analyzer's qualification MUST terminate in human-labelled cases checked into the repository and reviewed like code — the mechanism ADR-0052 established for judges, applied to a new subject.
- **FR-020a**: The corpus MUST have a mechanical floor that **fails** rather than warns. A floor nothing enforces is a suggestion, and this one is the root of every intake decision above it.
- **FR-020b**: The floor MUST be calibrated to intake's own failure modes — the attack classes of FR-019 — and MUST NOT be inherited verbatim from the judge's floor, which is calibrated to answering suites. Reusing that shape would measure the wrong thing at the right threshold.

**The human gate**

- **FR-021**: No pipeline outcome MAY promote a skill. Promotion MUST require a human acceptance.
- **FR-022**: The record MUST distinguish a machine verdict from a human approval, so a reader can never mistake one for the other.
- **FR-023**: An accepted candidate MUST still land in warn mode before enforce mode.
- **FR-024**: Every stage MUST fail closed: a stage that cannot complete blocks the candidate rather than passing it along.
- **FR-025**: Adoption MUST remain possible when the pipeline is unavailable. A pipeline whose absence blocks all adoption has become a dependency of the supply chain it protects.
- **FR-025a**: Taking the manual path MUST itself be recorded — who took it, when, for which skill, and why the pipeline was unavailable — and that record MUST be distinguishable from a promotion that passed the gauntlet.
- **FR-025b**: The manual path MUST NOT be quieter than the automated one. The failure being guarded against is a bypass that becomes routine because nothing makes its use visible.

**Boundaries**

- **FR-026**: This feature MUST NOT change what the existing promotion gate requires. It produces evidence *for* that gate.
- **FR-027**: Nothing in this feature MAY be described, in documentation or in the evidence package, as making an adopted skill safe. The limits statement MUST be **stage-aware**: it names what has not run as well as what ran and found nothing.
- **FR-027a**: A proposal carrying no analyzer verdict MUST say so in the same place a verdict would appear. Absence must be legible where presence would be, or a reader scanning for a finding sees nothing and concludes there was nothing to find. Detonation catches only what the corpus provokes, and the runtime governance floor remains the backstop.

### Key Entities

- **Pin** — the recorded upstream identity of an adopted skill: where it came from and exactly which version. What "moved" is measured against.
- **Candidate** — a specific proposed version, identified by content rather than by name, so evidence cannot drift onto different bytes.
- **Delta** — the exact difference between the pinned version and the candidate. The analysis subject, and the reason cost tracks upstream motion rather than upstream size.
- **Verdict** — what the analyzer concluded. May block; never approves.
- **Detonation comparison** — how the candidate behaved against the corpus relative to the pinned version: attempts, denials, canary contact.
- **Evidence package** — everything the reviewer is given. The feature's actual product.
- **Hostile corpus** — deliberately malicious candidates with known-correct verdicts, against which the analyzer is qualified.
- **Canary** — material planted in the range whose appearance anywhere outside it is proof of exfiltration.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A pinned upstream that has moved is detected without a person initiating the check, and a proposal carrying the delta exists before anyone has read the upstream text.
- **SC-002**: For every case in the hostile corpus, the analyzer's verdict is correct at or above the required must-flag rate — and a deliberately weakened analyzer **fails** the gate. A qualification that cannot fail has qualified nothing.
- **SC-003**: Falsely flagged benign candidates stay within the stated budget, measured against realistic skill content rather than only against obviously-clean text.
- **SC-004**: A candidate seeded to exfiltrate a canary is caught **mechanically**, with no reliance on a person noticing.
- **SC-005**: No candidate-authored content reaches the observer's context, demonstrated by an assertion rather than by inspection of the design.
- **SC-006**: No sequence of pipeline outcomes promotes a skill without a recorded human acceptance — **100%, with no tolerated exception**, since a single one converts the gate into a formality.
- **SC-007**: Every stage, when made to fail, blocks the candidate. Demonstrated for each stage rather than argued from a shared mechanism.
- **SC-008**: The reviewer's starting point is the evidence package rather than raw upstream text, and the package states what it does **not** establish.

## Assumptions

- **All seven stages are in scope by explicit decision.** The maintainer was shown that three named dependencies are absent — the hardened isolation tier, the golden-task corpus, and the analyzer's eval class — and chose the full gauntlet knowing the feature includes building them. The roadmap describes the eval class as "owed before it can be specified"; it is therefore specified here as a deliverable of equal weight to the pipeline, not as a follow-on.
- **The existing promotion gate is the consumer, not the subject.** Its order — provenance, then digest, then lens, then suites — is deliberate and is not revisited here.
- **The existing injection lens stays.** It is pattern-based and cheap; the analyzer is a second, deeper pass, not a replacement. A model-based lens replacing a deterministic one would trade a check that always runs the same way for one that does not.
- **Hostility is assumed, not detected.** Candidate content is treated as adversarial regardless of source, so the containment does not depend on judging upstream's trustworthiness.
- **The sealed core is in play.** Recording analyzer verdicts, detonation outcomes and canary contact adds audit vocabulary, so this needs a Principle V review.
- **Adopted content beyond skills is out of scope.** Packs, prompts and models have their own promotion paths.

## Deferred

Recorded so nobody re-derives why these are absent:

- **Automating the human review.** The pipeline raises the floor; the ceiling is deliberate and permanent.
- **Applying the gauntlet to packs, prompts, or models.** Different artifacts, different promotion paths, different failure modes.
- **Changing what the promotion gate requires.** This feature feeds that gate; redefining it is separate work.
- **Acting on a verdict automatically** — auto-rejecting, auto-filing, or auto-reverting. Every outcome routes to a person.
- **Detecting compromise at the upstream source.** Provenance establishes which bytes were published, never whether the publisher was sound.
