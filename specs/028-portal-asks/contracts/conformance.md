<!-- SPDX-License-Identifier: Apache-2.0 -->
# Conformance contract: 028 — the portal learns to ask

---

## Who runs these rows

| Group | Where | Needs | Status |
| --- | --- | --- | --- |
| The four shapes, patience, token relay, no-classification | `tests/component/test_portal_asks.py` | Nothing | **In force** — 13 rows |
| Containment (egress, catalogued-operations, no credential, client size) | `tests/conformance/portal/test_containment.py` | Nothing | **In force** — 10 rows; the scripted session now drives the ask, so the newest page is inside the claim |
| WCAG 2.2 AA + keyboard, for form / answered (both sources) / declined / refused | `tests/a11y/` | The browser lane CI already runs | **In force** — 27 rows green |
| **A person asks through the deployed portal and reads a cited answer (SC-001)** | Browser, deployed portal | The enclave, `ASK_MODEL`, the credential, a qualified cell — all standing as of 2026-08-02 | **Owed — named runner: Dan McTeer** |

No sealed core is touched and no constitution text moves: **no Principle V review and no
security-maintainer review arises** — the first feature in five for which that sentence is true.

---

## What these rows assert

**The four outcomes are four pages, and refusals are the API's words (FR-009, FR-010, SC-003).**
Component rows drive the portal with an injected transport returning each shape and assert:
unreachable renders as "could not be asked"; a 403 and two distinct 503 refusals render their
`detail` prose verbatim and therefore differ exactly as the API's sentences differ; a decline
renders as an answer naming its source. **A row asserts the portal added no classification**: the
refusal block contains the transported `detail` string and no portal-authored cause vocabulary.

**Guidance citations are links; estate references are not (FR-006, FR-007, SC-002).** An answered
guidance response renders each citation as an anchor with the citation URL; an answered estate
response renders each reference with the full hash present and **zero** anchors pointing at it.

**The ask waits longer and nothing else does (FR-004, SC-004).** The transport records the timeout
each call carried: `/ask` carries the ask patience; a `/threads` call made in the same session
carries the default. The second assertion is the one that keeps this a design rather than a raised
number.

**The relay sends the person's own token (FR-011, portal half).** The transport asserts the
`Authorization` value is the signed-in session's token — not a portal credential, of which the
containment rows separately assert there are none.

**A signed-out ask never reaches the API.** GET redirects to login; POST redirects to login; the
transport observes zero calls. The trail half of that property — a *refused* ask still records —
is the API's, already in force (027's rows), and is observed end-to-end at the demonstration.

**The form refuses an empty question without a relay call** — the cheapest refusal in the feature,
and the transport observes it costs zero API traffic.

**Accessibility**: the form (with its expectation text), an answered page of each source, a
declined page and a refused page each pass WCAG 2.2 AA and the keyboard row. The expectation text
is plain page content — perceivable without a spinner, a live region, or any client machinery.

---

## What these rows refuse to assert

**They do not assert the answer is good.** Answer quality is the eval lane's (the cell was earned
2026-08-02); the portal renders what came back.

**They do not assert the API records the ask** — 027's rows already do, and a portal row
re-asserting it would be a second copy that drifts. What the portal rows assert is the portal's
half: the person's own token made the call.

**They do not assert `refused.html`'s wording for act-shaped operations.** That template and its
callers are out of scope; only the ask page carries the verbatim-detail discipline.

**They do not assert any waiting mechanism beyond patience** — no polling, no streaming, no
in-flight state. The spec records submit-then-poll as the next shape, owed to a future feature
that changes the API deliberately.

---

## The row that would catch this feature's own tempting wrong fix

**No-classification.** The obvious "improvement" is a friendly mapping — `credential_unavailable`
becomes a portal-authored paragraph about credentials. It would look better in review and drift
from the API's vocabulary the first time a reason code was added or reworded, leaving the page
confidently explaining the wrong cause. The row pins the refusal block to the transported
`detail` string so that fix fails a gate instead of shipping.

---

## What implementation changed about this contract

**Two a11y failures from one three-line nav addition**, and the second is the more instructive.

**The minimum target size, found by the lane rather than by review.** The new navigation links
rendered at their text height, 18px, and WCAG 2.2's 24px minimum target applies to them. The
keyboard row caught it on the first run of the ask page. Fixed in the stylesheet (vertical padding
and an explicit `min-height`) rather than by exempting the nav, because the rule is about whether
a person with imprecise pointing can hit the link, and the nav is on every page.

**Reflow at 320px — which passed locally and failed in CI.** The header could not wrap, so adding
the nav pushed it past a 320px viewport and the page scrolled sideways. macOS renders the same
strings narrower than CI's Linux Chromium, so a local run said green and the gate said 340 > 320.
Fixed by letting the header wrap rather than by shrinking the text: at 320px it becomes two lines
and nothing is lost. **The lesson is about where a browser gate has to run**, not about CSS — a
rendering property measured on one platform is a property of that platform, and this repository
now has an instance where the difference was the whole verdict.

Worth recording because it is the second time this feature's own gates found something a reading
would not: the analysis pass caught the containment session excluding the new page, and the a11y
lane caught the nav. Both were additions that looked complete and were not.

**Two rows added beyond the plan**, both pinning properties the design has by construction and
nothing asserted:

- **The question travels in the body, never a URL.** A question in a query string is a question
  in every access log, proxy log and browser history — none of them the append-only trail the
  platform governs, all of them outliving it. The API keeps the question out of the record; a URL
  on the way there would undo that outside the platform's reach. The tempting change is making an
  answer bookmarkable by moving the ask to GET, and this row makes that an argument somebody has
  to win rather than a convenience they add.
- **A hostile refusal sentence renders as text.** Verbatim means the *sentence*, not the *markup*.
  The template escapes; the row asserts it, because the feature rests on passing a string through
  untouched and "untouched" is precisely the word that invites a `| safe` filter later.
