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
from tests.harness.api_fixtures import (
    available_credential,
    qualified_ask_authority,
    surface_under_test,
)

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


class _Answers:
    """An ask provider that cites the corpus, so the ANSWERED page state is reachable (028).

    This gate is about the page, not the platform — everything behind the portal is doubled
    already. Without a provider the ask page could only ever be audited in its refused state,
    and the state a person actually reads is the answered one.
    """

    def answer(self, question: str, material: Any) -> list[dict[str, Any]]:
        from core.answering.corpus import Corpus

        if isinstance(material, Corpus):
            document = next(iter(material.documents.values()))
            return [
                {
                    "statement": "An agent presents an attested identity.",
                    "citations": [{"path": document.path, "anchor": next(iter(document.anchors))}],
                }
            ]
        return [
            {
                "statement": "A run was recorded.",
                "references": [{"entry_hash": r.entry_hash} for r in material[:1]],
            }
        ]


def _console_config() -> Any:
    """A console with an endorsement to render, so the lane walks a POPULATED page (045, EL3).

    044's row walks `/settings` as an *operator* and therefore audits the refusal state. That
    is a real page and worth auditing, and it is not the page this feature adds: a refusal
    contains no table, no drift flag and no review control, so a lane that only ever saw it
    would stay green while every element 045 introduces went unchecked. 044's own note says
    exactly this about the page it added — "a gate that does not visit a surface has not
    tested it" — and this is that lesson applied to the surface after it.
    """
    from datetime import UTC, datetime

    from core.answering.endorsed.records import (
        CANDIDATE,
        EndorsedDocument,
        SyncedVersion,
        digest_of_document,
    )
    from surfaces.api.console import ENDORSED_SOURCES_PATH, ConsoleConfig

    record = {
        "data": {
            "data": {
                "acme-standards": {
                    "location": "https://git.example.com/acme/standards",
                    "endorsed_by": "dan@acme.example",
                    "endorsed_at": "2026-08-01T09:00:00+00:00",
                    "adopted_version": "v-one",
                    "adopted_by": "dan@acme.example",
                    "adopted_at": "2026-08-01T09:05:00+00:00",
                },
                # A withdrawn source AND an endorsed-but-unadopted one, because the three
                # states render differently and an audit of one row says nothing about the
                # others.
                "acme-retired": {
                    "location": "https://git.example.com/acme/retired",
                    "endorsed_by": "dan@acme.example",
                    "withdrawn": True,
                },
                "acme-new": {
                    "location": "https://git.example.com/acme/new",
                    "endorsed_by": "dan@acme.example",
                },
            },
            "metadata": {"version": 4},
        }
    }
    sections = {"retention": "Logs are retained for 400 days."}
    documents = {
        "/endorsed/acme-standards/logging.md": EndorsedDocument(
            path="/endorsed/acme-standards/logging.md",
            url="https://git.example.com/acme/standards/logging.md",
            digest=digest_of_document(sections),
            anchors=frozenset(sections),
            sections=dict(sections),
        )
    }

    class _Store:
        def __init__(self) -> None:
            self.versions = {
                "v-one": SyncedVersion(
                    version_id="v-one",
                    tenant_id="acme",
                    source="acme-standards",
                    upstream_tip="abc123",
                    synced_at=datetime(2026, 8, 1, tzinfo=UTC),
                    synced_by="dan@acme.example",
                    state=CANDIDATE,
                    documents=documents,
                )
            }

        def read_version(self, version_id: str, *, verify: bool = True) -> Any:
            return self.versions.get(version_id)

        def write_version(self, version: Any) -> None:
            self.versions[version.version_id] = version

        def mark_adopted(self, **kwargs: Any) -> None:
            return None

    def _sync(**kwargs: Any) -> Any:
        from core.endorsed_sync import SyncOutcome

        version = SyncedVersion(
            version_id="v-two",
            tenant_id="acme",
            source=kwargs["source"],
            upstream_tip="def456",
            synced_at=datetime(2026, 8, 6, tzinfo=UTC),
            synced_by=kwargs["triggered_by"],
            state=CANDIDATE,
            documents={
                **documents,
                "/endorsed/acme-standards/incident.md": EndorsedDocument(
                    path="/endorsed/acme-standards/incident.md",
                    url="https://git.example.com/acme/standards/incident.md",
                    digest=digest_of_document(sections),
                    anchors=frozenset(sections),
                    sections=dict(sections),
                ),
            },
        )
        return version, SyncOutcome(
            version_id="v-two",
            source=kwargs["source"],
            upstream_tip="def456",
            document_count=2,
            uncitable=("preamble.md",),
        )

    return ConsoleConfig(
        read_matrix=lambda: {"schema_version": 1, "cells": []},
        read_versioned=lambda path: record if path == ENDORSED_SOURCES_PATH else None,
        endorsed_store=_Store(),
        sync_source=_sync,
        tenant_id="acme",
    )


@pytest.fixture(scope="session")
def portal_server() -> Iterator[PortalServer]:
    """The real portal as a process, because a browser cannot drive an ASGI object."""
    surface = surface_under_test(
        # 028: arranged so the ask page's ANSWERED state is auditable, not only its refusals.
        ask_provider=_Answers(),
        ask_model="anthropic/claude-opus@5",
        ask_authority=qualified_ask_authority(model="anthropic/claude-opus@5"),
        credential_source=available_credential(),
        console_config=_console_config(),
    )
    # 048: one designed theme. Light is withdrawn; doubling the lane only existed to
    # exercise prefers-color-scheme. One subject is enough — the two-subject split was
    # only to dodge doubled rate limits.
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


#: ONE DESIGNED THEME (048). Light is withdrawn. A leftover light parametrization would
#: be an unverified surface of the kind 034 existed to prevent. One context, dark.
#:
#: 034 doubled the lane over `prefers-color-scheme`. That doubling is gone with the light
#: theme. One subject is enough: the two-subject split existed only because doubling the
#: rows doubled rate-limit counts.


@pytest.fixture
def page(browser: Any, portal_server: PortalServer) -> Iterator[Any]:
    """A fresh, signed-in page. Each row starts from a clean context."""
    context = browser.new_context(color_scheme="dark")
    tab = context.new_page()
    _sign_in(tab, portal_server, subject="alice")
    yield tab
    context.close()


@pytest.fixture
def admin_page(browser: Any, portal_server: PortalServer) -> Iterator[Any]:
    """A signed-in ADMINISTRATOR, which is the only subject the console renders for (045)."""
    context = browser.new_context(color_scheme="dark")
    tab = context.new_page()
    subject = "admin-alice"
    fabric_users = portal_server.surface.identity_fabric.users
    fabric_users.setdefault(subject, fabric_users["alice"])
    _sign_in(tab, portal_server, subject=subject, groups=["platform-admin"])
    yield tab
    context.close()


@pytest.fixture
def anonymous_page(browser: Any, portal_server: PortalServer) -> Iterator[Any]:
    """A page with no session, for the signed-out state."""
    context = browser.new_context(color_scheme="dark")
    tab = context.new_page()
    yield tab
    context.close()


def _sign_in(
    tab: Any, server: PortalServer, *, subject: str = "alice", groups: list[str] | None = None
) -> None:
    state, _url = server.oidc.begin()
    code = server.idp.authorize(
        code_challenge=code_challenge_for(server.oidc._pending[state].verifier),
        subject=subject,
        claims={"groups": groups or ["platform"]},
    )
    tab.goto(f"{server.base}/callback?code={code}&state={state}")


def start_thread_from_home(
    tab: Any,
    server: PortalServer,
    message: str = "hello",
    *,
    agent: str = "",
) -> str:
    """Open a thread from the operator Run surface (``/run``).

    047 made ``GET /`` Build. The agent-picker composer still lives at ``/run``.
    """
    tab.goto(f"{server.base}/run")
    tab.fill("#message", message)
    if agent:
        tab.select_option("#agent", agent)
    tab.click(".run-composer button[type=submit]")
    tab.wait_for_load_state()
    return str(tab.url)


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
