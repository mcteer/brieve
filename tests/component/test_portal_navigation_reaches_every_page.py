# SPDX-License-Identifier: Apache-2.0
"""Every page a person can open is reachable from the navigation (045).

**A page nothing links to is a page nobody finds.** 044 built `/settings` — admin-gated,
accessibility-audited, with its own conformance rows — and linked it from nowhere. It was
reachable only by typing the URL, and it stayed that way through 045, which added an entire
section and a review flow to it. Found by an administrator going to look for it.

That is `capability_inventory.py`'s finding one layer up: *built and unreachable*, in the
interface, where the inventory cannot see. The inventory sweeps `src/core` for capabilities a
run can reach; nothing swept the portal for pages a person can reach, and both gates existed —
the a11y lane walks `/settings` with `page.goto`, which asserts the page is accessible and says
nothing about whether anybody can get to it.

So this row reads the routes the portal actually registers and requires each top-level page to
appear in the navigation. It is deliberately derived from the app rather than from a list: a
list would have to be remembered, and the whole class of defect here is something nobody
remembered.
"""

from __future__ import annotations

import re

from surfaces.portal.app import create_portal
from surfaces.portal.oidc import OidcClient
from surfaces.portal.relay import ApiRelay, ApiResponse

#: Paths that are correctly absent from the navigation, each with the reason. **Enumerated, so
#: adding one is a decision somebody wrote down** rather than a page quietly slipping out of
#: reach — which is precisely what happened to `/settings`.
NOT_NAVIGATION = {
    # The OIDC flow. A person arrives here from the provider, never from a link.
    "/login": "part of the sign-in flow; linking it would be linking a redirect",
    "/callback": "the provider posts here; it is not a destination",
    "/signout": "an action, offered as a control rather than as a place",
    # 034's static asset routes and the health probe: not pages.
    "/static/{path:path}": "assets",
    "/healthz": "a probe, not a page",
    # FastAPI's own routes. Machine-facing, and linking them would put a schema document in
    # a person's navigation.
    "/openapi.json": "the schema, not a page",
    "/docs": "generated API documentation",
    "/docs/oauth2-redirect": "generated API documentation",
    "/redoc": "generated API documentation",
    # 047: home is Build. `/propose` 303s there so old bookmarks still work — linking
    # both would put the same page in the nav twice.
    "/propose": "alias of `/`; not a distinct page",
    # Operator agent-picker. 047 moved the primary act to Build; `/run` stays for
    # people who still start a named agent, reached by URL rather than the main nav.
    "/run": "operator Run surface; not the primary product path",
}


def _nav_targets() -> set[str]:
    """The hrefs in the main navigation, read out of the rendered template.

    Rendered rather than regex-matched over the file, so a link inside a comment or behind a
    condition that is never true does not count as reachable.
    """
    portal = create_portal(
        relay=ApiRelay(
            base_url="http://api.test",
            transport=lambda **kwargs: ApiResponse(status=200, payload={}),
        ),
        oidc=OidcClient(
            issuer="http://idp.test",
            client_id="portal",
            redirect_uri="http://localhost/callback",
            authorize_endpoint="http://idp.test/authorize",
            token_endpoint="http://idp.test/token",
            exchange=lambda code, code_verifier: {},
        ),
    )
    from fastapi.testclient import TestClient

    body = TestClient(portal).get("/").text
    nav = re.search(r"<nav[^>]*aria-label=\"Main\"[^>]*>(.*?)</nav>", body, re.S)
    assert nav, "the portal renders no main navigation at all"
    return set(re.findall(r'href="([^"#?]+)"', nav.group(1)))


def _page_routes() -> set[str]:
    """Top-level GET routes that render a page for a person.

    Excludes anything with a path parameter: a conversation or a thread is reached from a
    list, not from the navigation, and requiring a link to `/threads/{id}` would be asking
    for something that cannot exist.
    """
    portal = create_portal(
        relay=ApiRelay(
            base_url="http://api.test",
            transport=lambda **kwargs: ApiResponse(status=200, payload={}),
        ),
        oidc=OidcClient(
            issuer="http://idp.test",
            client_id="portal",
            redirect_uri="http://localhost/callback",
            authorize_endpoint="http://idp.test/authorize",
            token_endpoint="http://idp.test/token",
            exchange=lambda code, code_verifier: {},
        ),
    )
    paths: set[str] = set()
    for route in portal.routes:
        path = str(getattr(route, "path", ""))
        methods = getattr(route, "methods", None) or set()
        if "GET" in methods and "{" not in path and path not in NOT_NAVIGATION:
            paths.add(path)
    return paths


def test_every_top_level_page_is_reachable_from_the_navigation() -> None:
    """The row 044 needed and 045 wrote, after the page it would have caught went unlinked.

    `/settings` is the case in hand: admin-gated, accessibility-audited, conformance-covered,
    and reachable only by typing a URL. Everything about it was tested except that a person
    could get to it.
    """
    unreachable = sorted(_page_routes() - _nav_targets())

    assert not unreachable, (
        f"{unreachable} render pages that nothing in the navigation links to. A page nobody "
        f"can navigate to is a page nobody finds — and every other gate stays green, because "
        f"each of them opens the page by URL. If one of these is deliberately unlinked, name "
        f"it in NOT_NAVIGATION with the reason."
    )


def test_the_navigation_links_nothing_that_is_not_a_page() -> None:
    """The other direction. A link to a route that does not exist is a 404 with a person's
    click behind it, and it would look identical to a page that had simply moved."""
    routes = _page_routes() | set(NOT_NAVIGATION)
    dangling = sorted(target for target in _nav_targets() if target not in routes)

    assert not dangling, f"the navigation links {dangling}, which the portal does not serve"


def _console_forms() -> list[str]:
    """Every `<form>` on the console and its review page, as whole blocks.

    **Whole blocks rather than actions**, and that was a correction. The first version
    collected action attributes alone, and could not tell the endorse form (`/settings/endorsed`,
    with a location) from the re-endorse control on a withdrawn source (`/settings/endorsed`,
    without one) — so deleting the endorse form left the row green. A gate that cannot fail is
    the thing this estate refuses, and it took removing the form to find out.

    Rendered rather than grepped, for the reason `_nav_targets` is: a control inside a comment
    or behind a condition that never fires is not a control.
    """
    from fastapi.templating import Jinja2Templates

    from surfaces.portal.app import TEMPLATES

    templates = Jinja2Templates(directory=str(TEMPLATES))
    forms: list[str] = []
    for name, context in (
        ("settings.html", {"posture": _POSTURE, "reachable": True, "refused": False}),
        (
            "endorsed_review.html",
            {
                "source": "acme",
                "review": _REVIEW,
                "reachable": True,
                "refused": False,
                "failed": False,
                "failure": "",
            },
        ),
    ):
        body = templates.get_template(name).render(request=_FakeRequest(), **context)
        forms.extend(re.findall(r"<form\b.*?</form>", body, re.S))
    return forms


def _form_posting_to(action: str, *, carrying: str = "") -> str | None:
    """The form for one operation, identified by where it posts and what it carries.

    `carrying` is what makes two forms with the same action distinguishable — an endorsement
    of a NEW source needs a location; restoring a withdrawn one deliberately does not, because
    re-endorsing keeps the location and the adopted version already recorded.
    """
    for form in _console_forms():
        if f'action="{action}"' not in form:
            continue
        if carrying and f'name="{carrying}"' not in form:
            continue
        return form
    return None


class _FakeRequest:
    """Enough of a request for the templates to render: they read `url.path` and nothing else."""

    class _Url:
        path = "/settings"

    url = _Url()


#: A console posture with one endorsed source and one withdrawn one, so the row sees the
#: controls that only appear in each state. A fixture showing one state would assert nothing
#: about the other, which is how the re-endorse control could go missing unnoticed.
_POSTURE = {
    "gating": "ungated",
    "bindings": {"unavailable": True},
    "qualified_cells": {"unavailable": True},
    "connections": {"unavailable": True},
    "endorsed_sources": {
        "sources": {
            "acme": {
                "location": "https://git.example.com/acme",
                "endorsed_by": "dan",
                "endorsed_at": "",
                "adopted_version": "v-one",
                "adopted_by": "dan",
                "adopted_at": "",
                "withdrawn": False,
                "citable": True,
            },
            "retired": {
                "location": "https://git.example.com/old",
                "endorsed_by": "dan",
                "endorsed_at": "",
                "adopted_version": "",
                "adopted_by": "",
                "adopted_at": "",
                "withdrawn": True,
                "citable": False,
            },
        },
        "version": 1,
        "set_by": "console/dan",
        "consumed_by": "citation resolution, at the adopted version",
    },
}

_REVIEW = {
    "candidate_version": "v-two",
    "adopted_version": "v-one",
    "upstream_tip": "abc",
    "added": [],
    "removed": [],
    "common": [],
    "uncitable": [],
    "in_force": "nothing has changed; adopting is a separate act",
}


def test_every_console_operation_has_a_control() -> None:
    """**The gap the navigation row could not see, one level in.**

    045 shipped endorse, withdraw and adopt as API routes and a console that could only read.
    The one act the feature is named for could not be performed from the interface, and the
    review page said *"adopting is a separate act"* while offering no way to do it.

    The navigation row checks that pages are reachable. This checks that the operations on them
    are — because "built and unreachable" has two shapes and the first gate only saw one.
    """
    for operation, action, carrying in (
        ("endorse a new source", "/settings/endorsed", "location"),
        # Withdraw is offered on the source that is still trusted, not on the one already
        # withdrawn — which is why the fixture carries one of each.
        ("withdraw", "/settings/endorsed/acme/withdraw", ""),
        ("adopt", "/settings/endorsed/acme/adopt", "version_id"),
        ("review", "/settings/endorsed/acme/review", ""),
    ):
        assert _form_posting_to(action, carrying=carrying) is not None, (
            f"the console exposes no control to {operation}. The API route exists; a person "
            f"cannot reach it. That is the same defect as an unlinked page, one level in."
        )


def test_the_adopt_control_carries_the_version_that_was_reviewed() -> None:
    """Not "the latest" — what the administrator actually looked at.

    The source can move between the review and the click, and adopting something other than
    what was just read is the failure the review step exists to prevent.
    """
    form = _form_posting_to("/settings/endorsed/acme/adopt", carrying="version_id")

    assert form is not None
    assert 'value="v-two"' in form, (
        "the adopt control does not carry the reviewed candidate, so what gets adopted is "
        "whatever the server resolves at click time"
    )


def test_a_withdrawn_source_can_be_re_endorsed_from_the_page() -> None:
    """Withdrawal is reversible and the interface has to say so.

    Without a control, restoring trust would mean deleting and recreating the source — which
    loses the adopted version, and with it every run record's ability to name ground that
    still exists. The control carries a source and NO location, which is what distinguishes it
    from endorsing something new.
    """
    restore = _form_posting_to("/settings/endorsed", carrying="source")

    assert restore is not None, "a withdrawn source offers no way back"
    assert 'value="retired"' in restore


def test_there_is_nowhere_on_this_page_to_type_a_credential() -> None:
    """FR-018b's posture, asserted at the interface rather than only in the record parser.

    The vocabulary has no field a secret could go in; this is the other end of that — no input
    invites one. A form that asked for a token would make the closed set irrelevant.
    """
    for form in _console_forms():
        for forbidden in ("password", "token", "secret", "credential", "api_key"):
            assert f'name="{forbidden}"' not in form.lower(), (
                f"the console asks for {forbidden!r}. A source's material is trust-store "
                f"material referenced per sync, never entered here."
            )
        assert 'type="password"' not in form


def test_settings_is_linked() -> None:
    """Named explicitly as well as covered by the sweep above.

    The sweep is the general rule; this is the instance that produced it, and a row naming the
    case makes the regression legible in a diff rather than only in a set difference.
    """
    assert "/settings" in _nav_targets(), (
        "the admin console is unlinked again — it was built in 044, extended in 045, and "
        "reachable by URL alone through both"
    )
