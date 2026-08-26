# Feature Specification: Create home

**Feature Branch**: `spec/050-create-home`

**Created**: 2026-08-25

**Status**: Draft

**Input**: User description: Shift the signed-in portal layout to be similar to
Claude's interface. Instead of that product's logo, use the HashiCorp logo (the
maintainer has permission). Text beside the logo should be simple, like "Let's
Create". The composer is a rounded bubble: Enter starts work; while work is
running, a Stop control actually stops the running Ask or Build. A + control at
the bottom left of the bubble is a placeholder for attaching context. To its
right, a slider is Ask/Build rather than Chat/Cowork. History stays on the left
but is combined for Ask and Build, with a search field above it. No Home/Code
switcher. + New and Projects in the top left; Projects is a placeholder. User
profile at the bottom left, logout to its right using the existing sign-out
action. Iterate from that shell.

## Traceability *(mandatory)*

| Field | Value |
| --- | --- |
| **Requirements (R1–R17)** | **R12 (lean)** — presentation of existing Ask and Build; no new operated component, no client framework, no build step, no third-party fetch at runtime. **R15 (thin portal)** — the browser still only renders and relays; it does not orchestrate, choose models, or invent work. **R7 (fail-closed)** — Stop must use the platform's existing stop; a stop that cannot be completed must not look like the work ended. **R8 (Ask never acts)** — the Ask verb remains unable to start a Build or open a pull request |
| **ADRs touched** | **ADR-0034** (portal stays a thin client). **ADR-0039** (Ask never acts; the Ask/Build slider must keep that distinction visible). **ADR-0033** (no new transport; no new catalogue operation). **ADR-0004** (the HashiCorp mark is adopted content with provenance, not a redrawn lookalike). Consumes 012/028/034/035/047/048 for existing pages and stops; does not reopen their operations |
| **Evidence class** | **none** — presentation and existing stop; no new record |
| **Sealed core** | **None.** Chrome, stylesheet, self-hosted faces and mark. Combined history and search are of work the person can already see. Stop is the stop Ask and Build already have. No new route that is a new operation, no new payload, sealed core untouched |

## What is actually wrong

048 made Ask and Build one product with two layouts that still *feel* like two
products in a narrow rail: separate lists, verb switch in the rail, a one-row
composer, Build Stop in the header. People who use a modern assistant expect one
empty stage, one place to type, one history of their work, and a control in that
same bubble that stops whatever is running.

The maintainer named the reference: a dark, spacious empty home, a rounded
composer with the verb inside the bubble, a left column of past work with search,
New at the top, profile and sign-out at the bottom. That reference's Home/Code
switcher, model picker, microphone, and extra nav items are **not** this feature.

The HashiCorp mark replaces that reference's logo. The greeting is "Let's Create".
The slider is **Ask / Build**. Combined history is Ask conversations and Builds
together.

## Clarifications

### Session 2026-08-25

- Q: Now that the icon rail is gone, where does someone reach Settings? → A: **Settings sits with profile and logout at the bottom of the left column.** Not a third primary action next to New and Projects, and not address-only.
- Q: When someone opens an Ask or a Build from history, what happens to the Ask/Build slider? → A: **The slider stays visible, set to that item’s verb, and is not operable.** New returns to the empty home, where the slider works again. On an open item the summarized title sits at the top of the stage; the same rounded composer moves to the bottom centre. The HashiCorp mark and “Let's Create” are empty-home only.
- Q: On the empty create home, what should the old Ask and Build empty pages mean? → A: **They go away.** Empty home is one place. Ask versus Build is only the slider. A conversation or a run still has its own address so that item can be opened again; those are not a second empty home.
- Q: When you hit + New, should the slider stay on whatever you last used, or go back to Ask? → A: **The slider always defaults to Ask.** Empty home, sign-in, and + New all start on Ask. Build is a deliberate move of the slider on empty home. An open Build still shows Build locked.
- Q: Does the redesign keep the current colour schema? → A: **Yes. Nocturne is part of this redesign**, not leftover chrome. The new shell (column, greeting, bubble, slider, history) uses the shipped dark grounds, ink, muted text, violet accent, and semantic status colours. It MUST NOT adopt the reference screenshot’s orange, and MUST NOT bring back a second identity (048 copper as a competing palette).

Resolved earlier from the request and 048/047 constraints:



- **Empty home is one stage.** Signed-in with no open conversation or run, the
  person sees the mark, "Let's Create", and the composer. Ask versus Build is
  only the slider. There is not an empty Ask page and an empty Build page.
- **History is one list.** Ask conversations and Builds appear together, newest
  first, each row still obviously an Ask or a Build. Search filters that list by
  text the list already shows (title and any subtitle already on the row). It does
  not add a new platform search.
- **Stop lives in the bubble.** While Ask is answering or a Build is in flight,
  the bubble's primary action is Stop and it performs the stop that surface
  already has. It must actually halt that work, not only hide a spinner. When
  nothing is running, Enter (and the send control, if shown) starts the selected
  verb. Shift+Enter still writes a new line.
- **Placeholders do not pretend.** The + in the bubble (attach context) and
  **Projects** are visible and named, and they MUST NOT start work, attach files,
  or navigate as if those features exist.
- **048 composer geometry is superseded** for this shell: the composer is a
  rounded bubble with its controls on the inner bottom edge, not a single
  flush row of field-plus-chips. 048's accessibility, thin-client, and
  never-acts rules still govern. Colour is the shipped Nocturne schema (see
  Session Q).
- **No Home/Code switcher** in this feature.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Empty home is one place to create (Priority: P1)

A signed-in person who is not looking at a past item sees a quiet stage: the
HashiCorp mark, the words "Let's Create", and a large rounded composer. They
choose Ask or Build with a slider in the bubble, type, and press Enter. That
starts Ask or Build the way those verbs already work. They do not have to hunt
in a rail to find the other verb.

**Why this priority**: This is the new first impression. Everything else hangs
off this stage.

**Independent Test**: Sign in to an account with no item open. Confirm the
greeting and mark, the Ask/Build slider, and that submitting with Ask selected
asks (never acts) and submitting with Build selected starts a Build. A reviewer
who cannot read the address can still name the selected verb from the slider.

**Acceptance Scenarios**:

1. **Given** a signed-in person with no conversation or run open, **When** they
   look at the page, **Then** they see the HashiCorp mark, the text "Let's Create",
   and one rounded composer with the Ask/Build slider on Ask — not an empty Ask
   page and a different empty Build page.
2. **Given** that composer with Ask selected, **When** they submit a question,
   **Then** Ask runs as it does today and nothing starts a Build or a pull request.
3. **Given** that composer with Build selected, **When** they submit a Build
   request the platform already accepts, **Then** a Build starts as it does today.
4. **Given** the empty home, **When** they look for a Home/Code switcher or a
   model picker, **Then** those controls are absent.

---

### User Story 2 - The bubble starts work and can stop it (Priority: P1)

Enter starts the selected verb. While Ask is answering or a Build is running, the
same place in the bubble becomes Stop. Using Stop actually stops that work using
the platform's existing stop. A + control sits at the bottom left of the bubble
as a named placeholder for attaching context later.

**Why this priority**: A shell that cannot stop what it started is unsafe to
leave running. A + that looks like attach but silently does nothing must not
fake success.

**Independent Test**: Start an Ask; while it is answering, Stop ends it and the
person can tell it stopped. Start a Build; while it is in flight, Stop in the
bubble ends that run the same way today's Build stop does. Activate + and confirm
no attachment and no new work.

**Acceptance Scenarios**:

1. **Given** the composer idle, **When** the person presses Enter (not
   Shift+Enter), **Then** the selected verb starts.
2. **Given** Ask answering, **When** they use Stop in the bubble, **Then** that
   Ask stops through the existing Ask stop, and the page does not keep presenting
   it as in flight.
3. **Given** a Build in flight, **When** they use Stop in the bubble, **Then**
   that Build stops through the existing Build stop (not a new kind of stop), and
   the run is not still presented as running.
4. **Given** Stop cannot be completed, **When** the person has used it, **Then**
   the page does not claim the work ended.
5. **Given** the + control, **When** they activate it, **Then** nothing is
   attached, no file picker that would start work appears as success, and the
   control is presented as not available yet.

---

### User Story 3 - One history, searchable (Priority: P1)

The left column lists this person's Ask conversations and Builds together. A
search field above the list narrows it to rows whose already-visible text
matches. Choosing a row opens that Ask or that Build. **+ New** returns to the
empty create home. **Projects** is present and is a placeholder.

**Why this priority**: Combined history is what makes two verbs feel like one
product. Search that only works on one verb would undo it.

**Independent Test**: With at least one Ask and one Build in history, both appear
in one list. Search for a word that is only on one row and only that row remains.
New returns to the empty home. Projects does not open a projects product.

**Acceptance Scenarios**:

1. **Given** a person who has both an Ask conversation and a Build, **When** they
   look at the left column, **Then** both appear in one list, each row still
   identifiable as Ask or Build without opening it.
2. **Given** that list, **When** they type in search, **Then** only rows whose
   already-shown text matches remain; clearing search restores the list.
3. **Given** a row, **When** they open it, **Then** they see that Ask or that
   Build — not a merged thread. A summarized title for that item is at the top
   of the stage; the composer is at the bottom centre and looks the same as on
   empty home; the slider shows that item’s verb and cannot be changed. The
   HashiCorp mark and “Let's Create” are not on this page.
4. **Given** + New, **When** they activate it, **Then** they return to the empty
   create home (US1) without deleting history, and the slider is on Ask.
5. **Given** Projects, **When** they activate it, **Then** it does not navigate
   as if a projects feature exists and does not start work.

---

### User Story 4 - Profile and sign-out stay at the bottom of the column (Priority: P2)

The left column ends with this person's profile (the identity the portal already
shows), a named Settings control that opens the existing Settings page, and a
logout control that performs the existing sign-out. Settings and other
non-conversational pages keep the same visual identity; they are not a second
product.

**Why this priority**: The reference puts identity at the bottom. Losing sign-out
would trap a session.

**Independent Test**: Sign out from the new control ends the session the same
way today's sign-out does. Profile still names the signed-in person. Settings
from that bottom row opens the existing Settings page.

**Acceptance Scenarios**:

1. **Given** a signed-in person, **When** they look at the bottom of the left
   column, **Then** they see their existing profile presentation, a named
   Settings control, and a logout control.
2. **Given** that Settings control, **When** they use it, **Then** they open the
   existing Settings page — not a new settings product.
3. **Given** that logout control, **When** they use it, **Then** they are signed
   out through the existing sign-out and must sign in again to continue.
4. **Given** Settings, sign-out, login failure, or other existing non-chat pages,
   **When** they render, **Then** they inherit this identity rather than the
   previous rail-and-split chrome.

---

### User Story 5 - The identity still passes the accessibility gate (Priority: P1)

Every accessibility criterion the portal passes today it still passes afterwards,
on the designed dark theme.

**Why this priority**: Equal to US1. A prettier shell that fails WCAG is a
regression this platform would have to undo.

**Independent Test**: The dedicated accessibility lane runs unchanged and green
over every page state it covers today, on the designed theme.

**Acceptance Scenarios**:

1. **Given** every page state the lane covers, **When** it runs against the
   designed theme, **Then** it reports no violation at WCAG 2.2 AA.
2. **Given** the keyboard rows, **When** they run, **Then** the focus indicator is
   drawn and unobscured, every target meets 24×24, the page reflows at 320px with
   no horizontal scrolling, and text-spacing overrides clip nothing.
3. **Given** a screen reader on New, Projects, search, history rows, slider,
   Stop, +, profile, Settings, and logout, **When** they land on a control, **Then** they
   hear a name that matches the verb, not an unnamed graphic.

---

### Edge Cases

- Opening an Ask item keeps the slider visible, locked on Ask; submitting is a
  follow-up Ask, never a Build from that thread. The summarized conversation
  title is at the top of the stage; the composer sits at the bottom centre and
  looks the same as on empty home.
- Opening a Build item keeps the slider visible, locked on Build. The summarized
  run title is at the top of the stage; the composer sits at the bottom centre.
  The bubble does not start a second Build from that page (047/048: empty home
  remains the posting surface for a new Build; Stop is not a second propose).
- Empty home shows the HashiCorp mark and “Let's Create” with the composer in
  the stage. An open item MUST NOT repeat that greeting; the title replaces it.
- An empty history still shows the list region and search; it does not collapse
  into a different layout.
- Search with no matches says so and does not invent rows.
- A placeholder (+, Projects) that is activated MUST be presented as unavailable
  — not as a successful attach or a projects workspace.
- Long titles wrap; they MUST NOT force horizontal scrolling at 320px.
- Stop while already terminal is absent or inert; it MUST NOT look like a new
  stop succeeded.
- The operator run surface is not a third verb in this shell.
- Sign-out and skip-to-content remain present and operable.
- The HashiCorp mark MUST be the official mark adopted with provenance, not an
  invented star. The maintainer has permission to use it here. A missing mark
  MUST NOT fetch one from the public internet at runtime.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The signed-in empty state MUST be one create home: HashiCorp mark,
  the text "Let's Create", and one rounded composer in the stage. There MUST NOT
  be a separate empty Ask page and empty Build page. The slider is the only empty-home
  verb. The mark and greeting MUST NOT appear on an open Ask or Build.
- **FR-002**: The composer MUST be a rounded bubble. Controls sit on its inner
  bottom edge: + (placeholder) on the left, Ask/Build slider beside it, and the
  primary action on the right (send when idle, Stop when that verb is running).
  On empty home the bubble sits in the stage under the greeting. On an open Ask
  or Build it MUST sit at the bottom centre of the stage and MUST look the same.
- **FR-003**: The Ask/Build slider MUST be the verb for the next submit on the
  empty home and MUST be operable only there. Empty home, sign-in, and + New
  MUST present the slider on Ask. Build is selected only when the person moves
  the slider on empty home. On an open Ask or Build it MUST remain visible, show
  that item’s verb, and MUST NOT be operable. Ask selected MUST keep Ask unable
  to act (ADR-0039). The selected or locked verb MUST be obvious without colour
  alone.
- **FR-004**: Enter MUST start the selected verb. Shift+Enter MUST insert a line
  without starting work.
- **FR-005**: While Ask is answering, the bubble's primary action MUST be Stop
  and MUST perform the existing Ask stop. While a Build is in flight, that
  action MUST be Stop and MUST perform the existing Build stop. Stop MUST
  actually halt that work. If stop does not complete, the page MUST NOT present
  the work as ended.
- **FR-006**: The + control MUST be visible, named for attaching context, and
  MUST NOT attach files or start work in this feature.
- **FR-007**: The left column MUST list this person's Ask conversations and
  Builds in one newest-first list. Each row MUST remain identifiable as Ask or
  Build. Opening a row MUST open that existing item.
- **FR-008**: A search field above that list MUST filter rows by text already
  shown on the row. It MUST NOT add a new platform search or show work this
  person could not already list.
- **FR-009**: **+ New** MUST return to the empty create home without destroying
  history, with the slider on Ask. **Projects** MUST be visible, named, and MUST
  NOT behave as a projects product.
- **FR-010**: There MUST NOT be a Home/Code switcher, a model picker, or other
  controls from the visual reference that this feature did not name.
- **FR-011**: The bottom of the left column MUST present the existing profile
  identity, a named Settings control that opens the existing Settings page, and a
  logout control that performs the existing sign-out. Settings MUST NOT sit with
  New and Projects as a third primary action.
- **FR-012**: The portal MUST fetch nothing from a third party at runtime — no
  CDN, no build step. Faces remain Inter (prose and controls) and IBM Plex Mono
  (evidence), self-hosted with ADR-0004 provenance (048 FR-007). The HashiCorp
  mark MUST be self-hosted with ADR-0004 provenance (pinned source, digest,
  licence, provenance record).
- **FR-013**: The redesign MUST use the shipped **Nocturne** colour schema —
  dark grounds, primary and muted ink, violet accent, semantic status colours —
  on the new column, greeting, bubble, slider, and history. Three type roles,
  saturated colour only for meaning, and non-colour cues for state remain
  (034/048). Dark is the designed theme. A second palette (the reference
  screenshot’s orange, or 048 copper as a competing identity) is a defect.
- **FR-014**: No new catalogue operation and no new payload. Combined history and
  search are of lists the portal already loads. Stop is the stop already
  catalogued for Ask and for runs.
- **FR-015**: Opening a conversation or a run MUST still land on that item (so a
  person can return to it). Those item addresses are not a second empty home.
  An open item MUST show a summarized title for that Ask or Build at the top of
  the stage. Share, model picker, and other reference-only header chrome MUST
  NOT appear.
- **FR-016**: Every existing accessibility criterion MUST still pass on the
  designed theme (048 FR-012).
- **FR-017**: Templates' decision comments MUST survive (048 FR-014). Where a
  comment's premise changes (separate lists, icon rail as the only verb switch,
  one-row composer), the comment changes with it.
- **FR-018**: When this shell lands, chrome that exists only to serve the
  superseded rail-and-split empty layouts MUST be removed if nothing remaining
  loads it. The visual reference screenshot is not a product artifact and MUST
  NOT be added to the tree.

### Key Entities

- **Create home**: the signed-in empty stage — mark, greeting, composer — where
  the next Ask or Build is started.
- **Verb slider**: Ask or Build for the next submit on create home.
- **Combined history**: one list of this person's Ask conversations and Builds.
- **Placeholder control**: a named control (+, Projects) that must not succeed
  at a feature that does not exist.
- **HashiCorp mark**: the official logo adopted for this shell, with provenance.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A reviewer shown the signed-in empty home without an address bar
  names it as one create surface and can say whether Ask or Build is selected
  from the slider, not from two different page layouts. A reviewer shown an
  open item sees a title at the top and the same bubble at the bottom centre,
  not the empty-home greeting.
- **SC-002**: From that home, a first Ask still cannot start a Build or open a
  pull request; a first accepted Build still starts a Build.
- **SC-003**: While Ask is answering, Stop in the bubble ends that Ask. While a
  Build is in flight, Stop in the bubble ends that Build. After a successful
  stop, the page does not keep presenting that work as running.
- **SC-004**: With at least one Ask and one Build in history, both appear in one
  left-column list; search that matches only one row leaves only that row.
- **SC-005**: Activating + or Projects never attaches a file, never starts work,
  and never opens a projects workspace.
- **SC-006**: + New returns to the empty create home with the slider on Ask;
  logout signs the person out.
- **SC-007**: Every page state the accessibility lane covers still passes WCAG
  2.2 AA on the designed theme; 24×24 targets, 320px reflow with no horizontal
  scrolling, named controls for New, Projects, search, slider, Stop, +, profile,
  Settings, and logout.
- **SC-008**: Colour is never the sole carrier of the selected verb or of
  Ask-versus-Build in the list. Every colour on the new shell traces to the
  shipped Nocturne tokens; a page-local hex or the reference screenshot’s
  orange is a defect.
- **SC-009**: The portal still serves with no build step and fetches nothing
  from a third party — including the HashiCorp mark.
- **SC-010**: Ask still cannot act from this shell (047 P8 remains green).

## Assumptions

- The Claude interface screenshot is a layout reference only. Its product name,
  logo, orange accent, Home/Code switcher, model picker, microphone, Artifacts,
  Scheduled, Dispatch, Customize, and Design items are out of scope and MUST
  NOT appear. Colour comes from the shipped Nocturne schema.
- The HashiCorp mark is used with the maintainer's permission. Implementation
  adopts the official artwork with provenance; it does not redraw a "similar"
  star.
- Greeting copy is exactly **Let's Create** (straight apostrophe in prose is
  allowed to match existing portal punctuation rules).
- Combined-history search filters the rows already loaded for this person. It
  does not promise a full-text search of answer bodies the list does not show.
- Settings remains the existing Settings page. This shell reaches it from the
  bottom of the left column, with profile and logout — not from New/Projects,
  and not by address only.
- 047 remains the governing spec for Build behaviour, phases, and "no PR on
  failure." 048 remains the governing spec for thread spine, tokens, faces, and
  accessibility, except where this spec supersedes empty-home layout, composer
  geometry, verb switching, and list combination.
- Login without a named next page lands on this one empty create home with the
  slider on Ask. There is no empty Ask destination and no empty Build destination.
  + New also returns there with the slider on Ask.
- Operator run is unchanged in purpose and is not a primary verb here.
- Iteration after this slice may add attach-context and Projects as real
  features under later specs; this slice forbids fake success for either.
