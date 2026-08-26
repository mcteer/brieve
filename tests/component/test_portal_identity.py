# SPDX-License-Identifier: Apache-2.0
"""GATE:fail-closed — the portal's visual identity is enforceable, not conventional.

Four claims that a stylesheet cannot make about itself:

**Tokens are the only source of colour.** A design system nobody enforces becomes a suggestion
the first time someone is in a hurry, and the failure is invisible — a page with one hardcoded
blue looks fine and is no longer themeable. The row below fails on a colour literal outside the
token blocks, which is what turns "no page invents its own colour" into a fact.

**A verdict survives greyscale.** Colour alone would fail 1.4.1, and the axe lane cannot check
"is this meaning carried by more than hue" — that is a structural question, asked here.

**The vendored font is what it claims to be.** The row recomputes the digests in
`fonts/PROVENANCE.md`; the row is the verifier, exactly as the pack loader is for skill bytes.

**Nothing is fetched from a third party.** The portal works offline, and the check is about what
the BROWSER FETCHES — `src`, `<link href>`, `url()`, `@import` — not about what a person may
click. Citation anchors point at developer.hashicorp.com and legitimately should.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "src" / "surfaces" / "portal" / "static"
TEMPLATES = ROOT / "src" / "surfaces" / "portal" / "templates"
CSS = STATIC / "portal.css"
PROVENANCE = STATIC / "fonts" / "PROVENANCE.md"

#: Anything that looks like a colour. Deliberately broad: the point is that colour lives in
#: exactly one place, so the check should catch a value however it is spelled.
COLOUR = re.compile(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(")

#: Where colour IS allowed: the token declarations themselves. One designed theme (048).
TOKEN_BLOCKS = (":root {",)


def _token_block_lines(source: str) -> set[int]:
    """Line numbers inside a token declaration block, brace-counted rather than guessed."""
    inside: set[int] = set()
    depth = 0
    for number, line in enumerate(source.splitlines(), start=1):
        opening = any(marker in line for marker in TOKEN_BLOCKS)
        if opening:
            depth += line.count("{")
            inside.add(number)
            continue
        if depth:
            inside.add(number)
            depth += line.count("{") - line.count("}")
    return inside


def test_every_colour_lives_in_a_token() -> None:
    """SC-004. A page-local colour is a defect a check can find — so it finds it."""
    source = CSS.read_text()
    allowed = _token_block_lines(source)

    strays = [
        (number, line.strip())
        for number, line in enumerate(source.splitlines(), start=1)
        if number not in allowed and COLOUR.search(line) and not line.strip().startswith("*")
    ]

    assert strays == [], (
        f"colour outside the token blocks: {strays}. Every colour is a token — add one and "
        f"reference it, so the theme stays changeable in one place"
    )


def test_no_template_carries_its_own_colour() -> None:
    """The other half of the same discipline: a `style=` attribute escapes the token system
    entirely and is invisible to the stylesheet's own audit."""
    offenders = [
        (path.name, line.strip())
        for path in sorted(TEMPLATES.glob("*.html"))
        for line in path.read_text().splitlines()
        if "style=" in line and COLOUR.search(line)
    ]

    assert offenders == [], f"inline colour in templates: {offenders}"


def _font_face_lines(source: str) -> set[int]:
    """`@font-face` names the family it is defining rather than using a role token."""
    inside: set[int] = set()
    depth = 0
    for number, line in enumerate(source.splitlines(), start=1):
        if "@font-face" in line:
            depth += line.count("{")
            inside.add(number)
            continue
        if depth:
            inside.add(number)
            depth += line.count("{") - line.count("}")
    return inside


def test_every_typeface_is_a_role() -> None:
    """FR-001. Three roles plus a display face; a fourth stack appearing inline is a role
    nobody named, and the next person will not know which content belongs to it."""
    source = CSS.read_text()
    allowed = _token_block_lines(source)
    face_lines = _font_face_lines(source)

    strays = [
        (number, line.strip())
        for number, line in enumerate(source.splitlines(), start=1)
        if number not in allowed
        and number not in face_lines
        and "font-family:" in line
        and "var(--font-" not in line
    ]

    assert strays == [], f"a typeface outside the role tokens: {strays}"


def test_a_verdict_is_carried_by_more_than_colour() -> None:
    """SC-003, 1.4.1. The pill has a border and contains the disposition word; hue is the
    third signal rather than the only one — so the meaning survives greyscale, a colour-blind
    reader, and a printed page."""
    css = CSS.read_text()
    thread = (TEMPLATES / "_thread_turns.html").read_text()

    assert ".pill {" in css
    pill_rule = css.split(".pill {", 1)[1].split("}", 1)[0]
    assert "border:" in pill_rule, "the pill has no border — greyscale would erase the verdict"

    for verdict in ("declined", "refused"):
        assert f'class="pill pill--{verdict}"' in thread, f"{verdict} has no pill"
        # The word itself, not only a class: a screen reader and a greyscale printer both get it.
        assert f">{verdict}</span>" in thread, f"the {verdict} pill does not say so in text"


def test_the_vendored_font_is_what_the_record_says() -> None:
    """FR-002a. The provenance document is only as good as something checking it, and this is
    that something — the same posture the pack loader takes toward skill bytes."""
    record = PROVENANCE.read_text()
    digests = dict(re.findall(r"`([^`]+)`[^|]*\|\s*`([0-9a-f]{64})`", record))
    assert digests, "the provenance record carries no digests to verify"

    fonts_dir = STATIC / "fonts"
    for name in (
        "roboto-variable.woff2",
        "ibm-plex-mono-regular.woff2",
        "ibm-plex-mono-medium.woff2",
        "OFL-roboto.txt",
        "OFL-ibm-plex-mono.txt",
    ):
        recorded = next((d for key, d in digests.items() if name in key), None)
        assert recorded, f"{name} has no recorded digest"
        actual = hashlib.sha256((fonts_dir / name).read_bytes()).hexdigest()
        assert actual == recorded, (
            f"{name} does not match its provenance record: {actual} != {recorded}. Either the "
            f"file changed without the record, or the record without the file — both are the "
            f"drift this check exists to stop"
        )

    leftover = fonts_dir / "inter-variable.woff2"
    leftover_licence = fonts_dir / "OFL-inter.txt"
    leftover_034 = fonts_dir / "OFL.txt"
    assert not leftover.exists(), "inter-variable.woff2 must leave with Roboto (unused faces leave)"
    assert not leftover_licence.exists(), "OFL-inter.txt must leave with Inter"
    assert not leftover_034.exists(), "unnamed OFL.txt is not the Roboto licence file"


def test_the_licence_travels_with_the_font() -> None:
    """OFL 1.1's own requirement, and a supply-chain fact: adopted content carries its terms."""
    roboto = (STATIC / "fonts" / "OFL-roboto.txt").read_text()
    plex = (STATIC / "fonts" / "OFL-ibm-plex-mono.txt").read_text()
    record = PROVENANCE.read_text()

    assert "SIL Open Font License" in roboto
    assert "SIL Open Font License" in plex
    assert "OFL" in record, "the provenance record does not name the licence"
    assert "Reserved Font Name" in record, "Plex RFN presence must be recorded"
    assert "Palatino" not in CSS.read_text()
    assert "Inter" not in CSS.read_text()
    assert "Iowan Old Style" not in CSS.read_text()


@pytest.mark.parametrize("path", sorted(TEMPLATES.glob("*.html")), ids=lambda p: p.name)
def test_no_template_fetches_from_a_third_party(path: Path) -> None:
    """SC-006. The offline property, checked at what the BROWSER FETCHES.

    A citation anchor pointing at developer.hashicorp.com is a link a person may follow and is
    not a fetch — narrowing to fetch-causing attributes is what keeps this row honest rather
    than merely strict.
    """
    fetching = re.findall(r'(?:src|href)\s*=\s*"(https?://[^"]+)"', path.read_text())
    external = [url for url in fetching if not url.startswith(("http://localhost", "/"))]
    # `href` on an anchor is navigation; only stylesheet/script/image references fetch.
    fetch_causing = [
        url
        for url in external
        if any(tag in path.read_text() for tag in ("<link", "<script", "<img"))
        and re.search(rf'<(?:link|script|img)[^>]*"{re.escape(url)}"', path.read_text())
    ]

    assert fetch_causing == [], f"{path.name} fetches from a third party: {fetch_causing}"


def test_hashicorp_mark_matches_provenance() -> None:
    record = (STATIC / "mark" / "PROVENANCE.md").read_text()
    digest = re.search(r"`hashicorp-logomark.svg`\s*\|\s*`([0-9a-f]{64})`", record)
    assert digest, "mark provenance has no digest"
    actual = hashlib.sha256((STATIC / "mark" / "hashicorp-logomark.svg").read_bytes()).hexdigest()
    assert actual == digest.group(1)
    assert "orange" not in CSS.read_text().lower() or "--warning" in CSS.read_text()


def test_the_stylesheet_fetches_nothing_external() -> None:
    """The same claim for CSS: `url()` and `@import` are fetches, and the only one here is the
    font we vendored ourselves."""
    source = CSS.read_text()

    urls = re.findall(r"url\(\s*[\"']?([^\"')]+)", source)
    assert all(not url.startswith(("http://", "https://", "//")) for url in urls), (
        f"the stylesheet fetches from off-origin: {urls}"
    )
    assert "@import" not in source, "@import is a runtime fetch the offline property forbids"
    assert set(urls) == {
        "fonts/roboto-variable.woff2",
        "fonts/ibm-plex-mono-regular.woff2",
        "fonts/ibm-plex-mono-medium.woff2",
    }, f"unexpected asset references: {urls} — every one is a fetch a reader pays for"


# ------------------------------------------------------------------ US2: the product stripe


def _render_thread(turns: list[dict[str, object]], definitions: list[dict[str, object]]) -> str:
    """The real template, rendered with the real environment — not a string built here."""
    from fastapi.templating import Jinja2Templates  # noqa: PLC0415

    from surfaces.portal.app import TEMPLATES as TEMPLATE_DIR  # noqa: PLC0415

    environment = Jinja2Templates(directory=str(TEMPLATE_DIR)).env
    return environment.get_template("threads.html").render(
        request=_FakeRequest(),
        thread={"thread_id": "t-1", "title": "A conversation"},
        turns=turns,
        threads=[],
        reachable=True,
        refused=False,
        definitions=definitions,
        definitions_reachable=True,
    )


class _FakeRequest:
    """Enough request for the templates: a path, for `aria-current`."""

    class _Url:
        path = "/threads/t-1"

    url = _Url()


def _turn(definition: str | None) -> dict[str, object]:
    return {
        "turn_id": "x",
        "message": "do the thing",
        "disposition": "dispatched",
        "agent_definition_id": definition,
        "run_id": "r-1",
        "run": None,
        "result_status": None,
        "context_run_ids": (),
        "context_dropped": (),
    }


def test_a_turn_shows_the_product_its_definition_declares() -> None:
    """US2. The platform knows; the page now says so."""
    html = _render_thread(
        turns=[_turn("vault-agent")],
        definitions=[
            {"agent_definition_id": "vault-agent", "may_start": True, "packs": ("vault",)}
        ],
    )

    assert 'data-pack="vault"' in html


def test_an_unknown_product_costs_no_colour_and_no_space() -> None:
    """FR-006. Absence is not a visual defect to apologise for — there is no attribute at all,
    so the stylesheet has nothing to style and no placeholder is reserved."""
    for definitions in (
        [{"agent_definition_id": "mystery", "may_start": True, "packs": ()}],
        [],  # the definition is not in the list at all
    ):
        html = _render_thread(turns=[_turn("mystery")], definitions=definitions)
        assert "data-pack" not in html


def test_a_definition_spanning_products_draws_no_stripe() -> None:
    """One identity or none. Two packs have no single colour, and picking the first would be
    the page asserting something the record does not say."""
    html = _render_thread(
        turns=[_turn("both-agent")],
        definitions=[
            {
                "agent_definition_id": "both-agent",
                "may_start": True,
                "packs": ("terraform", "vault"),
            }
        ],
    )

    assert "data-pack" not in html


def test_the_stripe_is_a_lookup_not_a_guess_from_the_name() -> None:
    """The row that would catch the tempting shortcut.

    `vault-agent` says its product in its own id, so a name heuristic would pass every happy
    case and be wrong the first time a definition was named for its team. Here the definition
    is NAMED for one product and DECLARES another: the record wins.
    """
    html = _render_thread(
        turns=[_turn("vault-agent")],
        definitions=[
            {"agent_definition_id": "vault-agent", "may_start": True, "packs": ("terraform",)}
        ],
    )

    assert 'data-pack="terraform"' in html
    assert 'data-pack="vault"' not in html


def test_the_thread_list_carries_no_product_at_all() -> None:
    """Deferred, and asserted so the deferral cannot rot into an accidental implementation."""
    threads_template = (TEMPLATES / "threads.html").read_text()
    turns_partial = (TEMPLATES / "_thread_turns.html").read_text()

    assert "data-pack" not in threads_template
    assert "does not know which product" not in threads_template
    assert "data-pack" in turns_partial


def _css_block(source: str, selector: str) -> str:
    needle = selector + " {"
    assert needle in source, f"missing rule {selector}"
    return source.split(needle, 1)[1].split("}", 1)[0]


def test_composer_and_reading_column_share_one_measure() -> None:
    """The composer is a rounded bubble on the SAME axis and the SAME width as the transcript.

    050 pinned the composer at 56rem beside a 680px transcript, both centred on one axis —
    which put the field a person types into 216px wider than the answers above it, so no two
    edges in the conversation lined up. Widths that are meant to match are asserted here as
    one token rather than as two literals that agreed once: two numbers that must be equal and
    are written down twice are two numbers that will stop being equal.
    """
    css = CSS.read_text()
    composer = _css_block(css, ".composer")
    reading = _css_block(css, ".thread .inner")

    assert "display: flex" in composer
    assert "flex-direction: column" in composer
    assert "min-height: 7.5rem" not in composer
    assert "var(--radius-composer)" in composer

    assert "max-width: var(--stage-column)" in composer
    assert "max-width: var(--stage-column)" in reading
    assert "margin-inline: auto" in composer
    assert "margin-inline: auto" in reading

    # The docked composer takes the same measure, so an open item and empty home agree.
    assert css.count("min(var(--stage-column), calc(100% - 4rem))") == 2
    # No rule sets a width of its own beside the token. (The token's own comment names the
    # 56rem it replaced, so this looks at declarations rather than at the whole file.)
    assert "max-width: 56rem" not in css
    assert "width: min(56rem" not in css

    # The field's FLOOR, which is a 2.5.8 matter rather than a taste one: this textarea
    # shipped at 22px and sat under the 24px target minimum until the a11y lane caught it.
    # Asserted as "at least 24px" rather than as one exact value, so the composer can be
    # made taller or shorter without anybody having to guess which number was load-bearing.
    textarea = _css_block(css, ".composer textarea")
    floor = re.search(r"min-height:\s*([0-9.]+)rem", textarea)
    assert floor is not None, "the composer field declares no minimum height"
    assert float(floor.group(1)) * 16 >= 24, (
        f"the composer field floor is {floor.group(1)}rem, under the 24px target minimum"
    )
    go = _css_block(css, ".composer .ask-send,\n.composer .go")
    assert "position: static" in go
    assert "margin: 0 0 0 auto" in go


def test_header_actions_are_themed_chips_not_native_buttons() -> None:
    """Stop in the Build header was a browser-default button on a dark page."""
    css = CSS.read_text()
    quiet = _css_block(css, ".quiet-action")
    chip = _css_block(css, ".rail-new")

    assert "appearance: none" in quiet
    assert "background: var(--bg-surface)" in quiet
    assert "border: 1px solid var(--border-strong)" in quiet
    assert "border-radius: var(--radius-sm)" in quiet
    assert "background: var(--bg-surface)" in chip
    assert "border: 1px solid var(--border-strong)" in chip


def test_ask_script_turns_the_action_into_stop() -> None:
    """While a question is in flight the same control aborts the wait, like every chat UI."""
    script = (STATIC / "portal-ask.js").read_text()
    assert "AbortController" in script
    assert '"Stop"' in script
    assert "inflight.abort" in script


def test_propose_submit_script_turns_the_action_into_stop() -> None:
    """While a Build POST is in flight the same control aborts the wait, like Ask."""
    script = (STATIC / "portal-propose-submit.js").read_text()
    assert "AbortController" in script
    assert '"Stop"' in script
    assert "inflight.abort" in script
    assert "fetch(form.action" in script
    assert "BRIEVE_PROPOSE_WATCH" in script


def test_column_names_settings_and_sign_out() -> None:
    """US4 / FR-011. The column names Settings and Sign out — as TEXT, not as a label.

    Both are icon-only now (a gear and a power symbol), which is exactly the shape that
    usually loses a name: the words move to `aria-label`, the visible string disappears, and
    the name is then in a place no test that reads this file would notice going stale. So the
    assertion is unchanged from when they were visible rows — the words are still in the
    document, in a `visually-hidden` span — and the icons are asserted to carry no name of
    their own, so the accessible name has one source and this row still guards it.
    """
    base = (TEMPLATES / "base.html").read_text()
    assert ">Settings<" in base
    assert 'href="/settings"' in base
    assert ">Sign out<" in base
    assert "subject_user_id" in base
    assert 'aria-label="New"' in base
    assert 'aria-label="Projects"' in base

    # The marks are decorative — the span beside them is the name.
    account = base.split('class="column-end"', 1)[1]
    assert account.count('aria-hidden="true"') == 2
    assert "aria-label" not in account
    assert account.count('class="visually-hidden">Settings<') == 1
    assert account.count('class="visually-hidden">Sign out<') == 1


def test_decision_comments_survive_on_base_and_ask() -> None:
    """FR-014 / research F9. Premises update; comments are not deleted."""
    base = (TEMPLATES / "base.html").read_text()
    ask = (TEMPLATES / "ask.html").read_text()

    assert "ONE EMPTY HOME, LOCKED SLIDER" in base
    assert "028 chose separate pages" in base
    assert "SETTINGS, LINKED FOR EVERYONE" in base
    assert "aria-current" in base
    assert "left column" in base
    assert "the only one that wants the whole viewport" not in base

    assert "empty list region stays" in ask or "omitted when there is nothing to list" in ask
    assert "No `tabindex`" in ask or "No tabindex" in ask
