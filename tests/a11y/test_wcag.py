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
    page.goto(f"{portal_server.base}/ask")
    page.fill("#question", question)
    page.click("form.ask button[type=submit]")
    page.wait_for_load_state()


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
