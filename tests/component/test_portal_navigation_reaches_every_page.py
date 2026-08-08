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


def test_settings_is_linked() -> None:
    """Named explicitly as well as covered by the sweep above.

    The sweep is the general rule; this is the instance that produced it, and a row naming the
    case makes the regression legible in a diff rather than only in a set difference.
    """
    assert "/settings" in _nav_targets(), (
        "the admin console is unlinked again — it was built in 044, extended in 045, and "
        "reachable by URL alone through both"
    )
