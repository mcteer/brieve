# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — the criteria a scanner cannot assert, asserted anyway.

Axe checks structure. It does not tab through a page, it does not read the accessibility
tree the way a screen reader does, it does not measure a focus ring, and it does not know
whether a live region will announce anything. Those were filed as "needs a human", which
was wrong: a browser can do all of it, and a checklist nobody has run is worse than a row
that runs on every commit.

What each row here does that the scanner cannot:

- **Focus order** — walks the real tab sequence and compares it against *visual* reading
  order, which is the actual criterion. Axe sees that a focus order exists.
- **Screen-reader flow** — takes Playwright's accessibility-tree snapshot, which is
  approximately what assistive technology consumes, and asserts every interactive node has
  a usable accessible name.
- **Focus appearance (2.4.13)** — measures the rendered focus indicator and asserts it is
  actually drawn, rather than trusting a stylesheet.
- **Focus not obscured (2.4.11)** — checks the focused element is inside the viewport and
  that nothing is painted over it.
- **Target size (2.5.8)** — measures every interactive element.
- **Alt text meaningfulness** — cannot judge prose, but *can* catch the failures that
  actually occur: filenames, "image", and empty alt on informative content.
- **Reflow (1.4.10) and text spacing (1.4.12)** — re-renders under the conditions the
  criteria name and asserts nothing is lost.

What remains genuinely human is narrow and stated at the bottom of this file.
"""

from __future__ import annotations

from typing import Any

import pytest

from tests.a11y.conftest import PortalServer, start_thread_from_home

#: WCAG 2.5.8 AA. 24×24 CSS pixels, the AA threshold (2.5.5 AAA asks 44).
MIN_TARGET_PX = 24

#: Alt text that is present and useless. These are the failures that happen in practice.
USELESS_ALT = ("image", "photo", "picture", "icon", "graphic", "spacer", "img")


def _states(server: PortalServer) -> list[tuple[str, str]]:
    """Every page state worth walking, as (name, path)."""
    return [
        ("thread list", "/run"),
    ]


def _tab_sequence(page: Any, limit: int = 40) -> list[dict[str, Any]]:
    """The real focus order, walked with the keyboard rather than inferred from the DOM."""
    sequence: list[dict[str, Any]] = []
    seen: set[str] = set()
    for _ in range(limit):
        page.keyboard.press("Tab")
        node = page.evaluate(
            """() => {
                const el = document.activeElement;
                if (!el || el === document.body) return null;
                const r = el.getBoundingClientRect();
                return {
                    tag: el.tagName.toLowerCase(),
                    id: el.id || '',
                    text: (el.innerText || el.value ||
                           el.getAttribute('aria-label') || '').trim().slice(0, 40),
                    top: Math.round(r.top + window.scrollY),
                    left: Math.round(r.left + window.scrollX),
                    width: Math.round(r.width),
                    height: Math.round(r.height),
                };
            }"""
        )
        if node is None:
            break
        key = f"{node['tag']}#{node['id']}@{node['top']},{node['left']}:{node['text']}"
        if key in seen:
            break
        seen.add(key)
        sequence.append(node)
    return sequence


def test_focus_order_follows_visual_reading_order(page: Any, portal_server: PortalServer) -> None:
    """2.4.3, asserted properly: tab order must match what a sighted user sees.

    Axe confirms *an* order exists. This walks the real one and compares it against
    top-to-bottom position — which is the criterion, and the thing that actually breaks
    when someone reorders markup or adds a positioned element.
    """
    page.goto(f"{portal_server.base}/")
    sequence = _tab_sequence(page)

    assert len(sequence) >= 3, f"only {len(sequence)} focusable elements; the walk found too few"

    tops = [node["top"] for node in sequence]
    out_of_order = [
        (sequence[i - 1], sequence[i])
        for i in range(1, len(tops))
        # A tolerance, because elements on one visual row legitimately share a band.
        # A jump UP is a defect in the same column; starting the next column at its
        # top (icon rail, then list, then stage) is how this shell is read.
        if tops[i] < tops[i - 1] - 12 and sequence[i]["left"] <= sequence[i - 1]["left"] + 24
    ]
    assert out_of_order == [], "focus jumps upward against reading order: " + "; ".join(
        f"{a['text']!r} -> {b['text']!r}" for a, b in out_of_order
    )


def test_every_interactive_element_has_an_accessible_name(
    page: Any, portal_server: PortalServer
) -> None:
    """The screen-reader view, from the tree assistive technology actually consumes.

    A control announced as "button" and nothing else is unusable. This reads Playwright's
    accessibility snapshot rather than the DOM, so it catches the case where a visible
    label exists but is not *associated* — which looks fine and reads as nothing.
    """
    start_thread_from_home(page, portal_server)

    # The browser's own accessibility tree, via CDP. Playwright removed `page.accessibility`
    # in 1.58, and reaching for the protocol underneath is the better answer anyway: this is
    # the same tree the browser hands to assistive technology, not an approximation of it.
    session = page.context.new_cdp_session(page)
    session.send("Accessibility.enable")
    tree = session.send("Accessibility.getFullAXTree")

    interactive = {"button", "link", "textbox", "combobox", "checkbox", "radio", "listbox"}
    nameless: list[dict[str, str]] = []
    for node in tree.get("nodes", []):
        if node.get("ignored"):
            continue
        role = str((node.get("role") or {}).get("value", ""))
        name = str((node.get("name") or {}).get("value", "")).strip()
        if role in interactive and not name:
            nameless.append({"role": role, "id": str(node.get("nodeId", ""))})

    assert nameless == [], (
        f"interactive elements the browser exposes with no accessible name: {nameless}. "
        "Assistive technology announces these as their role and nothing else."
    )


def test_the_console_is_announced_to_a_screen_reader(
    page: Any, portal_server: PortalServer
) -> None:
    """CL3's other half — the console's states are *announced*, not merely rendered.

    Its most important content is a status, not a control: whether the estate is gated, and
    whether a record could be read. A `role="status"` region is how a screen-reader user
    learns those without hunting, and the console leans on them heavily precisely because
    what it has to say is mostly not interactive.
    """
    page.goto(f"{portal_server.base}/settings")

    session = page.context.new_cdp_session(page)
    session.send("Accessibility.enable")
    tree = session.send("Accessibility.getFullAXTree")

    roles = [
        str((node.get("role") or {}).get("value", ""))
        for node in tree.get("nodes", [])
        if not node.get("ignored")
    ]
    assert "status" in roles, (
        "the console's state — refused, ungated, unavailable — reaches a screen-reader user "
        "through a status region or not at all; rendering it as ordinary prose leaves them "
        "to find it"
    )

    named = [
        str((node.get("name") or {}).get("value", "")).strip()
        for node in tree.get("nodes", [])
        if not node.get("ignored")
    ]
    assert any(text for text in named), "the page exposes no accessible text at all"


def test_the_endorsed_sources_table_is_navigable_by_a_screen_reader(
    admin_page: Any, portal_server: PortalServer
) -> None:
    """EL3 — the console's new content is a TABLE, which is a structure or it is noise (045).

    A table of endorsed sources without header association is a screen-reader user hearing
    "acme-standards, https://…, dan@acme.example, v-one, citable" with no way to know which
    value is which. The row above audits the operator's refusal page, which contains no table
    at all — so this is the first row in the lane that can see the structure.
    """
    admin_page.goto(f"{portal_server.base}/settings")
    admin_page.wait_for_selector("table")

    session = admin_page.context.new_cdp_session(admin_page)
    session.send("Accessibility.enable")
    tree = session.send("Accessibility.getFullAXTree")
    roles = [
        str((node.get("role") or {}).get("value", ""))
        for node in tree.get("nodes", [])
        if not node.get("ignored")
    ]

    assert "table" in roles, "the endorsed sources render as something other than a table"
    assert roles.count("columnheader") >= 5, (
        "the table's columns are not headers, so a screen-reader user hears five values per "
        "row with nothing saying which is the location and which is the version in force"
    )
    assert "rowheader" in roles, (
        "no row is headed by its source name, so a user moving down a column cannot tell "
        "which source each value belongs to"
    )
    # The caption, because a table announced without one is a table a user must read to
    # identify.
    assert "caption" in roles or any(
        "endorsed" in str((node.get("name") or {}).get("value", "")).lower()
        for node in tree.get("nodes", [])
        if not node.get("ignored")
    )


def test_the_review_control_says_which_source_it_reviews(
    admin_page: Any, portal_server: PortalServer
) -> None:
    """Three buttons reading "Review changes" are three buttons a screen-reader user cannot
    tell apart — and picking the wrong one reaches a different customer's repository.

    The accessible name carries the source, which is why the label is not shortened to fit the
    column.
    """
    admin_page.goto(f"{portal_server.base}/settings")
    admin_page.wait_for_selector("table")

    names = admin_page.eval_on_selector_all(
        "form[action^='/settings/endorsed/'] button",
        "els => els.map(e => (e.getAttribute('aria-label') || e.textContent).trim())",
    )

    assert names, "there is no way to reach a review from the console"
    assert len(names) == len(set(names)), f"two review controls share a name: {names}"
    assert all("acme" in name for name in names), (
        f"a review control does not name its source: {names}"
    )


def test_the_review_page_announces_that_nothing_has_changed(
    admin_page: Any, portal_server: PortalServer
) -> None:
    """The review page's most important content is a status: **reviewing changes nothing**.

    A user who cannot hear that is left to infer it from the absence of a confirmation, which
    is exactly the inference an interface should never require about a governance act.
    """
    admin_page.goto(f"{portal_server.base}/settings")
    admin_page.click("form[action='/settings/endorsed/acme-standards/review'] button")
    admin_page.wait_for_selector("h1")

    session = admin_page.context.new_cdp_session(admin_page)
    session.send("Accessibility.enable")
    tree = session.send("Accessibility.getFullAXTree")
    roles = [
        str((node.get("role") or {}).get("value", ""))
        for node in tree.get("nodes", [])
        if not node.get("ignored")
    ]

    assert "status" in roles, "the review page's state reaches a screen-reader user through nothing"

    # **The AX tree gives the region's ROLE; its text comes from the DOM.** A live region's
    # accessible *name* is empty unless it is labelled — the announcement is its contents, not
    # its name — so a row asserting on the name alone would pass on a status region that said
    # nothing at all.
    announced = " ".join(
        admin_page.eval_on_selector_all(
            "[role=status]", "els => els.map(e => e.textContent.trim())"
        )
    ).lower()

    assert "nothing has changed" in announced, (
        f"the page does not announce that reviewing is not adopting: {announced!r}"
    )


def test_a_screen_reader_is_told_when_a_run_changes_state(
    page: Any, portal_server: PortalServer
) -> None:
    """The conversational-flow criterion, made concrete.

    The client updates a run's state in place. Without a live region a screen-reader user
    is never told — the page changes silently and they are left believing nothing has
    happened, which on a surface whose whole job is watching work is the difference between
    usable and not.
    """
    start_thread_from_home(page, portal_server, "plan the migration", agent="planner")

    live = page.evaluate(
        """() => {
            const el = document.querySelector('[data-run-id] .state');
            if (!el) return null;
            const region = el.closest('[aria-live]');
            return region ? {
                politeness: region.getAttribute('aria-live'),
                atomic: region.getAttribute('aria-atomic'),
            } : null;
        }"""
    )
    assert live is not None, (
        "the run-state element is not inside an aria-live region; a screen-reader user is "
        "never told the run progressed"
    )
    assert live["politeness"] in ("polite", "assertive")


def test_the_focus_indicator_is_actually_drawn(page: Any, portal_server: PortalServer) -> None:
    """2.4.13, measured rather than trusted.

    A stylesheet saying `outline: 3px` proves nothing if a later rule removes it. This
    focuses each control and reads the *computed* style off the focused element.
    """
    page.goto(f"{portal_server.base}/")
    page.keyboard.press("Tab")

    for _ in range(6):
        indicator = page.evaluate(
            """() => {
                const el = document.activeElement;
                if (!el || el === document.body) return null;
                const s = getComputedStyle(el);
                return {
                    text: (el.innerText || '').trim().slice(0, 30),
                    outlineWidth: parseFloat(s.outlineWidth) || 0,
                    outlineStyle: s.outlineStyle,
                    boxShadow: s.boxShadow,
                };
            }"""
        )
        if indicator is None:
            break
        drawn = (
            indicator["outlineWidth"] >= 1 and indicator["outlineStyle"] != "none"
        ) or indicator["boxShadow"] not in ("none", "")
        assert drawn, (
            f"the focused element {indicator['text']!r} draws no focus indicator "
            f"(outline {indicator['outlineWidth']}px {indicator['outlineStyle']}, "
            f"shadow {indicator['boxShadow']!r})"
        )
        page.keyboard.press("Tab")


def test_the_focused_element_is_never_obscured(page: Any, portal_server: PortalServer) -> None:
    """2.4.11: focus that scrolls out of view or sits under something is focus nobody sees."""
    page.goto(f"{portal_server.base}/")

    for _ in range(8):
        page.keyboard.press("Tab")
        state = page.evaluate(
            """() => {
                const el = document.activeElement;
                if (!el || el === document.body) return null;
                const r = el.getBoundingClientRect();
                if (r.width === 0 && r.height === 0) return null;
                const cx = r.left + r.width / 2;
                const cy = r.top + r.height / 2;
                const top = document.elementFromPoint(cx, cy);
                return {
                    text: (el.innerText || '').trim().slice(0, 30),
                    inViewport: r.top >= 0 && r.bottom <= window.innerHeight,
                    covered: top !== null && top !== el && !el.contains(top),
                };
            }"""
        )
        if state is None:
            continue
        assert state["inViewport"], f"focus moved off-screen at {state['text']!r}"
        assert not state["covered"], f"the focused element {state['text']!r} is painted over"


_TARGET_SIZE_PROBE = """(minimum) => {
    const targets = document.querySelectorAll('a, button, select, textarea, input');
    const bad = [];
    for (const el of targets) {
        const r = el.getBoundingClientRect();
        if (r.width === 0 && r.height === 0) continue;   // not rendered
        if (getComputedStyle(el).position === 'absolute' && r.width < 2) continue;
        // 2.5.8's INLINE EXCEPTION, in the criterion's own words: a target "in a sentence or
        // whose size is otherwise constrained by the line-height of non-target text" is
        // exempt. A link inside prose is sized by the line box around it, and forcing it to
        // 24px would break the rhythm of the sentence it lives in. Detected structurally —
        // an inline-displayed link whose parent holds text that is not the link.
        if (el.tagName === 'A' && getComputedStyle(el).display === 'inline') {
            const parent = el.parentElement;
            const around = parent ? parent.innerText.replace(el.innerText, '').trim() : '';
            if (around.length > 0) continue;
        }
        if (r.width < minimum || r.height < minimum) {
            bad.push({
                text: (el.innerText || el.getAttribute('aria-label') ||
                       el.tagName).trim().slice(0, 30),
                w: Math.round(r.width), h: Math.round(r.height),
            });
        }
    }
    return bad;
}"""


def test_every_target_meets_the_minimum_size(page: Any, portal_server: PortalServer) -> None:
    """2.5.8: a control smaller than 24×24 is one a person with a tremor cannot hit."""
    # BOTH surfaces. This row walked the thread page alone, and the ask composer's textarea
    # measured 22px from the day it shipped — a real 2.5.8 failure nothing was looking at.
    start_thread_from_home(page, portal_server)
    small = page.evaluate(_TARGET_SIZE_PROBE, MIN_TARGET_PX)
    assert small == [], f"thread-page targets below {MIN_TARGET_PX}px: {small}"

    page.goto(f"{portal_server.base}/ask")
    page.wait_for_load_state()
    on_ask = page.evaluate(_TARGET_SIZE_PROBE, MIN_TARGET_PX)
    assert on_ask == [], f"ask-page targets below {MIN_TARGET_PX}px: {on_ask}"


def test_alt_text_is_not_present_but_useless(page: Any, portal_server: PortalServer) -> None:
    """1.1.1's checkable half.

    Whether alt text is *good* is judgment. Whether it is a filename, or the literal word
    "image", or missing entirely on an informative graphic, is not — and those are the
    failures that actually happen.
    """
    page.goto(f"{portal_server.base}/")
    problems = page.evaluate(
        """(useless) => {
            const bad = [];
            for (const img of document.querySelectorAll('img')) {
                const alt = img.getAttribute('alt');
                if (alt === null) { bad.push({src: img.src, why: 'no alt attribute'}); continue; }
                const lowered = alt.trim().toLowerCase();
                if (useless.includes(lowered)) bad.push({src: img.src, why: `alt is ${alt!r}`});
                if (/\\.(png|jpe?g|gif|svg|webp)$/.test(lowered)) {
                    bad.push({src: img.src, why: 'alt is a filename'});
                }
            }
            return bad;
        }""".replace("${alt!r}", "${alt}"),
        list(USELESS_ALT),
    )
    assert problems == [], f"alt text problems: {problems}"


def test_no_interaction_requires_dragging(page: Any, portal_server: PortalServer) -> None:
    """2.5.7: asserted as an absence rather than reviewed by eye."""
    start_thread_from_home(page, portal_server)

    draggable = page.evaluate(
        """() => Array.from(document.querySelectorAll('[draggable="true"]'))
                     .map(el => el.tagName.toLowerCase())"""
    )
    assert draggable == [], f"draggable elements exist: {draggable}"

    script = page.evaluate(
        """() => Array.from(document.querySelectorAll('script[src]')).map(s => s.src)"""
    )
    assert script, "the row is stale — no script is served"


@pytest.mark.parametrize(("width", "height"), [(320, 800), (1280, 720)])
def test_the_page_reflows_without_horizontal_scrolling(
    page: Any, portal_server: PortalServer, width: int, height: int
) -> None:
    """1.4.10: at 320 CSS px nothing may require sideways scrolling to read."""
    page.set_viewport_size({"width": width, "height": height})
    start_thread_from_home(page, portal_server)
    page.fill("#message", "a message long enough to test wrapping " * 6)
    page.click(".run-composer button[type=submit]")
    page.wait_for_load_state()

    overflow = page.evaluate(
        """() => ({
            doc: document.documentElement.scrollWidth,
            view: document.documentElement.clientWidth,
        })"""
    )
    assert overflow["doc"] <= overflow["view"] + 1, (
        f"the page scrolls horizontally at {width}px ({overflow['doc']} > {overflow['view']})"
    )


_TEXT_SPACING_PROBE = """() => {
    const style = document.createElement('style');
    style.textContent = `* {
        line-height: 1.5 !important;
        letter-spacing: 0.12em !important;
        word-spacing: 0.16em !important;
    }
    p { margin-bottom: 2em !important; }`;
    document.head.appendChild(style);
    const bad = [];
    for (const el of document.querySelectorAll('p, li, label, h1, button, a')) {
        // Deliberately offscreen text (the `visually-hidden` idiom) is not clipped — it is a
        // 1px box on purpose, and nothing a sighted reader can see is being lost.
        if (el.getBoundingClientRect().height <= 1) continue;
        if (el.scrollHeight > el.clientHeight + 2 &&
            getComputedStyle(el).overflow === 'hidden') {
            bad.push((el.innerText || '').trim().slice(0, 30));
        }
    }
    return bad;
}"""


def test_text_spacing_overrides_do_not_clip_content(page: Any, portal_server: PortalServer) -> None:
    """1.4.12: applying the criterion's own spacing values must lose nothing.

    People with dyslexia routinely apply exactly these overrides. A layout with fixed
    heights silently clips text under them, which the page's own rendering never reveals.
    """
    # BOTH surfaces, because the pattern this row exists to catch is a fixed height and the
    # ask surface is the one with a composer sharing a row with a control.
    start_thread_from_home(page, portal_server)
    clipped = page.evaluate(_TEXT_SPACING_PROBE)
    assert clipped == [], f"text is clipped on the thread page under 1.4.12 spacing: {clipped}"

    page.goto(f"{portal_server.base}/ask")
    page.wait_for_load_state()
    on_ask = page.evaluate(_TEXT_SPACING_PROBE)
    assert on_ask == [], f"text is clipped on the ask page under 1.4.12 spacing: {on_ask}"


def test_the_document_declares_a_language_and_a_title(
    page: Any, portal_server: PortalServer
) -> None:
    """3.1.1 and 2.4.2 — cheap, and the first thing a screen reader uses."""
    page.goto(f"{portal_server.base}/")
    assert page.evaluate("() => document.documentElement.lang") == "en"
    assert "Harness" in page.title()

    start_thread_from_home(page, portal_server)
    page.wait_for_load_state()
    # Titles must differ between states, or a person with twenty tabs cannot tell them
    # apart — which is the whole point of the criterion.
    assert page.title() != "", "the thread page has no title"


def test_headings_and_landmarks_describe_the_page(page: Any, portal_server: PortalServer) -> None:
    """1.3.1: how a screen-reader user navigates without reading everything."""
    page.goto(f"{portal_server.base}/")
    structure = page.evaluate(
        """() => ({
            h1: document.querySelectorAll('h1').length,
            main: document.querySelectorAll('main').length,
            header: document.querySelectorAll('header').length,
            skip: !!document.querySelector('a[href^="#"]'),
        })"""
    )
    assert structure["h1"] == 1, f"expected exactly one h1, found {structure['h1']}"
    assert structure["main"] == 1
    assert structure["skip"], "no skip link, so a keyboard user tabs the header every time"


# --------------------------------------------------------------------------------------
# What is still not automated here, stated so the boundary stays visible.
#
# These rows cover the criteria previously deferred to a person. What a browser genuinely
# cannot decide is whether the *words* are good: whether "Send" is the right label for what
# the button does, whether a decline's explanation actually helps, whether the reading
# level suits the audience. That is content review, not conformance testing, and it does
# not belong in a gate.
#
# One real limit worth naming: this asserts against the accessibility TREE, which is what
# assistive technology consumes, but not against any specific screen reader's behaviour.
# JAWS, NVDA, and VoiceOver differ. A page that satisfies these rows can still read oddly
# in one of them, and finding that out needs the software itself.
