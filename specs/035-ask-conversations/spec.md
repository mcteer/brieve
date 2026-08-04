# Feature Specification: Ask becomes a conversation

**Feature Branch**: `035-ask-conversations`

**Created**: 2026-08-04

**Status**: Draft

**Input**: User description: "I want a chat interface layout similar to Claude and others versus what it looks like right now" — refined mid-specification to: "Layout, visuals, and the chat should hold context and be able to respond to follow-up questions."

## Traceability *(mandatory)*

| Field | Value |
| --- | --- |
| **Requirements (R1–R17)** | R7 (fail-closed — a conversation is reachable only by its owner), R12 (lean — no client framework, no build step), R16 (versioned seams — the ask contract gains a conversation; sealed core untouched) |
| **ADRs touched** | ADR-0039 (asking never acts — an ask must not become a turn), ADR-0034 (the portal stays thin — the transcript renders what the platform decided), ADR-0033 (transport parity — a conversation reachable on the API is reachable on MCP), ADR-0004 (adopted content provenance — claims still resolve against the pin), ADR-0009 (evidence over claims — the record must say what the model was shown) |
| **Evidence class** | attestation-relevant — every ask already writes `ask_answered`, and this feature changes **what the model was given**, so the record changes with it or the trail stops describing the answer it is attached to |

## Clarifications

### Session 2026-08-04

- Q: A follow-up like "what about multi-region?" carries nothing the router recognises. How should it be routed? → A: Explicit signal wins; silence inherits. A question carrying its own routable signal always routes on its own words and context can never override it; only a question with no signal of its own inherits the source of the exchange it follows.
- Q: Under ADR-0033, what does the MCP surface do when the API gains conversation operations? → A: Full parity. Conversation operations are catalogued and reachable on both transports and asserted by parity rows; ADR-0033 keeps no exception.
- Q: Is a declined exchange carried forward as context? → A: Carry the question, not the decline. The question is part of what is being asked about; the decline is a fact about the corpus rather than about the topic, and feeding it back invites a second decline by agreement rather than by reading.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — The answer stays, and the next question builds on it (Priority: P1)

A person asks how to run a Vault cluster in AWS. The answer appears beneath their question rather than replacing the page. They read it, type "what about multi-region?" into a composer at the bottom, and get an answer that understands what "it" refers to. Both exchanges stay on screen.

**Why this priority**: This is the request. Today the surface shows one question at a time and discards the previous answer, so nobody can compare two answers or refer back to one — and a follow-up phrased the way people actually speak is meaningless to a platform that only ever sees the latest sentence alone.

**Independent Test**: Ask a question, receive an answer, ask a follow-up that is unintelligible on its own, and confirm the second answer addresses the subject of the first. Both exchanges remain visible.

**Acceptance Scenarios**:

1. **Given** a new conversation, **When** a person asks a question and it is answered, **Then** question and answer are both visible, the question still legible above the answer, and the composer is ready for the next one without the page having navigated.
2. **Given** a conversation whose first exchange was about Vault clustering, **When** the person asks "what about multi-region?", **Then** the answer addresses multi-region Vault clustering and cites corpus sections that resolve.
3. **Given** a conversation with several exchanges, **When** a new answer arrives, **Then** the person is brought to it and earlier exchanges remain reachable by scrolling.
4. **Given** any answer in the transcript, **When** it is read, **Then** it carries what an answer carries today: claims, citations as followable destinations, the source consulted, and the provenance notes exactly as its source carries them (the ground note on guidance answers, the window note when a read truncated).

---

### User Story 2 — Conversations survive leaving the page (Priority: P2)

A person asks something, closes the tab, and comes back later. Their earlier conversations are listed, and opening one shows the exchange as they left it.

**Why this priority**: Persistence was chosen explicitly. Without it the transcript is a trick of one page load — the platform records every ask for an auditor and shows the person who asked nothing, which is the asymmetry this feature closes.

**Independent Test**: Hold a conversation, reload the browser, confirm it is listed and reopens complete.

**Acceptance Scenarios**:

1. **Given** a person has held a conversation, **When** they return later, **Then** it appears in a list, identified by something they can recognise it by.
2. **Given** a listed conversation, **When** it is opened, **Then** every exchange appears in the order it happened, including any that were declined or refused.
3. **Given** two different people, **When** each lists their conversations, **Then** neither sees the other's.
4. **Given** a conversation somebody no longer wants, **When** they delete it, **Then** it leaves their list and the platform's own record of those asks is unaffected.

---

### User Story 3 — The platform can still be asked what it was shown (Priority: P2)

Someone reviewing an answer can establish which earlier exchanges the model was given when it produced that answer.

**Why this priority**: Carrying context changes the answer. A record that says only which corpus was pinned no longer describes what produced it, and a trail that has quietly stopped describing its subject is worse than one that never claimed to.

**Independent Test**: Answer a follow-up, read the evidence record for that ask, establish which prior exchanges were included.

**Acceptance Scenarios**:

1. **Given** an answer produced with conversation context, **When** its evidence record is read, **Then** the record identifies the conversation and which prior exchanges were supplied.
2. **Given** an answer produced with no prior context, **When** its record is read, **Then** it is distinguishable from one that had context available.
3. **Given** context truncated because the conversation grew long, **When** the answer is read by the person who asked, **Then** they are told not all of the conversation was carried.

---

### User Story 4 — The chat surface looks like the rest of the platform (Priority: P3)

The transcript, the composer and the conversation list carry the visual identity already established — the same type roles, the same restraint with colour, the same treatment of anything a person would quote to an auditor.

**Why this priority**: The request named visuals. A chat layout assembled without the established tokens is a second design system, and the first hardcoded colour is invisible until the theme changes.

**Independent Test**: Render every state of the surface and confirm no colour or typeface appears outside the token system.

**Acceptance Scenarios**:

1. **Given** any state of the chat surface, **When** its styling is examined, **Then** every colour and typeface resolves to an existing design token.
2. **Given** a record hash, disposition or timestamp in the transcript, **When** it is rendered, **Then** it appears in the role reserved for what a person carries to an auditor.
3. **Given** the light and the dark theme, **When** each is rendered, **Then** both are legible and neither was produced by inverting the other.

---

### Edge Cases

- **A follow-up meaningless on its own.** "What about multi-region?" names no product and offers nothing to retrieve on. It must be resolved against the conversation rather than answered literally or declined.
- **A follow-up that changes the subject.** Vault clustering, then Consul backups. Carried context must not drag the second answer back toward Vault.
- **A conversation that outgrows the bound.** Context is bounded. At the bound the platform drops the oldest material rather than failing, and says so.
- **An estate question inside a documentation conversation.** A question carrying its own signal routes on its own words, so "which runs failed?" asked inside a documentation conversation reaches the records and nothing about the conversation prevents it — and the reverse holds. Only a question with no signal of its own inherits.
- **A declined or refused exchange mid-conversation.** A decline is an answer and stays in the transcript. Its QUESTION is carried as context; the decline itself is not — see FR-014a.
- **The same conversation open twice.** Two questions asked concurrently must not interleave into one exchange or lose one another.
- **Somebody else's conversation.** Guessing an identifier must not open it.
- **A very long answer.** The transcript stays navigable and the composer stays reachable.
- **Nothing to list yet.** The surface is usable and self-explanatory with no conversations.
- **A slow model.** An answer takes a minute or two; the transcript shows the question was received and is being worked on, without navigating.

## Requirements *(mandatory)*

### Functional Requirements

**The transcript**

- **FR-001**: The ask surface MUST present a conversation as a sequence of exchanges, each showing the question asked and what came back, in the order they happened.
- **FR-002**: A new exchange MUST be added without replacing earlier ones and without the page navigating.
- **FR-003**: Every answer MUST carry what the current single-shot answer carries: claims, citations as followable destinations, the source consulted, and the provenance notes exactly as each source carries them today (the ground note unconditionally on guidance answers, the window note when a read truncated).
- **FR-004**: A declined or refused question MUST appear as its own exchange, distinguishable from an answered one, carrying the platform's own words for why.
- **FR-005**: The surface MUST indicate that a question was received and is being worked on.
- **FR-006**: When an answer arrives, the person MUST be brought to it, and earlier exchanges MUST remain reachable.

**Conversations that persist**

- **FR-007**: A conversation MUST survive the person leaving the surface and returning.
- **FR-008**: A person MUST be able to see a list of their own conversations, each identified by something derived from its content rather than an opaque identifier.
- **FR-009**: A person MUST be able to open any of their conversations and see every exchange in it.
- **FR-010**: A person MUST be able to start a new conversation without disturbing existing ones.
- **FR-011**: A person MUST be able to delete a conversation. Deletion removes it from their view and MUST NOT remove or alter the platform's record of the asks it contained.
- **FR-012**: A conversation MUST be reachable only by the person who created it, and MUST NOT be reachable by another person who knows or guesses its identifier.
- **FR-013**: Conversations MUST be scoped within a tenant and MUST NOT be reachable across tenants.

**Context**

- **FR-014**: A question asked within a conversation MUST be answerable in terms of earlier exchanges in that conversation, such that a follow-up meaningless in isolation is answered about the subject under discussion.
- **FR-014a**: When an earlier exchange was declined or refused, its QUESTION MUST be carried as context and the decline or refusal itself MUST NOT be, so that a follow-up keeps its subject without the earlier verdict being offered to the model as evidence.
- **FR-015**: The material carried forward MUST be bounded, and the bound MUST be a stated quantity rather than whatever happens to fit.
- **FR-016**: At the bound the platform MUST carry the most recent material, drop the oldest, and tell the person that not all of the conversation was carried.
- **FR-017**: A question that carries a routable signal of its own MUST be routed on its own words, and carried context MUST NOT override that.
- **FR-017a**: A question that carries no routable signal of its own MUST inherit the source of the exchange it follows, so that a bare follow-up in a documentation conversation reaches documentation and one in a records conversation reaches records.
- **FR-017b**: Routing MUST remain deterministic: the same question at the same point in the same conversation MUST always reach the same source.
- **FR-018**: A claim MUST still rest on a citation that resolves against the pinned corpus. Carried context MUST NOT become a source a claim can cite.
- **FR-019**: Context MUST NOT be carried across conversations, and MUST NOT be carried from a conversation belonging to anybody else.

**The record**

- **FR-020**: The evidence record for an ask MUST identify the conversation it belongs to.
- **FR-021**: The evidence record MUST make it possible to establish which prior exchanges were supplied to the model for that answer.
- **FR-022**: An ask with no prior context MUST be distinguishable in the record from one that had context available.
- **FR-023**: Deleting a conversation MUST NOT alter, remove, or make unreadable any evidence record.

**What must not change**

- **FR-024**: An ask MUST NOT become able to start a run, change anything, or touch the estate. The conversation surface MUST NOT acquire any capability a single ask does not have.
- **FR-025**: Asking and running agents MUST remain distinguishable to a person as different activities with different consequences, and MUST NOT be merged into one surface.
- **FR-026**: The portal MUST NOT classify, decide, or author any part of an outcome. Every sentence a person reads about one MUST come from the platform.
- **FR-027**: Every request the portal makes MUST be a catalogued platform operation.
- **FR-027a**: Every conversation operation MUST be reachable on both transports and MUST behave identically on each — listing, opening, deleting, and asking within a conversation. No conversation capability may exist on one transport and not the other.
- **FR-028**: The chat surface MUST meet the same accessibility standard as every other page, in every state, including a transcript long enough to scroll.
- **FR-029**: The surface MUST serve its own assets, with no build step and no third-party fetch.
- **FR-030**: Every colour and typeface on the chat surface MUST resolve to an existing design token.

### Key Entities

- **Ask conversation**: A sequence of exchanges held by one person within one tenant. Carries something a person recognises it by and when it was last added to. Cannot start anything.
- **Exchange**: One question and what came back — an answer with claims and citations, or a decline or refusal with its stated reason. Belongs to exactly one conversation, and corresponds to an evidence record already written for that ask.
- **Carried context**: The bounded material from earlier exchanges supplied to the model when answering a later question. Not a source, not citable, and identified in the record.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A person can ask, read the answer, and ask a follow-up phrased naturally, without the page navigating and without retyping the subject.
- **SC-002**: A follow-up meaningless in isolation is answered about the subject under discussion in at least 9 of 10 attempts across a set of realistic follow-up phrasings.
- **SC-003**: A conversation held before a reload is listed and reopens complete after it, every exchange in its original order.
- **SC-004**: Nobody can see, open, or carry context from a conversation that is not theirs — verified by attempting it directly with a known identifier.
- **SC-005**: For any answer produced with context, which prior exchanges the model was given can be established from the record alone.
- **SC-006**: Deleting a conversation leaves every evidence record for its asks readable and unchanged, verified by comparing the record before and after.
- **SC-007**: Every state of the chat surface — empty, one exchange, many, one in flight, declined, refused, the conversation list, the delete confirmation — passes the accessibility standard, in both themes.
- **SC-008**: The surface reflows at 320 pixels with no horizontal scrolling, and the composer stays reachable and unobscured with a transcript long enough to scroll.
- **SC-009**: No colour or typeface appears on the chat surface outside the token system.
- **SC-010**: Asking a question as a follow-up routes it to the same source as asking it standalone, for every question that carries a routable signal of its own.
- **SC-010a**: A follow-up carrying no routable signal reaches the same source as the exchange it follows — verified in both directions, in a documentation conversation and in a records conversation.
- **SC-011**: Every claim resolves to a section of the pinned corpus; no claim rests on something said earlier in the conversation.
- **SC-011a**: A follow-up to a declined question is answered when the corpus supports it, at a rate no worse than the same follow-up asked after an answered question.
- **SC-012**: When a conversation exceeds the context bound, the person is told not all of it was carried, and the answer still arrives.
- **SC-013**: The same conversation operation, performed on either transport, produces the same outcome — including the same source consulted, the same disposition, and the same stated reason when declined.

## Assumptions

- **The reader is the asker.** Conversations are private to their creator. Sharing, hand-off and team visibility are out of scope and carry their own disclosure decisions.
- **A title is derived, not demanded.** Nobody names a conversation before they can use it; a recognisable label comes from what was asked.
- **Context is bounded by recency.** At the bound the most recent exchanges are the ones worth keeping — somebody following up is following up on what they just read.
- **The existing thread surface is untouched.** Threads remain where turns act. This is a parallel surface sharing no store, no vocabulary and no navigation with it beyond the two entries already in the header.
- **The outcome is the platform's.** The portal continues to render and never to classify, so any new sentence about an outcome is authored platform-side.
- **One model, one corpus.** No model selector, no source selector, no per-conversation configuration.
- **Conversations are kept until deleted.** No age-based expiry and no cap on how many a person may hold; the evidence record has its own lifecycle and is untouched by any of this.
- **Exchanges are ordered by when the platform accepted them.** A conversation open in two places converges on reload rather than merging live; concurrent questions are appended in acceptance order and neither is lost.
- **One name.** “The ask surface” is the canonical name for this page throughout; “chat” and “conversation surface” in this document are informal references to the same thing, never a second page.
- **The ask surface becomes the conversation surface.** There is no separate single-shot page to maintain beside it; a new conversation begins empty and exists once a first question is asked.

## Deferred

Recorded so nobody re-derives why these are absent:

- **Streaming.** Answers arrive whole. Token-by-token rendering shows a person text before it has been checked against the pin, which is a decision about citation integrity rather than a visual nicety.
- **Sharing a conversation.** Another person reading one raises disclosure questions this spec does not answer.
- **Renaming, folders, pinning, search across conversations.**
- **Editing or re-asking an earlier question in place.** Rewriting history in a surface whose records are evidence needs its own thinking.
- **Carrying context across conversations.** A conversation is the boundary.
