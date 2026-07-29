# SPDX-License-Identifier: Apache-2.0
"""The portal: a thin client of the northbound API.

**Every capability here is the API's.** This app renders pages and relays operations; it
makes no authorization decision, holds no credential, and reaches nothing the catalogue
does not expose. That is ADR-0034's thin-client rule, and it is built structurally rather
than promised: the only HTTP client in this package is `relay.py`, and the browser receives
rendered state instead of machinery.

**Routes here are not operations.** Nothing this app serves appears in the operation
snapshot, and that is correct — the portal is a *consumer* of the catalogue, not a third
implementation of it. Its conformance obligation is containment ("does it add anything at
all"), asserted by comparing what the relay reached against what the catalogue exposes.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from surfaces.portal.events import thread_event_stream
from surfaces.portal.oidc import LoginRefused, OidcClient
from surfaces.portal.relay import ApiRelay
from surfaces.portal.session import COOKIE_NAME, SessionStore, cookie_attributes

TEMPLATES = Path(__file__).parent / "templates"
STATIC = Path(__file__).parent / "static"

#: How long a portal session lasts when the token carries no usable expiry.
FALLBACK_SESSION_LIFETIME = timedelta(hours=1)


def create_portal(
    *,
    relay: ApiRelay,
    oidc: OidcClient,
    sessions: SessionStore | None = None,
) -> FastAPI:
    """Build the portal with its collaborators supplied rather than imported.

    The same rule the API's assembly follows: a surface that reached for its own relay or
    built its own client could be stood up in a test with different security properties
    than it has in production.
    """
    app = FastAPI(title="Enterprise Agent Harness Portal", docs_url=None, redoc_url=None)
    app.state.relay = relay
    app.state.oidc = oidc
    app.state.sessions = sessions if sessions is not None else SessionStore()
    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    templates = Jinja2Templates(directory=str(TEMPLATES))
    app.state.templates = templates

    def _session(request: Request) -> Any:
        return app.state.sessions.get(request.cookies.get(COOKIE_NAME))

    def _login_redirect(request: Request, next_path: str) -> RedirectResponse:
        _state, url = app.state.oidc.begin(next_path=next_path)
        return RedirectResponse(url, status_code=303)

    # ------------------------------------------------------------------ auth

    @app.get("/login")
    def login(request: Request, next: str = "/") -> RedirectResponse:
        return _login_redirect(request, next)

    @app.get("/callback")
    def callback(request: Request, code: str = "", state: str = "") -> Response:
        """Redeem the code and start a session, or show why not.

        A failed callback renders a page rather than a stack trace: the reasons here are
        all things a person can hit legitimately — a stale tab, a back button, a bookmarked
        callback — and none of them is an error on their part.
        """
        try:
            token, next_path = app.state.oidc.complete(code=code, state=state)
        except LoginRefused as refused:
            return templates.TemplateResponse(
                request=request,
                name="login_failed.html",
                context={"reason": refused.reason},
                status_code=400,
            )

        claims = _claims(token)
        session = app.state.sessions.create(
            subject_user_id=str(claims.get("sub", "")),
            tenant_id=str(claims.get("tenant", "")),
            access_token=token,
            expires_at=_expiry(claims),
        )
        response = RedirectResponse(next_path, status_code=303)
        response.set_cookie(
            COOKIE_NAME,
            session.session_id,
            **cookie_attributes(),  # type: ignore[arg-type]
        )
        return response

    @app.post("/logout")
    def logout(request: Request) -> RedirectResponse:
        app.state.sessions.destroy(request.cookies.get(COOKIE_NAME))
        response = RedirectResponse("/", status_code=303)
        response.delete_cookie(COOKIE_NAME, path="/")
        return response

    # ----------------------------------------------------------------- pages

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> Response:
        session = _session(request)
        if session is None:
            return templates.TemplateResponse(request=request, name="signed_out.html", context={})

        threads = app.state.relay.request("GET", "/threads", token=session.access_token)
        return templates.TemplateResponse(
            request=request,
            name="threads.html",
            context={
                "threads": (threads.payload or {}).get("threads", []) if threads.ok else [],
                "reachable": threads.reachable,
                "refused": not threads.ok and threads.reachable,
            },
        )

    @app.post("/threads")
    def new_thread(request: Request) -> Response:
        session = _session(request)
        if session is None:
            return _login_redirect(request, "/")
        created = app.state.relay.request("POST", "/threads", token=session.access_token)
        if not created.ok:
            return templates.TemplateResponse(
                request=request,
                name="refused.html",
                context={"what": "start a conversation", "response": created},
                status_code=created.status or 503,
            )
        return RedirectResponse(f"/threads/{created.payload['thread_id']}", status_code=303)

    @app.get("/threads/{thread_id}", response_class=HTMLResponse)
    def thread(request: Request, thread_id: str) -> Response:
        session = _session(request)
        if session is None:
            return _login_redirect(request, f"/threads/{thread_id}")

        detail = app.state.relay.request("GET", f"/threads/{thread_id}", token=session.access_token)
        if not detail.ok:
            return templates.TemplateResponse(
                request=request,
                name="refused.html",
                context={"what": "open this conversation", "response": detail},
                status_code=detail.status or 503,
            )
        definitions = app.state.relay.request(
            "GET", "/agent-definitions", token=session.access_token
        )
        turns = _with_run_state(app.state.relay, session.access_token, detail.payload["turns"])
        return templates.TemplateResponse(
            request=request,
            name="thread.html",
            context={
                "thread": detail.payload["thread"],
                "turns": turns,
                "definitions": (definitions.payload or {}).get("definitions", [])
                if definitions.ok
                else [],
                "definitions_reachable": definitions.reachable,
            },
        )

    @app.post("/threads/{thread_id}/turns")
    def send(
        request: Request,
        thread_id: str,
        message: str = Form(...),
        agent_definition_id: str = Form(""),
    ) -> Response:
        session = _session(request)
        if session is None:
            return _login_redirect(request, f"/threads/{thread_id}")

        body: dict[str, Any] = {"message": message}
        if agent_definition_id:
            body["agent_definition_id"] = agent_definition_id
        sent = app.state.relay.request(
            "POST",
            f"/threads/{thread_id}/turns",
            token=session.access_token,
            json_body=body,
        )
        if not sent.ok:
            return templates.TemplateResponse(
                request=request,
                name="refused.html",
                context={"what": "send that message", "response": sent},
                status_code=sent.status or 503,
            )
        return RedirectResponse(f"/threads/{thread_id}", status_code=303)

    @app.get("/threads/{thread_id}/delete", response_class=HTMLResponse)
    def confirm_delete(request: Request, thread_id: str) -> Response:
        """Ask first, and say what deletion does and does not do.

        A person deleting a conversation is entitled to know that the record survives —
        stating it here rather than in a footnote is what makes ADR-0051's cost informed
        at the moment it matters.
        """
        session = _session(request)
        if session is None:
            return _login_redirect(request, f"/threads/{thread_id}")
        return templates.TemplateResponse(
            request=request, name="delete_confirm.html", context={"thread_id": thread_id}
        )

    @app.post("/threads/{thread_id}/delete")
    def delete(request: Request, thread_id: str) -> Response:
        session = _session(request)
        if session is None:
            return _login_redirect(request, "/")
        removed = app.state.relay.request(
            "DELETE", f"/threads/{thread_id}", token=session.access_token
        )
        if not removed.ok:
            return templates.TemplateResponse(
                request=request,
                name="refused.html",
                context={"what": "delete this conversation", "response": removed},
                status_code=removed.status or 503,
            )
        return RedirectResponse("/", status_code=303)

    @app.post("/runs/{run_id}/stop")
    def stop(request: Request, run_id: str, thread_id: str = Form(...)) -> Response:
        """Stop through the catalogue's own operation. No thread-local stop exists."""
        session = _session(request)
        if session is None:
            return _login_redirect(request, f"/threads/{thread_id}")
        stopped = app.state.relay.request(
            "POST", f"/runs/{run_id}/stop", token=session.access_token
        )
        if not stopped.ok:
            return templates.TemplateResponse(
                request=request,
                name="refused.html",
                context={"what": "stop that run", "response": stopped},
                status_code=stopped.status or 503,
            )
        return RedirectResponse(f"/threads/{thread_id}", status_code=303)

    # ------------------------------------------------------------------ live

    @app.get("/threads/{thread_id}/events")
    def events(request: Request, thread_id: str) -> Response:
        """Server-sent state changes, sourced entirely from catalogued reads.

        **Cadence, not capability.** Every byte here comes from `get_run` and
        `get_run_result` made with this person's token; a refusal ends the stream. The
        portal computes nothing and authorizes nothing — this exists so a person does not
        refresh, which is a requirement about them rather than about the platform.
        """
        session = _session(request)
        if session is None:
            return Response(status_code=401)
        return thread_event_stream(
            relay=app.state.relay, token=session.access_token, thread_id=thread_id
        )

    return app


def _with_run_state(
    relay: ApiRelay, token: str, turns: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Join each dispatched turn's run state and result at read time.

    Not stored on the turn, for the reason 011 established: the checkpoint is the one
    writer of a run's state, and a second record of it would eventually disagree.
    """
    enriched: list[dict[str, Any]] = []
    for turn in turns:
        item = dict(turn)
        run_id = turn.get("run_id")
        if run_id:
            state = relay.request("GET", f"/runs/{run_id}", token=token)
            item["run"] = state.payload if state.ok else None
            result = relay.request("GET", f"/runs/{run_id}/result", token=token)
            # The three dispositions 011 established, kept distinguishable rather than
            # collapsed: not finished, produced a result, ended without one.
            item["result"] = result.payload if result.ok else None
            item["result_status"] = result.status
        enriched.append(item)
    return enriched


def _claims(token: str) -> dict[str, Any]:
    """Read the token's claims without verifying it.

    **Deliberately unverified, and safe only because of what it is used for.** The API
    verifies this token on every single request; the portal reads it purely to label the
    session and choose an expiry. Verifying here would mean the portal holding JWKS and an
    issuer — a second authentication authority, which is precisely what ADR-0033 forbids.
    Nothing is authorized on the basis of what this returns.
    """
    import base64
    import json

    try:
        payload = token.split(".")[1]
        padded = payload + "=" * (-len(payload) % 4)
        parsed: dict[str, Any] = json.loads(base64.urlsafe_b64decode(padded))
        return parsed
    except Exception:  # noqa: BLE001 — an unreadable token still gets a bounded session
        return {}


def _expiry(claims: dict[str, Any]) -> datetime:
    """The token's own expiry, honoured and never extended."""
    raw = claims.get("exp")
    if isinstance(raw, int | float):
        return datetime.fromtimestamp(float(raw), tz=UTC)
    return datetime.now(UTC) + FALLBACK_SESSION_LIFETIME


__all__ = ["create_portal"]
