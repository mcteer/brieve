# Feature Specification: The portal gets a visual identity

**Feature Branch**: `spec/034-portal-visual-identity`

**Created**: 2026-08-03

**Status**: Draft

**Input**: User description: "The portal gets a visual identity — HashiCorp's palette and precision carrying Claude's reading surface." Direction rendered and approved by the maintainer on 2026-08-03; the measured description is restated inline below.

## Traceability *(mandatory)*

| Field | Value |
| --- | --- |
| **Requirements (R1–R17)** | R12 (the portal is how a person meets the platform's evidence) |
| **ADRs touched** | ADR-0034 (the portal stays thin — presentation only, no logic moves here), ADR-0039 (the never-acts distinction stays *visible*, which is partly a design job), ADR-0033 (no surface parity change: this touches one transport's presentation, not its operations) |
| **Evidence class** | none — presentation carries no new evidence and changes no record |
| **Sealed core** | **None.** No Python behaviour, no payload, no route. Templates and one stylesheet. |

## The measured gap *(context)*

The portal is eight Jinja templates over a single hand-written **138-line** stylesheet with no
build step, no webfonts, and no design tokens: `system-ui` throughout, one blue `#0b4f9e`,
`#cbd3da` rules, `#14171a` ink. It is honest and entirely characterless — and two specific
things are lost in that flatness. **Nothing distinguishes an answer you read from a record hash
you carry to an auditor**, though those are the platform's two materials and a person uses them
completely differently. And **nothing says which product a conversation touched**, though the
platform knows: a pack is Vault's or Terraform's.

## Clarifications

### Session 2026-08-03

- Q: What visual direction? → A: **Approved from a rendered mockup**, not described in prose:
  HashiCorp's ramp (white ground, cool greys, near-black ink, black call-to-action, link blue
  darkened to clear AA) carrying Claude's reading surface underneath, expressed as **three type
  roles** rather than as colour. Saturated colour is scarce and always means something: a
  product or a verdict.
- Q: Serif for body prose, or headings only? → A: **Serif for headings; Roboto for body prose.**
  The mockup's serif body is narrowed to display use, and body text gets a named face rather
  than whatever `system-ui` resolves to — so the reading surface is the same on every machine
  instead of being San Francisco here and Segoe there.
- Q: Dark theme, and does the gate cover it? → A: **Both themes, and the accessibility lane
  extends to cover dark.** Nothing ships untested: the axe-core page states run twice, once per
  theme, rather than dark being an unverified surface in a repository whose posture is against
  exactly that.
- Q: Where can the product stripe actually appear? → A: **Where the platform already tells
  the page which definition acted** — the thread page's turns and composer. Measured: the
  thread LIST payload carries no product (a thread record is id, subject, tenant, created,
  title), and deriving one would mean joining every thread through its turns to a definition
  to its packs — API redesign, not presentation. The definitions payload gains ONE additive
  read-only field naming each definition's packs (the same additive-payload shape as 029's
  window note and 033's ground note; the view is transport-shared, so parity holds by
  construction), and the list's stripe is deferred until a thread carries its product.
- Q: Roboto is not a system face on macOS or Windows — how does the portal get it? → A:
  **Self-hosted, with the provenance discipline adopted content already gets.** A font stack
  naming Roboto would silently resolve to San Francisco on the maintainer's own machine, which
  is the approved design not landing while appearing to. So the file is vendored into the
  portal's static assets — no CDN, no build step, still offline-capable — and because that is
  third-party content entering the tree, it is pinned, digested and given a provenance record
  like every other adopted artifact here (ADR-0004's discipline, applied one file over).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A person can tell an argument from an identifier (Priority: P1)

Someone reads an answer and immediately sees which parts are prose to weigh and which parts are
identifiers to carry elsewhere — a record hash, a disposition, a timestamp — without anyone
explaining the difference. The two materials look like what they are.

**Why this priority**: This is the feature's whole reason. The portal's job is to make what the
platform did legible, and a page where an audit hash and a sentence share one typeface makes the
reader do work the design should have done.

**Independent Test**: Load a thread with every disposition and a guidance answer; confirm prose,
controls, and evidence each render in their own type role, and that a reader can point at "the
part I'd paste into a ticket" without being told.

**Acceptance Scenarios**:

1. **Given** an answer with claims and citations, **When** it renders, **Then** the claim text is
   set in the prose face and the citations and any record references are set in the evidence
   face, at a size and colour that reads as reference material rather than as body copy.
2. **Given** a thread turn carrying a disposition, **When** it renders, **Then** the disposition
   appears as a bordered label in the evidence face — legible in greyscale, so colour is not the
   only thing carrying it.
3. **Given** any page, **When** a control is rendered (button, nav link, form label), **Then** it
   is set in the control face, so what is operable looks different from what is read.

---

### User Story 2 - The page says which product it is about (Priority: P2)

A person scanning their conversations sees at a glance which touched Vault and which touched
Terraform, because the platform already knows and the page now says so.

**Why this priority**: Real orientation for anyone with more than a handful of conversations, and
cheap — but the page is usable without it, which is why it follows US1.

**Independent Test**: Render a thread whose turns span agents of both packs; the product is
identifiable per turn without reading the agent names, and a turn whose definition declares no
pack renders with no stripe and no gap where one should be.

**Acceptance Scenarios**:

1. **Given** a turn run by a definition whose pack is known, **When** the thread renders,
   **Then** that pack's identity colour appears as a rule against the turn, and the composer's
   agent picker shows the same identity beside each startable definition.
2. **Given** a turn whose definition declares no pack, **When** the thread renders, **Then** the
   turn renders cleanly with no colour and no reserved empty space — absence is not a visual
   defect.
3. **Given** a person who cannot distinguish those colours, **When** they read the turn, **Then**
   nothing is lost: the colour is redundant with the agent name that is already there.
4. **Given** the thread LIST, **When** it renders, **Then** it carries no product colour at all —
   deferred, recorded rather than approximated, because the list's payload does not know the
   product and a stripe derived from a name heuristic would be the platform pretending to know.

---

### User Story 3 - The identity survives the accessibility gate unchanged (Priority: P1)

Every criterion the portal passes today it still passes afterwards — automated and human — and
the restyle is judged on that as much as on how it looks.

**Why this priority**: Equal to US1. A prettier portal that loses a WCAG criterion is a
regression this platform would have to undo, and the gate is a merge blocker rather than a report.

**Independent Test**: The dedicated accessibility lane runs unchanged and green: axe-core over
every page state, plus the keyboard and screen-reader rows.

**Acceptance Scenarios**:

1. **Given** every page state the lane covers, **When** it runs, **Then** axe-core reports no
   violation at WCAG 2.2 AA.
2. **Given** the keyboard rows, **When** they run, **Then** the focus indicator is drawn and
   unobscured, every target meets 24×24, the page reflows at 320px with no horizontal scrolling,
   and text-spacing overrides clip nothing.
3. **Given** the narrowest supported width, **When** the header renders, **Then** it wraps rather
   than overflowing — the behaviour 028 established after CI's Linux rendering broke first.

---

### Edge Cases

- A page in a state the mockup never showed (a refusal page, a failed login, a delete
  confirmation) must inherit the identity rather than fall back to unstyled defaults.
- Long unbroken strings — a record hash, a correlation id — must not force horizontal scrolling
  at 320px; the evidence face makes them more prominent, so this gets worse before it gets better.
- A person with a text-spacing override or a large default font size must still get a usable page:
  the type scale is relative, not fixed.
- A reader with no serif available (an unusual system) must get a sane fallback rather than a
  face that breaks the reading measure.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The portal MUST render three distinct type roles — prose, controls, evidence — and
  each class of content MUST use its own role consistently across every page.
- **FR-002**: The portal MUST fetch nothing from a third party at runtime — no CDN, no build
  step, offline-capable exactly as today. Faces that a mainstream system already has are used
  from a stack; a face that is NOT universally present (Roboto) is **self-hosted from the
  portal's own static assets** rather than referenced and allowed to fall back silently.
- **FR-002a**: A self-hosted face is adopted third-party content and MUST carry the provenance
  this repository requires of it: a pinned upstream version, a content digest verified where the
  loader can verify it, a recorded licence, and a provenance document naming what was taken and
  when. A font is not exempt from ADR-0004's discipline for being a font.
- **FR-003**: The palette MUST be defined once as named tokens and referenced everywhere;
  no page may introduce a colour of its own.
- **FR-004**: Saturated colour MUST be reserved for meaning — a product identity or a verdict.
  Decorative use of the accent is out of bounds.
- **FR-005**: A disposition MUST be distinguishable without colour, carrying a shape and a label
  as well as a hue.
- **FR-006**: A conversation whose product the platform knows MUST show that product's identity
  colour; one whose product is unknown MUST render with no placeholder and no reserved space.
- **FR-007**: Every existing accessibility criterion MUST still pass: the automated lane over
  every covered page state, and the keyboard and screen-reader rows.
- **FR-008**: Link and body colours MUST meet WCAG AA contrast on their own backgrounds; a
  brighter brand tone may be used only where contrast rules do not bind (focus rings, borders).
- **FR-009**: The templates' explanatory comments — which record *decisions* rather than describe
  markup — MUST survive the restyle. Where a comment's premise changes, the comment changes with
  it rather than being deleted.
- **FR-010**: No route may change and no behaviour may change, with exactly ONE stated payload
  exception: the definitions listing gains an additive, read-only field naming each definition's
  packs — the same additive shape as the window note (029) and the ground note (033), served
  from the transport-shared view so parity holds by construction. Everything else is
  presentation: templates and the stylesheet.
- **FR-011**: The portal MUST offer a light and a dark theme, following the reader's system
  preference, and the accessibility lane MUST cover BOTH — every page state it checks today is
  checked in each theme. A theme that ships unverified is the shape this repository refuses.
- **FR-012**: The prose face is used for **headings**; **body prose is set in Roboto**. Controls
  keep the control face and evidence keeps the evidence face, so the three roles survive — what
  narrows is the serif's reach.
- **FR-013**: Both themes MUST meet WCAG AA contrast independently. The dark theme is designed
  rather than inverted: the accent that clears AA on white is not the accent that clears it on
  near-black.

### Key Entities

- **Type role**: one of three — prose (arguments a person reads), control (things a person
  operates), evidence (identifiers a person carries elsewhere). Every piece of content belongs to
  exactly one.
- **Design token**: a named colour or measure defined once, referenced everywhere; the thing that
  makes "no page introduces its own colour" checkable rather than aspirational.
- **Product identity**: the colour standing for a pack, applied only where the platform genuinely
  knows the product.
- **Verdict**: a disposition — answered, declined, refused — carried by shape and label as well as
  colour.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every page state the accessibility lane covers passes WCAG 2.2 AA automated checks
  after the restyle — the same states, the same lane, no exclusions added.
- **SC-002**: All keyboard and screen-reader criteria still hold: focus drawn and unobscured,
  24×24 targets, 320px reflow with no horizontal scrolling, text-spacing overrides clipping
  nothing.
- **SC-003**: Colour is never the sole carrier of meaning: every disposition remains identifiable
  in greyscale, verified by rendering without colour.
- **SC-004**: Every colour used on any page traces to a named token; a page-local colour is a
  defect a check can find.
- **SC-005**: A reader can distinguish prose, control, and evidence content on any page by
  appearance alone, with no legend.
- **SC-006**: The portal still serves with no build step and fetches nothing from a third party —
  a person can run it offline exactly as before.

## Assumptions

- The approved mockup is the reference for palette and type roles; where it and this spec differ
  in detail, the spec's requirements govern and the mockup illustrates.
- "System font stack" means the faces a mainstream OS already has; a system without the preferred
  serif falls back within the stack rather than to an arbitrary default.
- The portal's information architecture and copy are unchanged — this feature restyles what is
  there. Any copy edit is limited to what the new type roles require (for example, a label that
  only worked because everything looked the same).
- Product identity colours are the vendor's published product colours, used as identity rather
  than as decoration.
