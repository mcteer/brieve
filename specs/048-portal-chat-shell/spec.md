# Feature Specification: Ask and Build share one conversational shell

**Feature Branch**: `spec/048-portal-chat-shell`

**Created**: 2026-08-17

**Status**: Draft

**Input**: User description: Restyle the portal so Ask and Build are one product with two verbs, not two layouts. The approved direction is the dark conversational shell the maintainer signed off from rendered mockups on 2026-08-17: a narrow icon rail, a list of the person's own work, a thread, and a single-row composer that is wider than the reading column and centred in the stage. Build's thread is the person's request followed by system events along the Research → Plan → Write → Judge → Propose spine. Ask's thread is the person's questions followed by grounded answers with visible citations. Phases never appear in the shared header — that would make Ask look like a stalled Build. No new routes or operations; one additive read-only intake-text field on an existing read so the in-flight thread can show what 047 already accepted. Closes the visual gap 047 left when Propose reused Ask's composer classes but replaced the conversation with a status board.

## Traceability *(mandatory)*

| Field | Value |
| --- | --- |
| **Requirements (R1–R17)** | **R12 (lean)** — presentation only: no new operated component, no client framework, no build step, no third-party fetch at runtime. **R15 (thin portal)** — the restyle must not move logic, orchestration, or model calls into the browser. **R7 (fail-closed)** — not implicated in new enforcement; Ask must remain unable to act after the restyle (regression of ADR-0039, not a new deny path) |
| **ADRs touched** | **ADR-0034** (portal stays a thin client of the API; this feature restyles that client). **ADR-0039** (Ask never acts — the distinction stays *visible* in chrome and copy, not only in a glossary). **ADR-0033** (no surface-parity change: one transport's presentation). **ADR-0004** (any newly vendored face is adopted content and carries provenance). Consumes 012/028/034/035/047 for existing surfaces; does not reopen their operations |
| **Evidence class** | **none** — presentation carries no new evidence and changes no record |
| **Sealed core** | **None.** Templates, stylesheet, and any self-hosted faces. One additive read-only field on an existing run or result read (FR-013) — no new route, no new operation, sealed core untouched. |

## The measured gap *(context)*

034 gave the portal a visual identity: three type roles, named tokens, light and dark themes, HashiCorp's ramp with a serif heading and Roboto body. 047 then added Build as a second primary verb. What shipped is two products that share a few class names. Ask is a transcript with sticky composer. Build empty is a lede and a box. Build in flight is a word-list of phases and a status pill — the person's prompt is not on the page. The never-acts distinction 028 put in the nav is still there; the *pages* no longer look like the same assistant.

A person moving from Ask to Build should keep the same landmarks: where work is listed, where the conversation is, where they type. What changes is the verb and what the thread is allowed to contain.

## Clarifications

### Session 2026-08-17

- Q: Which of the four mockup cousins is the thread treatment? → A: **The spine.** The person's words sit as a quoted request; what follows is a vertical sequence of nodes (completed, current, waiting). Build's nodes are the 047 phases. Ask's nodes are answers with citations. The console split (live file beside the log), the quiet definition table, and the dispatch blotter were drawn to test the same chrome and are **not** this feature. A live file pane would need file bodies the portal does not already have; that is a payload change, which this feature forbids.
- Q: Dark only, or keep 034's dual theme? → A: **Dark is the designed theme.** 034 required both themes so dark would not ship unverified. This restyle *is* the dark identity; a light companion that is not in the approved mockups is out of scope. The accessibility lane covers the designed theme. A reader whose system prefers light still sees the designed surface.
- Q: Does 034's type and palette still govern? → A: **Accessibility, tokens, no third-party fetch, and the three type roles still govern. The HashiCorp/Palatino/Roboto direction does not.** Faces, ground, and chrome accent come from the approved mockups: a single sans-serif for prose and controls, a monospaced evidence face, a near-black ground, one warm chrome accent for the mark, the primary action, and the current conversational state. Product identity colours (034 US2) remain for packs, where the platform already knows the product. Saturated colour is still reserved for meaning — chrome identity, product, or verdict — not decoration.
- Q: How tall and how wide is the composer? → A: **One row, centred, wider than the reading column, not edge-to-edge.** Context chips sit on that same row, beside the action. A stacked field-plus-chips block and a full-bleed bar are both defects.
- Q: The in-flight Build page does not currently receive the person's request, and this feature forbids new payloads — which wins? → A: **The request is shown.** 047 already accepted that message; the page omitting it is the gap this restyle exists to close. One additive, read-only field on the run or result read the portal already performs names that intake text. Same exception shape as 034's definitions packs field: transport-shared, no new route, no new behaviour. Inventing the prompt in the template is forbidden.
- Q: Does in-flight Build gain a “steer this run” composer? → A: **No new operation.** Empty Build and every Ask state keep the composers they already have. In-flight Build shows the same composer chrome so the shell does not split; submitting from that page MUST NOT start a second propose and MUST NOT steer the current run. Empty Build remains the posting surface; its list control stays **New**. If in-flight chrome is shown, the only operable control in that row is named **New build** and is a link to empty Build, not a posting action.
- Q: Which faces, for provenance? → A: **Inter for prose and controls; IBM Plex Mono for evidence.** Those are the faces on the approved mockups. They are not universally present, so they are self-hosted with ADR-0004 provenance (034 FR-002 / FR-002a). No runtime CDN.
- Q: At 320px, what happens to rail plus list plus thread? → A: **Stack or collapse so the thread and composer remain usable, with no horizontal scrolling.** The work list may hide when empty (today's Ask behaviour). Icon-rail items keep accessible names matching the verbs (Build, Ask, Settings, Sign out) — icons are not the only name.
- Q: What happens to the superseded identity's files? → A: **They leave with the restyle.** Faces, provenance records, and styles or templates that exist only to serve Palatino/Roboto or the pre-shell chrome MUST be removed in the same change that lands the new identity. A leftover unused face or stylesheet is a defect (R12), not a souvenir. Approval mockups are not product artifacts and MUST NOT be committed with this feature.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ask and Build are the same place with two verbs (Priority: P1)

Someone who has used Ask opens Build (or the other way around) and does not have to relearn the page. The same landmarks are present: a way to switch the verb, a list of their own work on this surface, the conversation, and a place to type. The list is Builds on Build and Conversations on Ask. The action on the composer says **Build** or **Ask**. The shared header does not grow Build-only phase furniture.

**Why this priority**: This is the feature. Everything else is how the thread and the composer earn that sameness.

**Independent Test**: Open Ask and Build signed-in, empty and with history; a reviewer who cannot read the URL can still say which verb they are on, and cannot point at a region that exists on one surface and is absent on the other except the thread's contents and the list's labels.

**Acceptance Scenarios**:

1. **Given** a signed-in person on Ask or Build, **When** they look at the page, **Then** they see the same shell: icon rail (Build, Ask, Settings, sign out — each with an accessible name matching that verb), a list of their work on this verb, a thread stage, and a composer.
2. **Given** Ask, **When** the header and composer render, **Then** nothing presents Research / Plan / Write / Judge / Propose as chrome, and a status that Ask never acts remains visible without being explained in a paragraph.
3. **Given** Build in flight, **When** the header renders, **Then** the current phase may be named as status, but the five-phase sequence is not a global meter that Ask would have to hollow out.
4. **Given** Settings, signed-out, login failure, or the operator run page, **When** they render, **Then** they inherit the same identity (ground, type roles, accent, rail where navigation applies) rather than falling back to the previous identity.
5. **Given** a person using a screen reader on the icon rail, **When** they land on an item, **Then** they hear the verb (Build, Ask, Settings, or Sign out), not an unnamed graphic.

---

### User Story 2 - The thread is a conversation, including while Build runs (Priority: P1)

On Ask, the person sees what they asked and what was answered, with citations looking like references rather than body copy. On Build, they see the request they typed, then each phase as it completes or waits, including failure on the phase that failed. The prompt that started a Build remains on the page while it runs. Completed work stays visible above the current step.

**Why this priority**: 047 already required live phase progress. The defect is that progress replaced the conversation. Restoring the conversation without hiding phases is the Build half of US1.

**Independent Test**: Load an in-flight Build that has finished Research and Plan and is in Write; the original request is readable, completed phases remain, Write is the current node, later phases are waiting. Load an Ask with two exchanges; both questions and both answers with citations are readable in the same spine grammar.

**Acceptance Scenarios**:

1. **Given** a Build that has started, **When** the thread renders, **Then** the person's intake text is present as the first conversational turn, taken from the platform's run or result read — not invented in the page, and not only a truncated list title.
2. **Given** that Build, **When** phases have completed, **Then** each completed phase remains visible as a node in order, the active phase is obvious, and a failed phase is marked failed with the user-safe reason 047 already requires — later phases do not appear as if they ran.
3. **Given** an Ask with answers, **When** the thread renders, **Then** each answer is a node in the same spine grammar, claim text is prose, and citations are evidence.
4. **Given** a person who cannot distinguish colour, **When** they read either thread, **Then** completed / current / waiting (Build; 047 statuses `completed` / `active` / `pending`) and answer / citation (Ask) remain distinguishable by shape and label. Failed is marked failed.

---

### User Story 3 - The composer is one row you type into (Priority: P1)

The place they type is a single row: field, any context chips, action. It sits centred in the stage, wider than the reading column, with visible margin to the stage edges. It does not grow a second row for chips, and it does not stretch to the full width of the stage.

**Why this priority**: The mockups failed this twice (stacked height, then full-bleed on two cousins). The maintainer's correction is part of the approved direction, not polish.

**Independent Test**: Measure the composer on Ask empty, Ask with a thread, Build empty, and Build in flight: one row; centred; wider than the reading column; not flush to both stage edges.

**Acceptance Scenarios**:

1. **Given** empty Ask, Ask with a thread, or empty Build, **When** the composer renders, **Then** the field, chips, and action share one row, and submitting does what that surface already does.
2. **Given** that composer, **When** the stage is the signed-in conversational width, **Then** the composer is centred, wider than the thread's reading column, and not edge-to-edge in the stage.
3. **Given** Ask, **When** the action is read, **Then** it is labelled Ask. **Given** empty Build, **Then** it is labelled Build.
4. **Given** an in-flight Build, **When** the composer chrome is present, **Then** using it does not start a second propose and does not steer the current run. The operable control in that row is named **New build** and is a link to empty Build. Empty Build remains the posting surface; its list control stays **New**.

---

### User Story 4 - The identity still passes the accessibility gate (Priority: P1)

Every criterion the portal passes today it still passes afterwards — automated and human — on the designed theme.

**Why this priority**: Equal to US1. A prettier portal that loses a WCAG criterion is a regression this platform would have to undo.

**Independent Test**: The dedicated accessibility lane runs unchanged and green over every page state it covers today, on the designed theme.

**Acceptance Scenarios**:

1. **Given** every page state the lane covers, **When** it runs against the designed theme, **Then** axe-core reports no violation at WCAG 2.2 AA.
2. **Given** the keyboard rows, **When** they run, **Then** the focus indicator is drawn and unobscured, every target meets 24×24, the page reflows at 320px with no horizontal scrolling, and text-spacing overrides clip nothing.
3. **Given** the narrowest supported width, **When** the shell renders, **Then** rail, list, and thread stack or collapse so the thread and composer remain usable, with no horizontal scrolling — the behaviour 028 established after CI's Linux rendering broke first.

---

### Edge Cases

- A page in a state the mockup never showed (a refusal, a failed login, a delete confirmation, an endorsed-content review) must inherit the identity rather than the previous one.
- Build empty (no run yet) still uses the shared shell; the thread may be a quiet prompt to start, not a different layout. Submitting there is the existing intake.
- Ask empty likewise: same shell, empty conversation, composer ready. Follow-up Ask is unchanged.
- In-flight Build shows the shared composer as chrome only: it does not post a new propose and does not add a steer operation. The operable control in that chrome is named **New build**.
- The work list may omit itself when this person has nothing to list (today's Ask collapse). New remains reachable.
- Long unbroken strings — a record hash, a correlation id, a repository URL — must not force horizontal scrolling at 320px.
- A person with a text-spacing override or a large default font size must still get a usable page: the type scale is relative, not fixed.
- The operator run surface is not a third conversational product: it inherits identity and must not reintroduce an agent picker into Ask or Build chrome.
- Sign-out and the skip-to-content link remain present and operable.
- Files that nothing remaining loads — superseded faces, their provenance, orphaned styles or templates — are removed rather than left beside the new identity.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Ask and Build MUST share one shell: icon rail, work list, thread stage, composer. No third layout for "Build is running." Each rail item MUST have an accessible name matching its verb (Build, Ask, Settings, Sign out).
- **FR-002**: The shared header MUST NOT carry a Build-only phase meter. Phase progress lives in Build's thread (FR-006). Ask's header MUST keep a visible never-acts status (ADR-0039).
- **FR-003**: The work list on Build MUST list Builds; the work list on Ask MUST list Conversations. Switching the verb in the rail MUST land on that verb's list, not a mixed list. An empty list MAY omit the column (existing Ask collapse); New remains reachable.
- **FR-004**: The composer MUST be a single row (field, chips, action), centred in the stage, wider than the reading column, and not edge-to-edge. The action label MUST be Ask on Ask and Build on empty Build. In-flight Build MAY show that chrome and MUST NOT use it to start a second propose or to steer the current run (no new operation). If that chrome is present, its operable control MUST be named **New build** and MUST be a link to empty Build, not a posting form.
- **FR-005**: Ask's thread MUST present person / answer turns in the spine grammar, with citations in the evidence role.
- **FR-006**: Build's thread MUST present the person's intake text, then phase nodes in 047 order. Completed, current, waiting, and failed MUST be distinguishable without colour. Those four words are the person's labels; the 047 `data-phase` statuses they map to are `completed`, `active` (current), `pending` (waiting), and `failed`. The intake text MUST remain visible while the run runs, taken from the platform field in FR-013 — not invented in the template, and not replaced by a truncated list title.
- **FR-007**: The portal MUST fetch nothing from a third party at runtime — no CDN, no build step, offline-capable exactly as today. **Inter** (prose and controls) and **IBM Plex Mono** (evidence) MUST be self-hosted from the portal's own static assets and MUST carry ADR-0004 provenance (pinned version, digest, licence, provenance record). 034 FR-002 / FR-002a stand.
- **FR-008**: The palette MUST be defined once as named tokens and referenced everywhere; no page may introduce a colour of its own. 034 FR-003 stands.
- **FR-009**: Three type roles — prose, controls, evidence — MUST remain. Prose and controls use Inter; evidence uses IBM Plex Mono. 034 FR-001 stands; 034 FR-012's Palatino/Roboto assignment does not.
- **FR-010**: Saturated colour MUST be reserved for meaning: the chrome accent (mark, primary action, current conversational state), a product identity, or a verdict. Decorative use is out of bounds. 034 FR-004 as amended by the chrome-accent clarification.
- **FR-011**: A disposition or phase state MUST be distinguishable without colour, carrying a shape and a label as well as a hue. 034 FR-005 stands, extended to Build phase nodes.
- **FR-012**: Every existing accessibility criterion MUST still pass on the designed theme: the automated lane over every covered page state, and the keyboard and screen-reader rows. 034 FR-007 / FR-008 / FR-013 stand for the designed theme; 034 FR-011's obligation to ship a second theme does not.
- **FR-013**: No route may change and no behaviour may change, with exactly ONE stated payload exception: the run or result read the portal already performs gains an additive, read-only field carrying the Propose intake text 047 accepted, served from the transport-shared view so API / MCP / portal parity holds by construction (the same additive-payload shape as 029's window note, 033's ground note, and 034's definitions packs field). Templates MUST NOT invent that text. No other new payload. 034 FR-010's definitions field is already shipped; this feature does not add a second one there.
- **FR-014**: The templates' explanatory comments — which record *decisions* rather than describe markup — MUST survive the restyle. Where a comment's premise changes (for example, Ask as the only full-width surface), the comment changes with it rather than being deleted. 034 FR-009 stands.
- **FR-015**: Product identity colour (034 US2) MUST still appear only where the platform already knows the product; absence is not a reserved gap.
- **FR-016**: When this identity lands, assets that exist only to serve the superseded identity MUST be removed in the same change: unused faces and their provenance records, and styles or templates that nothing remaining references. A file that is no longer loaded is a defect. Approval mockups are not product artifacts and MUST NOT be added to the tree.

### Key Entities

- **Shell**: the shared landmarks of a signed-in conversational page — icon rail, work list, thread stage, composer. Ask and Build are two verbs on one shell.
- **Spine**: the thread treatment — a quoted human turn followed by ordered nodes. On Build the nodes are phases; on Ask they are answers.
- **Type role**: prose, control, or evidence. Every piece of content belongs to exactly one.
- **Design token**: a named colour or measure defined once, referenced everywhere.
- **Chrome accent**: the single warm identity colour of the shell, distinct from pack product colours.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A reviewer shown Ask and Build (empty and in-progress) without URLs identifies both as the same product and names the verb from the rail, the list heading, or the composer action — not from a wholly different layout.
- **SC-002**: On an in-flight Build, the intake text from the platform field is visible as the first turn and the 047 phase sequence is visible in the thread; zero of those phase names appear as Ask header chrome.
- **SC-003**: The composer is one row on every Ask and Build state that has one; it is centred; it is wider than the reading column; it is not flush to both stage edges.
- **SC-004**: Every page state the accessibility lane covers passes WCAG 2.2 AA automated checks on the designed theme — the same states, the same lane, no exclusions added for the withdrawn light theme.
- **SC-005**: All keyboard and screen-reader criteria still hold: focus drawn and unobscured, 24×24 targets, 320px reflow with no horizontal scrolling, text-spacing overrides clipping nothing.
- **SC-006**: Colour is never the sole carrier of meaning: phase state and dispositions remain identifiable in greyscale.
- **SC-007**: Every colour used on any page traces to a named token; a page-local colour is a defect a check can find.
- **SC-008**: The portal still serves with no build step and fetches nothing from a third party — a person can run it offline exactly as before.
- **SC-009**: Ask still cannot act: no control on an Ask route starts a Build or opens a pull request (047 P8 remains green).
- **SC-010**: After the restyle, no unused face, unused stylesheet, or unreferenced template from the superseded identity remains in the portal tree; a search for the withdrawn faces' files finds none.

## Assumptions

- The approved mockups (Ask/Build twins of the spine treatment, with the single-row centred composer) are the reference for chrome, type roles, and accent; where they and this spec differ in detail, this spec's requirements govern and the mockups illustrate. Steer copy on those mockups is not an operation this feature adds.
- 034 remains the governing spec for accessibility gates, tokens, no third-party fetch, type roles, and "no behaviour change." This spec supersedes 034 only on visual direction (faces, ground, accent), dual-theme obligation, and the conversational information architecture 047 did not restyle.
- 047 remains the governing spec for Propose/Build behaviour, phase names, and "no PR on failure." This spec changes how that progress is shown, not what it means. It does not add a steer-the-current-run path.
- Copy on the surfaces is unchanged except labels the new shell requires (list headings, composer verbs, never-acts status). Nav labels Build / Ask / Settings stand. The recorded-as-evidence footer remains.
- The mockup name used in design discussion is not a product name and does not appear in the portal.
- Operator run surface stays reachable and is not linked as a third primary verb in the icon rail.
