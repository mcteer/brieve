# SPDX-License-Identifier: Apache-2.0
"""The accessibility lane: a real browser over every rendered page state.

**A gate class no other lane here can run.** Every existing gate asserts something about a
process — a decision, a refusal, a chain. This one asserts something about a *rendered
interface*, which needs a browser, which is why it has its own target and its own CI job
rather than a marker on an existing lane.

Everything behind the portal is doubled. This gate is about the page, not the platform:
what it checks is whether a person using a screen reader, a keyboard, or a magnified
display can use what 012 built.
"""

from __future__ import annotations

import pathlib
import threading
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import pytest
import uvicorn
from fastapi.testclient import TestClient

from surfaces.portal.app import create_portal
from surfaces.portal.oidc import OidcClient, code_challenge_for
from surfaces.portal.relay import ApiRelay, ApiResponse
from tests.harness.api_fixtures import surface_under_test

AXE = pathlib.Path(__file__).parent / "vendor/axe.min.js"
PORT = 8099

#: The ruleset this gate binds to (FR-020a).
#:
#: 2.2 rather than 2.1 because its additions — focus appearance, target size, dragging
#: alternatives — land squarely on a conversational interface rather than incidentally.
AXE_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]


@dataclass
class PortalServer:
    """A running portal, and the doubles needed to log into it."""

    base: str
    oidc: OidcClient
    idp: Any
    api: TestClient
    surface: Any


@pytest.fixture(scope="session")
def portal_server() -> Iterator[PortalServer]:
    """The real portal as a process, because a browser cannot drive an ASGI object."""
    surface = surface_under_test()
    api = TestClient(surface.app)

    def transport(*, method: str, url: str, token: str, json_body: object) -> ApiResponse:
        path = url.replace("http://api.test", "")
        response = api.request(
            method, path, json=json_body, headers={"Authorization": f"Bearer {token}"}
        )
        return ApiResponse(
            status=response.status_code,
            payload=response.json() if response.content else None,
        )

    oidc = OidcClient(
        issuer=surface.idp.issuer,
        client_id="portal",
        redirect_uri=f"http://127.0.0.1:{PORT}/callback",
        authorize_endpoint="http://idp.test/authorize",
        token_endpoint="http://idp.test/token",
        exchange=lambda code, code_verifier: surface.idp.exchange(
            code=code, code_verifier=code_verifier, redirect_uri="http://localhost/callback"
        ),
    )
    app = create_portal(
        relay=ApiRelay(base_url="http://api.test", transport=transport),
        oidc=oidc,
    )
    config = uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    waited = 0.0
    while not server.started and waited < 10:
        threading.Event().wait(0.05)
        waited += 0.05
    if not server.started:  # pragma: no cover - the lane cannot run
        raise RuntimeError("the portal did not start; the accessibility gate cannot run")

    yield PortalServer(
        base=f"http://127.0.0.1:{PORT}",
        oidc=oidc,
        idp=surface.idp,
        api=api,
        surface=surface,
    )
    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture(scope="session")
def browser() -> Iterator[Any]:
    """A headless browser.

    **Fails rather than skips when absent**, because a lane that skips itself reports the
    same green as one that ran. `make a11y` installs the browser; a bare pytest run that
    has not needs to hear about it rather than quietly pass.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - the lane cannot run
        raise RuntimeError(
            "the accessibility gate needs playwright. Run `make a11y`, which installs it "
            "and the browser. Not skippable: a gate that skips reports the same green as "
            "one that ran."
        ) from exc

    with sync_playwright() as engine:
        instance = engine.chromium.launch()
        yield instance
        instance.close()


@pytest.fixture
def page(browser: Any, portal_server: PortalServer) -> Iterator[Any]:
    """A fresh, signed-in page. Each row starts from a clean browser context."""
    context = browser.new_context()
    tab = context.new_page()
    _sign_in(tab, portal_server)
    yield tab
    context.close()


@pytest.fixture
def anonymous_page(browser: Any, portal_server: PortalServer) -> Iterator[Any]:
    """A page with no session, for the signed-out state."""
    context = browser.new_context()
    tab = context.new_page()
    yield tab
    context.close()


def _sign_in(tab: Any, server: PortalServer) -> None:
    state, _url = server.oidc.begin()
    code = server.idp.authorize(
        code_challenge=code_challenge_for(server.oidc._pending[state].verifier),
        subject="alice",
        claims={"groups": ["platform"]},
    )
    tab.goto(f"{server.base}/callback?code={code}&state={state}")


def audit(tab: Any) -> list[dict[str, Any]]:
    """Run the pinned axe ruleset and return the violations.

    Returns rather than asserts, so a row can name *which* criteria failed on *which* page.
    A gate that says only "failed" sends someone hunting through a whole interface.
    """
    tab.add_script_tag(content=AXE.read_text())
    violations: list[dict[str, Any]] = tab.evaluate(
        """async (tags) => {
            const result = await axe.run(document, {
                runOnly: { type: 'tag', values: tags }
            });
            return result.violations.map(v => ({
                id: v.id, impact: v.impact, help: v.help, nodes: v.nodes.length
            }));
        }""",
        AXE_TAGS,
    )
    return violations


def describe(violations: list[dict[str, Any]]) -> str:
    """A failure message someone can act on without opening the browser themselves."""
    return "; ".join(
        f"{v['id']} ({v['impact']}, {v['nodes']} node(s)): {v['help']}" for v in violations
    )


__all__ = ["AXE_TAGS", "PortalServer", "audit", "describe"]
