# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — WCAG 2.2 AA over every page state the portal can render.

FR-020a. One row per state, rather than one row over a crawl, so a failure names the page
as well as the criterion — "the thread page fails colour contrast" is actionable; "the
portal fails colour contrast" is a search.

**What this gate does not assert is recorded, not implied.** The criteria automation cannot
reach — focus order *adequacy*, screen-reader flow, alternative-text meaningfulness — are
enumerated in `specs/012-conversational-portal/contracts/conformance-portal.md` with a
named human runner. A green run here is not a conformance claim, and the last row in this
file says so out loud rather than leaving it to whoever reads the exit status.
"""

from __future__ import annotations

import pathlib
from typing import Any

from core.audit.schema import AuditEventType
from tests.a11y.conftest import AXE_TAGS, PortalServer, audit, describe


def _thread_with_all_dispositions(page: Any, server: PortalServer) -> str:
    """A thread showing dispatched, declined, and scope-refused turns.

    The richest page the portal renders, and therefore the one most likely to carry a
    contrast or landmark problem that the empty states do not.
    """
    page.goto(f"{server.base}/")
    page.click("form[action='/threads'] button[type=submit]")
    page.wait_for_load_state()
    thread_url = page.url

    # Re-navigate between sends rather than clicking twice on a page that navigated
    # underneath the first click. Each submit is a full round trip — the portal is a thin
    # client, so every state change is a new document, and a locator held across one is
    # stale by construction.
    _send(page, thread_url, "plan the migration", agent="planner")
    _send(page, thread_url, "what else can you do?")

    return str(thread_url)


def _send(page: Any, thread_url: str, message: str, *, agent: str = "") -> None:
    page.goto(thread_url)
    page.fill("#message", message)
    if agent:
        page.select_option("#agent", agent)
    page.click(".composer button[type=submit]")
    page.wait_for_load_state()


def test_the_signed_out_page_meets_wcag_22_aa(
    anonymous_page: Any, portal_server: PortalServer
) -> None:
    anonymous_page.goto(f"{portal_server.base}/")
    violations = audit(anonymous_page)
    assert violations == [], describe(violations)


def test_the_empty_thread_list_meets_wcag_22_aa(page: Any, portal_server: PortalServer) -> None:
    """The empty state is a real state, and the one a new person sees first."""
    page.goto(f"{portal_server.base}/")
    violations = audit(page)
    assert violations == [], describe(violations)


def test_the_populated_thread_list_meets_wcag_22_aa(page: Any, portal_server: PortalServer) -> None:
    page.goto(f"{portal_server.base}/")
    page.click("form[action='/threads'] button[type=submit]")
    page.wait_for_load_state()
    page.goto(f"{portal_server.base}/")
    violations = audit(page)
    assert violations == [], describe(violations)


def test_a_thread_with_every_disposition_meets_wcag_22_aa(
    page: Any, portal_server: PortalServer
) -> None:
    _thread_with_all_dispositions(page, portal_server)
    violations = audit(page)
    assert violations == [], describe(violations)


def test_the_delete_confirmation_meets_wcag_22_aa(page: Any, portal_server: PortalServer) -> None:
    thread_url = _thread_with_all_dispositions(page, portal_server)
    page.goto(f"{thread_url}/delete")
    violations = audit(page)
    assert violations == [], describe(violations)


def _ask(page: Any, portal_server: PortalServer, question: str) -> None:
    """Ask, and wait for the answer to ARRIVE rather than for a page to load.

    The form no longer navigates — it posts in place and APPENDS the server-rendered exchange
    to the transcript (035), so `wait_for_load_state` returns instantly on a page that is
    already loaded and the audit would run against an empty transcript. Waiting on the outcome
    itself is both correct for the enhanced form and correct if the script is ever removed,
    since a full page load produces the same element.
    """
    page.goto(f"{portal_server.base}/ask")
    page.fill("#question", question)
    page.click("form.ask button[type=submit]")
    page.wait_for_selector("#ask-transcript section.answer", timeout=30_000)


def test_the_ask_form_meets_wcag_22_aa(page: Any, portal_server: PortalServer) -> None:
    """028. The empty form, including the expectation text a person reads before waiting.

    That text is plain page content rather than a spinner or a live region, which is what makes
    it perceivable here at all — an announcement nobody can audit is not an affordance.
    """
    page.goto(f"{portal_server.base}/ask")
    violations = audit(page)
    assert violations == [], describe(violations)


def test_a_guidance_answer_meets_wcag_22_aa(page: Any, portal_server: PortalServer) -> None:
    """The state a person actually reads: claims with followable citations."""
    _ask(page, portal_server, "How does an AI agent obtain an identity with Vault?")
    violations = audit(page)
    assert violations == [], describe(violations)


def test_an_estate_answer_meets_wcag_22_aa(page: Any, portal_server: PortalServer) -> None:
    """The other answered shape — references rendered as identifiers rather than links.

    Audited separately from guidance because it renders different markup: inert `code` elements
    where the guidance page has anchors, and a11y failures live in exactly that difference.

    029 adds the window note to this state when a read was bounded. It is plain page content in
    the same register as the source line, so it is perceivable without a live region — which is
    the property that makes "the answer says it was a window" reach a screen-reader user at all.
    """
    portal_server.surface.audit.append_event(
        correlation_id="a11y-estate-run",
        tenant_id="tenant-test",
        event_type=AuditEventType.RUN_START,
        payload={"subject_user_id": "alice"},
    )
    _ask(page, portal_server, "Which runs were denied?")
    violations = audit(page)
    assert violations == [], describe(violations)


def test_a_declined_ask_meets_wcag_22_aa(page: Any, portal_server: PortalServer) -> None:
    """A decline is an answer, and it gets audited as one."""
    _ask(page, portal_server, "What is the capital of France?")
    violations = audit(page)
    assert violations == [], describe(violations)


def test_a_refused_ask_meets_wcag_22_aa(page: Any, portal_server: PortalServer) -> None:
    """The refusal page carries the platform's own sentence, and it must still be readable.

    Rendered by asking with an empty question, which the form refuses before any relay call —
    the one refusal state reachable without disturbing the session-scoped surface's wiring.
    """
    page.goto(f"{portal_server.base}/ask")
    page.eval_on_selector("#question", "el => el.removeAttribute('required')")
    page.click("form.ask button[type=submit]")
    page.wait_for_load_state()
    violations = audit(page)
    assert violations == [], describe(violations)


def test_the_ask_form_labels_its_control(page: Any, portal_server: PortalServer) -> None:
    """The same association the composer row protects, for the new field.

    Axe checks a label exists; this checks it points at the question box, because a label
    pointing at the wrong control is worse than none.
    """
    page.goto(f"{portal_server.base}/ask")
    label = page.get_attribute("label[for=question]", "for")
    assert label == "question", "the ask form's label does not point at the question box"
    described = page.get_attribute("#question", "aria-describedby")
    assert described == "ask-expectation", (
        "the question box is not described by the expectation text, so a screen-reader user is "
        "not told an answer takes a while before they wait for one"
    )


def test_the_composer_labels_its_controls(page: Any, portal_server: PortalServer) -> None:
    """Beyond the ruleset: the association a screen-reader user depends on.

    Axe checks that a label exists. This checks it points at the right control — a label
    associated with the wrong input is worse than none, because assistive technology
    announces it confidently.
    """
    page.goto(f"{portal_server.base}/")
    page.click("form[action='/threads'] button[type=submit]")
    page.wait_for_load_state()

    assert page.get_attribute("label[for='message']", "for") == "message"
    assert page.get_attribute("#message", "id") == "message"
    assert page.get_attribute("label[for='agent']", "for") == "agent"
    # The recorded-as-evidence notice must be announced with the field, not merely near it.
    assert page.get_attribute("#message", "aria-describedby") == "recorded-note"
    assert page.get_attribute("#recorded-note", "id") == "recorded-note"


def test_the_skip_link_is_the_first_focusable_element(
    page: Any, portal_server: PortalServer
) -> None:
    """A keyboard user should not tab through the header to reach the conversation."""
    page.goto(f"{portal_server.base}/")
    page.keyboard.press("Tab")
    focused = page.evaluate("document.activeElement.className")
    assert "skip" in focused, f"the first tab stop was {focused!r}, not the skip link"


def test_the_contract_records_what_these_gates_do_and_do_not_cover() -> None:
    """The boundary, kept visible in the same place as the result.

    This row used to assert the contract named a human runner for criteria automation
    "could not" reach. It now asserts the opposite: that those criteria are covered by
    `test_keyboard_and_screenreader.py`, and that the two things genuinely outside a
    browser's reach — whether the words are good, and how a specific screen reader behaves
    — are still written down. A gate that stopped saying what it does not cover would be
    the more dangerous kind of green.
    """
    import pathlib

    contract = (
        pathlib.Path(__file__).resolve().parents[2]
        / "specs/012-conversational-portal/contracts/conformance-portal.md"
    )
    text = contract.read_text()

    for criterion in (
        "2.4.3 Focus Order",
        "1.1.1 Non-text Content",
        "2.4.13 Focus Appearance",
        "2.5.8 Target Size",
        "1.4.10 Reflow",
    ):
        assert criterion in text, f"the contract no longer records how {criterion!r} is covered"

    assert "What is still not automated" in text
    assert "specific screen reader" in text
    assert "No named runner is owed" in text, (
        "the contract still claims a manual pass is outstanding; it is not"
    )
    assert AXE_TAGS[-1] == "wcag22aa"


# ────────────────────────────────────────── the ask as a conversation (035)


def _conversation(page: Any, portal_server: PortalServer, *questions: str) -> str:
    """Hold a conversation and return its id, so a row can reopen or delete it."""
    _ask(page, portal_server, questions[0])
    for index, question in enumerate(questions[1:], start=2):
        page.fill("#question", question)
        page.click("form.ask button[type=submit]")
        # Wait for THIS answer, not the last one — the count grows by one per exchange, and
        # waiting on the total made every intermediate step time out.
        page.wait_for_function(
            "n => document.querySelectorAll('#ask-transcript section.answer').length >= n",
            arg=index,
            timeout=30_000,
        )
    return str(page.url.rstrip("/").rsplit("/", 1)[-1])


def test_a_transcript_of_several_exchanges_meets_wcag_22_aa(
    page: Any, portal_server: PortalServer
) -> None:
    """The state this feature exists to create, and the one nothing audited before.

    A page that grew from one answer to several is a different page: more headings, more
    landmarks, a longer focus order, and a composer that has moved down the document.
    """
    _conversation(
        page,
        portal_server,
        "How does an AI agent obtain an identity with Vault?",
        "what about multi-region?",
        "and disaster recovery?",
    )

    violations = audit(page)
    assert violations == [], describe(violations)


def test_the_conversation_rail_meets_wcag_22_aa(page: Any, portal_server: PortalServer) -> None:
    """A second navigation landmark on a page that already had one."""
    _ask(page, portal_server, "How does an AI agent obtain an identity with Vault?")
    page.goto(f"{portal_server.base}/ask")
    page.wait_for_selector("nav.app-rail", timeout=10_000)

    violations = audit(page)
    assert violations == [], describe(violations)


def test_the_composer_never_obscures_what_focus_is_on(
    page: Any, portal_server: PortalServer
) -> None:
    """2.4.11 — THE NAMED TRAP, and the reason it was named in the plan before it was built.

    A sticky composer is exactly the overlay that hid a focused element in 034, and the page
    scrolls rather than a box inside it — which is how every chat interface behaves and what
    the first attempt gave up to make this easy.

    **Focus is moved by pressing Tab, not by calling `.focus()`.** That is the difference the
    first version of this row missed: `.focus()` does not scroll, so an element behind the
    composer stayed behind it and the row failed a layout that a keyboard user would never
    have had trouble with. Sequential focus navigation is what makes the browser scroll, and
    `scroll-margin-block-end` is what makes it land clear.
    """
    _conversation(
        page,
        portal_server,
        "How does an AI agent obtain an identity with Vault?",
        "what about multi-region?",
        "and disaster recovery?",
    )

    links = page.locator("#ask-transcript a")
    assert links.count() > 0, "no citation to focus; this row would pass vacuously"

    # Walk focus with Tab until it lands on the last citation, the way a person would.
    target = links.nth(links.count() - 1)
    target.evaluate("el => el.previousElementSibling && el.previousElementSibling.focus()")
    page.keyboard.press("Tab")
    for _ in range(200):
        if target.evaluate("el => el === document.activeElement"):
            break
        page.keyboard.press("Tab")
    assert target.evaluate("el => el === document.activeElement"), (
        "could not reach the last citation by keyboard"
    )

    box = target.bounding_box()
    composer = page.locator("form.ask").bounding_box()
    assert box is not None and composer is not None
    assert box["y"] + box["height"] <= composer["y"] + 1, (
        f"the focused element sits under the sticky composer: element ends at "
        f"{box['y'] + box['height']}, composer starts at {composer['y']}"
    )


def test_the_page_scrolls_rather_than_a_box_inside_it() -> None:
    """035, after the maintainer said so: answers do not arrive in a scrolling window.

    A nested scroll region satisfied 2.4.11 the easy way and read wrong — it is not what
    Claude or ChatGPT do, and it is not what anybody expects of a chat. Asserted on the
    stylesheet rather than in a browser, because the property is "this element does not own a
    scroll" and a browser can only show that it currently has nothing to scroll.
    """
    css = (
        pathlib.Path(__file__).resolve().parents[2] / "src/surfaces/portal/static/portal.css"
    ).read_text()
    rule = css.split(".transcript {", 1)[1].split("}", 1)[0]

    assert "overflow-y: auto" not in rule and "overflow: auto" not in rule, (
        "the transcript owns a scroll region again — the page is what scrolls"
    )
    assert "padding-block-end" in rule, (
        "no room reserved for the composer, so the last answer cannot be scrolled clear of it"
    )


def test_a_long_transcript_still_reflows_at_320px(page: Any, portal_server: PortalServer) -> None:
    """1.4.10 with the rail present — 028's lesson, one layout later.

    The rail collapses rather than narrowing, because a second column at 320px takes the
    transcript past the horizontal-scroll line with it.
    """
    _conversation(
        page,
        portal_server,
        "How does an AI agent obtain an identity with Vault?",
        "what about multi-region?",
    )
    page.set_viewport_size({"width": 320, "height": 800})
    page.goto(f"{portal_server.base}/ask")
    page.wait_for_selector("form.ask", timeout=10_000)

    overflow = page.evaluate(
        "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    assert overflow <= 0, f"the page scrolls horizontally at 320px by {overflow}px"
    assert audit(page) == [], "the collapsed layout fails the ruleset"


def test_the_conversation_delete_confirmation_meets_wcag_22_aa(
    page: Any, portal_server: PortalServer
) -> None:
    """A destructive page, and the one that has to say what deleting does not do."""
    _ask(page, portal_server, "How does an AI agent obtain an identity with Vault?")
    page.goto(f"{portal_server.base}/ask")
    page.click("nav.app-rail li a")
    page.wait_for_selector("form.ask", timeout=10_000)
    conversation_id = page.url.rstrip("/").rsplit("/", 1)[-1]
    page.goto(f"{portal_server.base}/ask/{conversation_id}/delete")
    page.wait_for_selector("form", timeout=10_000)

    violations = audit(page)
    assert violations == [], describe(violations)
    assert "does not remove" in page.inner_text("body"), (
        "the confirmation does not say that deleting leaves the platform's record intact"
    )


def test_enter_sends_and_shift_enter_writes_a_line(page: Any, portal_server: PortalServer) -> None:
    """035, after the maintainer said so. What every chat interface does.

    A textarea's default is the opposite, so this is behaviour the page adds — and adding it
    means the other half has to keep working, because somebody pasting a multi-line question
    must not have it sent on the first newline.
    """
    page.goto(f"{portal_server.base}/ask")
    page.click("#question")

    # SHIFT+ENTER writes a line and sends nothing.
    page.keyboard.type("first line")
    page.keyboard.press("Shift+Enter")
    page.keyboard.type("second line")
    assert "\n" in page.input_value("#question"), "Shift+Enter did not write a new line"
    assert page.locator("#ask-transcript section.answer").count() == 0, (
        "Shift+Enter sent the question"
    )

    # ENTER sends it.
    page.keyboard.press("Enter")
    page.wait_for_selector("#ask-transcript section.answer", timeout=30_000)
    assert page.locator("#ask-transcript section.answer").count() == 1


def test_enter_on_an_empty_box_sends_nothing(page: Any, portal_server: PortalServer) -> None:
    """The browser's own `required` still speaks first — `requestSubmit` honours it, which is
    why it is used rather than `submit()`."""
    page.goto(f"{portal_server.base}/ask")
    page.click("#question")
    page.keyboard.press("Enter")

    page.wait_for_timeout(1500)
    assert page.locator("#ask-transcript section.answer").count() == 0, "an empty question was sent"
