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

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Final

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markupsafe import Markup, escape

from surfaces.portal.events import thread_event_stream
from surfaces.portal.highlight import highlight_code
from surfaces.portal.oidc import LoginRefused, OidcClient
from surfaces.portal.relay import ApiRelay, ApiResponse
from surfaces.portal.session import COOKIE_NAME, SessionStore, cookie_attributes

TEMPLATES = Path(__file__).parent / "templates"
STATIC = Path(__file__).parent / "static"

#: Opening fence for a model-authored code block in a primary answer (046).
_FENCE: Final[str] = "```"

#: Inline emphasis the model already wrote — presentation only. Escape first, then wrap.
_BOLD: Final[re.Pattern[str]] = re.compile(r"\*\*(.+?)\*\*")
_INLINE_CODE: Final[re.Pattern[str]] = re.compile(r"`([^`\n]+)`")


def answer_segments(text: object) -> tuple[dict[str, str], ...]:
    """Split a primary answer into prose and fenced-code segments for display.

    **Presentation, not classification** (ADR-0034). The model already put ``` fences in the
    answer; this only chooses HTML shapes so a Terraform sketch reads as a code block rather
    than as backticks mixed into a prose blob. Nothing about grounding or disposition is
    decided here — unfenced text stays prose; inline emphasis is applied by `answer_markup`.
    """
    raw = str(text or "")
    if not raw:
        return ()
    segments: list[dict[str, str]] = []
    prose: list[str] = []
    lines = raw.splitlines(keepends=True)
    index = 0

    def _flush_prose() -> None:
        body = "".join(prose).strip("\n")
        prose.clear()
        if body.strip():
            segments.append({"kind": "prose", "lang": "", "text": body})

    while index < len(lines):
        line = lines[index]
        if line.startswith(_FENCE):
            _flush_prose()
            lang = line[len(_FENCE) :].strip()
            index += 1
            code: list[str] = []
            while index < len(lines) and not lines[index].startswith(_FENCE):
                code.append(lines[index])
                index += 1
            segments.append(
                {
                    "kind": "code",
                    "lang": lang,
                    "text": "".join(code).rstrip("\n"),
                }
            )
            if index < len(lines) and lines[index].startswith(_FENCE):
                index += 1
            continue
        prose.append(line)
        index += 1
    _flush_prose()
    if not segments and raw.strip():
        return ({"kind": "prose", "lang": "", "text": raw.rstrip("\n")},)
    return tuple(segments)


def answer_markup(text: object) -> Markup:
    """Escape prose, then honour the model's own ``**bold**`` and `` `code` `` markers.

    **Not a markdown engine.** Full markdown would pull a dependency into the portal for a
    shape the model rarely uses beyond emphasis and inline identifiers. Unmatched markers
    stay visible as text; nothing here invents structure the answer did not already write.
    """
    escaped = str(escape(str(text or "")))
    emphasised = _BOLD.sub(r"<strong>\1</strong>", escaped)
    return Markup(_INLINE_CODE.sub(r"<code>\1</code>", emphasised))


#: How long a portal session lasts when the token carries no usable expiry.
FALLBACK_SESSION_LIFETIME = timedelta(hours=1)

#: How long the portal waits for an answer, and **only** for an answer.
#:
#: Measured rather than chosen: a real question through the deployed surface on 2026-08-02 took
#: roughly two minutes, because the model reasons before it answers and retrieval runs over an
#: 856K corpus. 180 seconds is that plus headroom, and it is the same allowance the demonstration
#: used.
#:
#: **Passed per call, so no other page becomes slower.** The relay's own ten seconds exists
#: because a page that hangs teaches people to reload; extending it globally would apply an ask's
#: patience to a thread listing and turn one slow request into several. A row asserts both halves
#: — that an ask carries this, and that a listing in the same session does not.
ASK_PATIENCE = 180.0

#: Short labels for the agent picker — presentation only; the posted value stays the id.
_AGENT_LABELS: dict[str, str] = {
    "planner": "Plan",
    "applier": "Apply",
    "demo": "Demo",
    "authoring": "Author",
}


def agent_label(definition_id: str) -> str:
    """A definition id in words someone would pick from a menu.

    PRESENTATION, NOT CLASSIFICATION — the id is what the form submits and what the API
    expects; this affects only what the dropdown shows.
    """
    stem = (
        definition_id.removesuffix("-agent") if definition_id.endswith("-agent") else definition_id
    )
    if stem in _AGENT_LABELS:
        return _AGENT_LABELS[stem]
    return stem.replace("-", " ").title()


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

    def _readable_instant(value: Any) -> str:
        """An instant in words. `2026-08-05T03:46:53.836216Z` is a machine's way of saying it.

        PRESENTATION, NOT CLASSIFICATION — the thin-client rule (ADR-0034) forbids the portal
        deciding what a value MEANS, and this decides only how it reads. The exact value is
        never discarded: the template keeps it in the element's `datetime` attribute, so the
        precision an auditor needs is still on the page and still machine-readable.

        Rendered in UTC because that is the zone the platform recorded it in, and guessing at
        the reader's would be the portal claiming to know something it was not told. Anything
        unparseable comes back untouched rather than swallowed — a surface that hides a value
        it did not understand is worse than one that shows it raw.
        """
        try:
            moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return str(value)
        return f"{moment.day} {moment:%B %Y} at {moment:%H:%M} UTC"

    templates.env.filters["readable_instant"] = _readable_instant
    templates.env.filters["agent_label"] = agent_label
    templates.env.filters["answer_segments"] = answer_segments
    templates.env.filters["answer_markup"] = answer_markup
    templates.env.filters["highlight_code"] = highlight_code
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

        threads, reachable, refused = _threads(session)
        definitions, definitions_reachable = _definitions(session)
        return templates.TemplateResponse(
            request=request,
            name="threads.html",
            context={
                "thread": None,
                "turns": [],
                "threads": threads,
                "reachable": reachable,
                "refused": refused,
                "definitions": definitions,
                "definitions_reachable": definitions_reachable,
            },
        )

    # --------------------------------------------------------------- settings (044)

    @app.get("/settings", response_class=HTMLResponse)
    def settings(request: Request) -> Response:
        """The admin console, rendered from what the API returned and nothing else.

        **No governance logic here, and none possible.** The page has no view of the trust
        fabric, no credential, and no way to distinguish a permitted change from a refused one
        except by what the API said. That is the thin-client rule (Principle II) doing real
        work rather than being asserted: a reader looking for the decision will not find it
        in this file, because it is not here.

        A non-admin gets the API's 403 rendered as a refusal — the platform answering, not a
        portal error. `relay.py`'s docstring already draws that line and this page keeps it.
        """
        session = _session(request)
        if session is None:
            return templates.TemplateResponse(request=request, name="signed_out.html", context={})

        posture = app.state.relay.request(
            "GET", "/console/configuration", token=session.access_token
        )
        return templates.TemplateResponse(
            request=request,
            name="settings.html",
            context={
                "posture": posture.payload if posture.ok else {},
                "reachable": posture.reachable,
                "refused": not posture.ok and posture.reachable,
            },
        )

    @app.post("/settings/endorsed/{source}/review", response_class=HTMLResponse)
    def review_endorsed(request: Request, source: str) -> Response:
        """Show what changed upstream, against what answers currently rest on (045, US3).

        **POST, not GET**, and that is not REST pedantry: opening this page syncs a candidate
        version, which reaches a customer's repository. A GET that performed egress would be
        followed by every link prefetcher and crawler that ever saw the URL.

        No governance logic here either. The API syncs, compares, and decides which of the
        three sync failures occurred; this renders what came back.
        """
        session = _session(request)
        if session is None:
            return templates.TemplateResponse(request=request, name="signed_out.html", context={})

        review = app.state.relay.request(
            "POST",
            f"/console/endorsed-sources/{source}/review",
            token=session.access_token,
        )
        return templates.TemplateResponse(
            request=request,
            name="endorsed_review.html",
            context={
                "source": source,
                "review": review.payload if review.ok else {},
                "reachable": review.reachable,
                "refused": review.status == 403 and review.reachable,
                # A sync failure is neither a refusal nor an outage of ours — it is the
                # customer's source not being readable, and the page keeps the distinction the
                # API drew rather than flattening all three into "something went wrong".
                "failed": review.status == 502,
                "failure": (review.payload or {}).get("detail", ""),
            },
        )

    @app.post("/settings/endorsed", response_class=HTMLResponse)
    def endorse_source(
        request: Request, source: str = Form(""), location: str = Form("")
    ) -> Response:
        """Endorse a source of the customer's own documents (045, US1).

        **The console had no control for this and the API route existed the whole time.** 045
        shipped endorse, withdraw and adopt as routes, and a page that could only read — so the
        one act the feature is named for could not be performed from the interface. Same shape
        as `/settings` being unlinked, one level in, and the navigation gate could not see it
        because it checks pages rather than operations.

        No governance logic here, like every other portal route: the API composes the record,
        stamps who and when from the authenticated subject, and the fabric decides. This
        collects two strings and relays them.
        """
        return _endorsement_operation(
            request, operation="endorse", source=source, location=location
        )

    @app.post("/settings/endorsed/{source}/adopt", response_class=HTMLResponse)
    def adopt_version(request: Request, source: str, version_id: str = Form("")) -> Response:
        """Adopt a reviewed version, which is what moves the ground answers rest on.

        Reached from the review page, carrying the candidate the administrator was looking at —
        so what they adopt is what they saw. A control that adopted "the latest" would let the
        source move between the review and the click.
        """
        return _endorsement_operation(
            request, operation="adopt", source=source, version_id=version_id
        )

    @app.post("/settings/endorsed/{source}/withdraw", response_class=HTMLResponse)
    def withdraw_source(request: Request, source: str) -> Response:
        """Stop trusting a source. Citations into it stop resolving at the next question."""
        return _endorsement_operation(request, operation="withdraw", source=source)

    def _endorsement_operation(
        request: Request,
        *,
        operation: str,
        source: str,
        location: str = "",
        version_id: str = "",
    ) -> Response:
        """Relay one endorsement act and render the settings page around its outcome.

        **The outcome is rendered, never swallowed.** 044's whole point is that the fabric
        answers one of three ways — applied, awaiting approval, refused — and a page that
        redirected on success would collapse the first two into each other. So the settings
        page comes back carrying what happened.
        """
        session = _session(request)
        if session is None:
            return templates.TemplateResponse(request=request, name="signed_out.html", context={})

        result = app.state.relay.request(
            "POST",
            "/console/endorsed-sources",
            token=session.access_token,
            json_body={
                "operation": operation,
                "source": source,
                "location": location,
                "version_id": version_id,
            },
        )
        posture = app.state.relay.request(
            "GET", "/console/configuration", token=session.access_token
        )
        return templates.TemplateResponse(
            request=request,
            name="settings.html",
            context={
                "posture": posture.payload if posture.ok else {},
                "reachable": posture.reachable,
                "refused": not posture.ok and posture.reachable,
                # What the fabric did, in the vocabulary the page already renders for a change.
                "outcome": {
                    "operation": operation,
                    "source": source,
                    "state": (result.payload or {}).get("state", ""),
                    "message": (result.payload or {}).get(
                        "message", (result.payload or {}).get("detail", "")
                    ),
                    "ok": result.ok,
                    "pending": result.status == 202,
                },
            },
        )

    # ------------------------------------------------------------------- ask

    def _rendered(exchanges: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Stored exchanges in the shape `_outcome.html` already renders.

        The template speaks the RELAY's vocabulary — reachable, ok, payload — because that is
        what a live answer arrives as. A stored exchange is the same payload after the fact, so
        it is wrapped rather than given a second template: one renderer is the property this
        feature keeps paying for, and a `{% if stored %}` arm in the outcome would be the
        second one wearing a condition.
        """
        return [
            {
                "question": exchange.get("question", ""),
                "rendered": ApiResponse(status=200, payload=exchange.get("outcome") or {}),
            }
            for exchange in exchanges
        ]

    def _conversations(session: Any) -> list[dict[str, Any]]:
        """This person's own conversations for the rail, or nothing to show.

        A list the platform could not read is rendered as absent rather than as empty: the API
        answers 503 for an unreadable store precisely so nobody is told they have no
        conversations when the truth is that nobody could look.
        """
        listed = app.state.relay.request("GET", "/ask-conversations", token=session.access_token)
        if not listed.reachable or not listed.ok:
            return []
        conversations: list[dict[str, Any]] = (listed.payload or {}).get("conversations", [])
        return conversations

    def _threads(session: Any) -> tuple[list[dict[str, Any]], bool, bool]:
        """This person's agent threads for the rail, and whether the list could be read."""
        listed = app.state.relay.request("GET", "/threads", token=session.access_token)
        if not listed.reachable:
            return [], False, False
        if not listed.ok:
            return [], True, True
        threads: list[dict[str, Any]] = (listed.payload or {}).get("threads", [])
        return threads, True, False

    def _definitions(session: Any) -> tuple[list[dict[str, Any]], bool]:
        listed = app.state.relay.request("GET", "/agent-definitions", token=session.access_token)
        if not listed.ok:
            return [], listed.reachable
        definitions: list[dict[str, Any]] = (listed.payload or {}).get("definitions", [])
        return [
            {
                **definition,
                "label": agent_label(str(definition.get("agent_definition_id", ""))),
            }
            for definition in definitions
        ], listed.reachable

    @app.get("/ask", response_class=HTMLResponse)
    def ask_form(request: Request) -> Response:
        """A new conversation: the composer, and the rail of earlier ones.

        A thread is where turns **act**; an ask never does (ADR-0039). Putting them in one
        surface would make that difference a property of which button was pressed — legible to
        whoever wrote the code and invisible to the person using it. 035 gives asking a
        transcript of its own and still keeps it a different room.
        """
        session = _session(request)
        if session is None:
            return _login_redirect(request, "/ask")
        return templates.TemplateResponse(
            request=request,
            name="ask.html",
            context={"conversations": _conversations(session), "exchanges": []},
        )

    @app.get("/ask/{conversation_id}", response_class=HTMLResponse)
    def ask_conversation(request: Request, conversation_id: str) -> Response:
        """One conversation, reopened — every exchange as the person left it.

        The stored outcome is rendered rather than re-derived, so what comes back is what they
        saw, not what the corpus would say about the same question today.
        """
        session = _session(request)
        if session is None:
            return _login_redirect(request, f"/ask/{conversation_id}")

        found = app.state.relay.request(
            "GET", f"/ask-conversations/{conversation_id}", token=session.access_token
        )
        if not found.reachable or not found.ok:
            # The API's verdict, carried. A conversation that is not this person's answers 404
            # there and the portal must not soften that into an empty page.
            return templates.TemplateResponse(
                request=request,
                name="ask.html",
                context={
                    "conversations": _conversations(session),
                    "exchanges": [],
                    "missing": True,
                },
                status_code=found.status if found.reachable else 503,
            )
        payload = found.payload or {}
        return templates.TemplateResponse(
            request=request,
            name="ask.html",
            context={
                "conversations": _conversations(session),
                "conversation_id": conversation_id,
                "title": payload.get("title", ""),
                "exchanges": _rendered(payload.get("exchanges", [])),
            },
        )

    @app.get("/ask/{conversation_id}/delete", response_class=HTMLResponse)
    def ask_delete_confirm(request: Request, conversation_id: str) -> Response:
        """Ask before deleting, on its own page — the thread pattern, not the thread template."""
        session = _session(request)
        if session is None:
            return _login_redirect(request, f"/ask/{conversation_id}/delete")
        found = app.state.relay.request(
            "GET", f"/ask-conversations/{conversation_id}", token=session.access_token
        )
        if not found.reachable or not found.ok:
            return templates.TemplateResponse(
                request=request,
                name="ask.html",
                context={"conversations": [], "exchanges": [], "missing": True},
                status_code=found.status if found.reachable else 503,
            )
        payload = found.payload or {}
        return templates.TemplateResponse(
            request=request,
            name="ask_delete_confirm.html",
            context={
                "conversation_id": conversation_id,
                "title": payload.get("title", ""),
                "exchanges": len(payload.get("exchanges", [])),
            },
        )

    @app.post("/ask/{conversation_id}/delete")
    def ask_delete(request: Request, conversation_id: str) -> Response:
        """Delete, then take the person somewhere that still exists."""
        session = _session(request)
        if session is None:
            return _login_redirect(request, "/ask")
        app.state.relay.request(
            "DELETE", f"/ask-conversations/{conversation_id}", token=session.access_token
        )
        return RedirectResponse("/ask", status_code=303)

    @app.post("/ask")
    def ask(request: Request, question: str = Form("")) -> Response:
        """Relay the question and render what came back. **Decide nothing.**

        The portal does not route between guidance and estate, does not evaluate governance,
        does not compute scope, and does not classify refusals. It sends the person's own token
        and renders the platform's answer — which is ADR-0034's thin-client rule at the one place
        this feature could most easily have broken it.
        """
        session = _session(request)
        if session is None:
            return _login_redirect(request, "/ask")

        # WHOLE PAGE OR JUST THE OUTCOME — the same render either way.
        #
        # `portal-ask.js` posts this form without navigating and swaps the result into the page,
        # so an answer that takes a minute no longer costs a person their scroll position and a
        # blank tab. It sends this header; a browser with no JavaScript sends nothing and gets
        # the full page, which is why the form still works with the script removed.
        #
        # The branch chooses an ENVELOPE, never a rendering. Both arms end at `_outcome.html`,
        # because two templates that agree today are two templates that drift, and the one that
        # drifts is the one nobody opens without JavaScript.
        page = "_exchange.html" if request.headers.get("x-portal-fragment") else "ask.html"

        asked = question.strip()
        conversation_id = (request.query_params.get("conversation_id") or "").strip()
        if not asked:
            # THE CHEAPEST REFUSAL IN THE FEATURE, and it costs no API call and no model call.
            # An empty question relayed would spend a governed ask, a vendor call and a trail
            # record to be told what this line already knows.
            return templates.TemplateResponse(
                request=request,
                name="_notice.html" if page == "_exchange.html" else page,
                context={
                    "empty": True,
                    "conversations": _conversations(session) if page == "ask.html" else [],
                    "exchanges": [],
                    "conversation_id": conversation_id,
                },
                status_code=400,
            )

        # Fetched before the ask and only for a whole page. The fragment envelope re-renders one
        # exchange and never the rail, so a follow-up costs exactly one call — and doing it
        # first keeps the ask itself the last thing this handler does, which is what the
        # containment session reads.
        rail = _conversations(session) if page == "ask.html" else []

        body: dict[str, Any] = {"question": asked}
        if conversation_id:
            body["conversation_id"] = conversation_id
        answered = app.state.relay.request(
            "POST",
            "/ask",
            token=session.access_token,
            json_body=body,
            # The one call in the portal that waits longer, and only this one.
            timeout=ASK_PATIENCE,
        )
        # The conversation this exchange landed in — the API's answer, not the portal's guess.
        # A first ask has no id going in and gets one coming back, which is what the composer
        # posts to from then on.
        landed = (answered.payload or {}).get("conversation_id", conversation_id)
        return templates.TemplateResponse(
            request=request,
            name=page,
            context={
                "question": asked,
                "response": answered,
                "conversation_id": landed,
                "conversations": rail,
                "exchanges": [],
            },
            # The API's own status, carried rather than reinterpreted. A refusal is an answer.
            status_code=answered.status if answered.reachable else 503,
        )

    @app.post("/threads")
    def new_thread(
        request: Request,
        message: str = Form(""),
        agent_definition_id: str = Form(""),
    ) -> Response:
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
        thread_id = created.payload["thread_id"]
        if message.strip():
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
        threads, reachable, refused = _threads(session)
        definitions, definitions_reachable = _definitions(session)
        turns = _with_run_state(app.state.relay, session.access_token, detail.payload["turns"])
        return templates.TemplateResponse(
            request=request,
            name="threads.html",
            context={
                "thread": detail.payload["thread"],
                "turns": turns,
                "threads": threads,
                "reachable": reachable,
                "refused": refused,
                "definitions": definitions,
                "definitions_reachable": definitions_reachable,
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
