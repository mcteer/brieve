# SPDX-License-Identifier: Apache-2.0
"""028 — a person asks from the portal, and the portal renders without deciding.

**The discipline these rows exist to hold**: the portal relays and renders. It does not route,
does not evaluate governance, does not compute scope, and — the one that erodes quietest — does
not *classify refusals*. The API's refusal sentences are the product of five features making them
precise, each naming a different person to go to. A portal that translated them into friendlier
prose would look better in review and drift the moment a reason code moved, leaving the page
confidently explaining the wrong cause.

**Driven over the real API fixture wherever the outcome is the API's to produce** — the
`_portal_over_api` pattern the other portal rows use, so an answered page is one the platform
actually answered. The four-outcomes rows use a scripted transport instead, because arranging a
vendor fault through the real stack would be arranging it in the wrong place.
"""

from __future__ import annotations

import re
from typing import Any

from fastapi.testclient import TestClient

from surfaces.portal.app import ASK_PATIENCE, create_portal
from surfaces.portal.oidc import OidcClient, code_challenge_for
from surfaces.portal.relay import ApiRelay, ApiResponse
from surfaces.portal.session import COOKIE_NAME
from tests.harness.api_fixtures import (
    available_credential,
    qualified_ask_authority,
    surface_under_test,
)

GUIDANCE_QUESTION = "How does an AI agent obtain an identity with Vault?"
#: Deliberately WITHOUT a time phrase. "last night" resolves to a real window
#: (`window_phrase`), and a record appended at test time falls outside it — the ask then
#: declines correctly and the row would be measuring the clock rather than the rendering.
ESTATE_QUESTION = "Which runs were denied?"
MODEL = "anthropic/claude-opus@5"


def _visible(html: str) -> str:
    return " ".join(re.sub(r"<[^>]*>", " ", html).split())


def _anchors(html: str) -> list[str]:
    """Every href on the page — parsed, because the reference rule is about anchors."""
    return re.findall(r'<a[^>]+href="([^"]*)"', html)


def _answer_block(html: str) -> str:
    """Just the outcome section, so the page's own nav and footer are not evidence."""
    start = html.find('<section class="answer')
    return html[start:] if start >= 0 else ""


class _Answers:
    """A provider that cites the corpus faithfully, so the ANSWERED shape is reachable."""

    def __init__(self) -> None:
        self.calls = 0

    def answer(self, question: str, material: Any) -> list[dict[str, Any]]:
        from core.answering.corpus import Corpus

        self.calls += 1
        if isinstance(material, Corpus):
            document = next(iter(material.documents.values()))
            anchor = next(iter(document.anchors))
            return [
                {
                    "statement": "An agent presents an attested identity.",
                    "citations": [{"path": document.path, "anchor": anchor}],
                }
            ]
        return [
            {
                "statement": "A run was recorded.",
                "references": [{"entry_hash": r.entry_hash} for r in material[:1]],
            }
        ]


def _portal(surface: Any, *, relay: ApiRelay | None = None) -> TestClient:
    """A signed-in portal over the given API surface, using the established pattern."""
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
        redirect_uri="http://testserver/callback",
        authorize_endpoint="http://idp.test/authorize",
        token_endpoint="http://idp.test/token",
        exchange=lambda code, code_verifier: surface.idp.exchange(
            code=code, code_verifier=code_verifier, redirect_uri="http://localhost/callback"
        ),
    )
    portal = TestClient(
        create_portal(
            relay=relay or ApiRelay(base_url="http://api.test", transport=transport),
            oidc=oidc,
        ),
        base_url="http://testserver",
    )
    state, _ = oidc.begin()
    code = surface.idp.authorize(
        code_challenge=code_challenge_for(oidc._pending[state].verifier),  # noqa: SLF001
        subject="alice",
        claims={"groups": ["platform"]},
    )
    signed = portal.get(f"/callback?code={code}&state={state}", follow_redirects=False)
    portal.cookies.set(COOKIE_NAME, str(signed.cookies.get(COOKIE_NAME)))
    return portal


def _answering_surface(**kwargs: Any) -> Any:
    """A surface whose ask path can actually answer: qualified cell, credential in hand."""
    kwargs.setdefault("ask_provider", _Answers())
    kwargs.setdefault("ask_model", MODEL)
    kwargs.setdefault("ask_authority", qualified_ask_authority(model=MODEL))
    kwargs.setdefault("credential_source", available_credential())
    return surface_under_test(**kwargs)


# ------------------------------------------------------------------ T005/T006: the answered page


def test_a_guidance_answer_renders_every_claim_with_a_followable_citation() -> None:
    """FR-006, SC-002 — and asserted on the anchor SET rather than by substring.

    A page that printed the citation as text would satisfy any "is the URL present" check while
    giving the reader nothing to follow. What FR-006 asks for is a link, so the row parses links.
    """
    portal = _portal(_answering_surface())

    page = portal.post("/ask", data={"question": GUIDANCE_QUESTION})

    assert page.status_code == 200
    assert "An agent presents an attested identity." in _visible(page.text)
    hrefs = _anchors(_answer_block(page.text))
    assert hrefs, "the answer block carries no citation link"
    assert all(h.startswith("http") for h in hrefs), f"a citation is not followable: {hrefs}"


def test_an_estate_answer_renders_references_that_are_not_links() -> None:
    """FR-007's failure mode, pinned structurally.

    A record reference is a content hash. Wrapping it in an anchor produces a dead link and
    teaches the reader that references are decorative — which is worse than omitting them,
    because it looks like diligence. The row asserts the full hash is present **and** that the
    answer block contains no anchor at all.
    """
    surface = _answering_surface()
    from core.audit.schema import AuditEventType

    surface.audit.append_event(
        correlation_id="estate-run-1",
        tenant_id="tenant-test",
        event_type=AuditEventType.RUN_START,
        payload={"subject_user_id": "alice"},
    )
    entry_hash = surface.audit.all_entries()[0].entry_hash
    portal = _portal(surface)

    page = portal.post("/ask", data={"question": ESTATE_QUESTION})

    assert page.status_code == 200
    block = _answer_block(page.text)
    assert entry_hash in block, "the reference the claim rests on is not on the page"
    assert _anchors(block) == [], (
        "a record reference was rendered as a link; it resolves to nothing"
    )


def test_a_decline_reads_as_an_answer_and_names_the_door_that_was_opened() -> None:
    """FR-008, SC-002. The platform being honest must not look like the platform failing."""
    portal = _portal(_answering_surface())

    page = portal.post("/ask", data={"question": "What is the capital of France?"})

    text = _visible(page.text)
    assert "neither" in text, "the decline does not name which sources were considered"
    assert "could not be asked" not in text, "a decline rendered as an outage"


# ------------------------------------------------------------------ T005: nothing is spent early


def test_a_signed_out_ask_never_reaches_the_api() -> None:
    """Both routes, both redirects, and zero calls — the transport is the assertion."""
    surface = _answering_surface()
    calls: list[str] = []
    api = TestClient(surface.app)

    def counting(*, method: str, url: str, token: str, json_body: object) -> ApiResponse:
        calls.append(url)
        response = api.request(
            method,
            url.replace("http://api.test", ""),
            json=json_body,
            headers={"Authorization": f"Bearer {token}"},
        )
        return ApiResponse(status=response.status_code, payload=response.json())

    oidc = OidcClient(
        issuer=surface.idp.issuer,
        client_id="portal",
        redirect_uri="http://testserver/callback",
        authorize_endpoint="http://idp.test/authorize",
        token_endpoint="http://idp.test/token",
        exchange=lambda code, code_verifier: surface.idp.exchange(
            code=code, code_verifier=code_verifier, redirect_uri="http://localhost/callback"
        ),
    )
    anonymous = TestClient(
        create_portal(relay=ApiRelay(base_url="http://api.test", transport=counting), oidc=oidc),
        base_url="http://testserver",
    )

    assert anonymous.get("/ask", follow_redirects=False).status_code == 303
    assert (
        anonymous.post("/ask", data={"question": "hi"}, follow_redirects=False).status_code == 303
    )
    assert calls == [], f"a signed-out ask reached the platform: {calls}"


def test_an_empty_question_costs_no_api_call_and_no_model_call() -> None:
    """The cheapest refusal in the feature.

    Relayed, an empty question would spend a governed ask, a vendor call and a trail record to
    be told what the form already knows.
    """
    asked = _Answers()
    surface = _answering_surface(ask_provider=asked)
    portal = _portal(surface)

    page = portal.post("/ask", data={"question": "   "})

    assert page.status_code == 400
    assert "Type a question first" in _visible(page.text)
    assert asked.calls == 0, "an empty question reached a model"
    assert [e for e in surface.audit.all_entries() if str(e.event_type) == "ask_answered"] == []


def test_the_relay_carries_the_signed_in_persons_own_token() -> None:
    """FR-011's portal half. The portal holds no credential — containment asserts that
    separately; this asserts that what it *does* send is the person's."""
    surface = _answering_surface()
    seen: list[str] = []
    api = TestClient(surface.app)

    def recording(*, method: str, url: str, token: str, json_body: object) -> ApiResponse:
        seen.append(token)
        response = api.request(
            method,
            url.replace("http://api.test", ""),
            json=json_body,
            headers={"Authorization": f"Bearer {token}"},
        )
        return ApiResponse(status=response.status_code, payload=response.json())

    portal = _portal(surface, relay=ApiRelay(base_url="http://api.test", transport=recording))
    portal.post("/ask", data={"question": GUIDANCE_QUESTION})

    assert seen, "the ask reached nothing"
    import base64
    import json as jsonlib

    body = seen[-1].split(".")[1]
    claims = jsonlib.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    assert claims["sub"] == "alice", "the relay did not carry the signed-in person's identity"


# ------------------------------------------------------------------ T007: patience, both halves


class _RecordingRelay(ApiRelay):
    """Captures the patience each call carried, at the seam where it is decided."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.seen: list[tuple[str, float | None]] = []

    def request(self, method: str, path: str, **kwargs: Any) -> ApiResponse:
        self.seen.append((path, kwargs.get("timeout")))
        return super().request(method, path, **kwargs)


def test_the_ask_waits_longer_and_nothing_else_does() -> None:
    """SC-004, **both halves** — and the second is the one that matters.

    An implementation that raised the relay's shared default would satisfy "the ask waits long
    enough" and quietly apply an ask's patience to every thread listing, which is the harm the
    ten-second default was chosen to avoid. So the row asserts the listing still carries `None`
    (the relay's own), and fails on the tempting simplification.
    """
    surface = _answering_surface()
    api = TestClient(surface.app)

    def transport(*, method: str, url: str, token: str, json_body: object) -> ApiResponse:
        response = api.request(
            method,
            url.replace("http://api.test", ""),
            json=json_body,
            headers={"Authorization": f"Bearer {token}"},
        )
        return ApiResponse(
            status=response.status_code,
            payload=response.json() if response.content else None,
        )

    relay = _RecordingRelay(base_url="http://api.test", transport=transport)
    portal = _portal(surface, relay=relay)

    portal.post("/ask", data={"question": GUIDANCE_QUESTION})
    portal.get("/")

    patience = dict(relay.seen)
    assert patience["/ask"] == ASK_PATIENCE, "the ask did not carry its own patience"
    assert patience["/threads"] is None, (
        "a thread listing carried an ask's patience — the shared default was widened instead of "
        "one caller stating its exception"
    )


# ------------------------------------------------------------------ T008/T009: the four outcomes


#: The API's own refusal sentences, copied as literals from `surfaces/api/ask.py`
#: (`authorise_ask`'s unbound branch and `obtain_ask_credential`'s absent-source branch).
#:
#: **Literals rather than live imports.** If the API rewords a refusal, the portal still renders
#: whatever arrives and these rows still pass — the fixture is merely stale. Importing them would
#: couple the portal's rows to the API's internals to assert a property the portal does not have.
UNBOUND_DETAIL = (
    "no ask binding is configured for this surface; a configured provider is not a qualification"
)
CREDENTIAL_DETAIL = (
    "no model credential source is configured for this surface; a qualified cell is not "
    "authority to call a vendor"
)
VENDOR_DETAIL = "the model returned no text; this is a provider fault"


def _scripted(status: int, payload: Any) -> TestClient:
    """A portal whose platform answers exactly this, so each outcome is arrangeable."""
    surface = _answering_surface()

    def transport(*, method: str, url: str, token: str, json_body: object) -> ApiResponse:
        if url.endswith("/ask"):
            return ApiResponse(status=status, payload=payload)
        return ApiResponse(status=200, payload={"threads": []})

    return _portal(surface, relay=ApiRelay(base_url="http://api.test", transport=transport))


def test_the_four_outcomes_are_four_distinguishable_pages() -> None:
    """FR-009, FR-010, SC-003.

    Three refusals and an outage. Each renders its own response's words; the four pages differ
    pairwise. Collapsing any two would discard the work 027 did to keep the causes apart, at the
    exact surface a human reads.
    """
    pages = {
        "unbound": _scripted(403, {"detail": UNBOUND_DETAIL}),
        "credential": _scripted(503, {"detail": CREDENTIAL_DETAIL}),
        "vendor": _scripted(503, {"detail": VENDOR_DETAIL}),
        "unreachable": _scripted(0, None),
    }
    rendered = {
        name: _visible(portal.post("/ask", data={"question": GUIDANCE_QUESTION}).text)
        for name, portal in pages.items()
    }

    assert UNBOUND_DETAIL in rendered["unbound"]
    assert CREDENTIAL_DETAIL in rendered["credential"]
    assert VENDOR_DETAIL in rendered["vendor"]
    assert "could not be asked" in rendered["unreachable"]

    outcomes = list(rendered.values())
    assert len(set(outcomes)) == 4, "two outcomes render the same page"


def test_the_portal_renders_the_platforms_words_and_authors_no_cause_of_its_own() -> None:
    """**The row this feature turns on** (research F1).

    The tempting fix is a friendly mapping — `credential_unavailable` becomes a portal-authored
    paragraph about credentials. It reads better in review and drifts the first time a reason
    code is added or reworded, leaving this page confidently explaining a cause that is no longer
    the one that happened.

    So the refusal block must contain the transported sentence and none of the vocabulary such a
    fix would reach for.
    """
    portal = _scripted(503, {"detail": CREDENTIAL_DETAIL})

    page = portal.post("/ask", data={"question": GUIDANCE_QUESTION}).text
    block = _visible(_answer_block(page))

    assert CREDENTIAL_DETAIL in block
    assert "The platform refused this request" not in block, (
        "the ask page fell back to the generic refusal wording, which is the flattening the "
        "feature exists to avoid"
    )
    for invented in ("credential problem", "not qualified", "vendor error", "try again later"):
        assert invented not in block.lower(), (
            f"the portal authored a cause of its own ({invented!r}); it must render the "
            f"platform's words, which is what keeps this page from drifting"
        )


# ------------------------------------------------------------------ T010: the trail


def test_a_portal_ask_is_recorded_under_the_askers_own_identity() -> None:
    """US3, FR-011, SC-005 — observed end to end through the real API.

    The portal has no identity of its own to record (containment asserts it holds no credential),
    and this is the other side of that: what reaches the trail is the signed-in person.
    """
    surface = _answering_surface()
    portal = _portal(surface)

    portal.post("/ask", data={"question": GUIDANCE_QUESTION})

    asks = [e for e in surface.audit.all_entries() if str(e.event_type) == "ask_answered"]
    assert len(asks) == 1, "a portal ask left no record, or left more than one"
    assert asks[0].payload["subject_user_id"] == "alice"


def test_a_refused_portal_ask_is_recorded_too() -> None:
    """A boundary a person can probe without trace is what 022 removed, and the portal is the
    most attractive surface to probe it from."""
    surface = _answering_surface(credential_source=None)
    portal = _portal(surface)

    page = portal.post("/ask", data={"question": GUIDANCE_QUESTION})

    assert page.status_code == 503
    asks = [e for e in surface.audit.all_entries() if str(e.event_type) == "ask_answered"]
    assert [a.payload["disposition"] for a in asks] == ["credential_unavailable"]


def test_the_question_travels_in_the_body_and_never_in_a_url() -> None:
    """FR-013's portal half, and a property this design has by construction rather than by care.

    A question in a query string is a question in every access log, every proxy log and the
    browser's own history — none of which is the append-only trail the platform governs, and all
    of which outlive it. The API deliberately keeps the question out of the record; putting it in
    a URL on the way there would undo that outside the platform's reach.

    The tempting change is making an answer bookmarkable by moving the ask to GET. This row is
    what makes that a decision somebody has to argue for rather than a convenience they add.
    """
    surface = _answering_surface()
    urls: list[str] = []
    api = TestClient(surface.app)

    def watching(*, method: str, url: str, token: str, json_body: object) -> ApiResponse:
        urls.append(url)
        assert json_body == {"question": GUIDANCE_QUESTION}, (
            "the question did not travel in the request body"
        )
        response = api.request(
            method,
            url.replace("http://api.test", ""),
            json=json_body,
            headers={"Authorization": f"Bearer {token}"},
        )
        return ApiResponse(status=response.status_code, payload=response.json())

    portal = _portal(surface, relay=ApiRelay(base_url="http://api.test", transport=watching))
    portal.post("/ask", data={"question": GUIDANCE_QUESTION})

    assert urls == ["http://api.test/ask"], f"the question leaked into a URL: {urls}"


def test_a_hostile_refusal_sentence_is_rendered_as_text() -> None:
    """The one risk that comes with rendering the platform's words verbatim.

    Verbatim means *the sentence*, not *the markup*. The template escapes, so a detail string
    carrying a tag reaches the reader as characters — asserted rather than assumed, because the
    whole feature rests on passing a string through untouched and "untouched" is exactly the
    word that invites an `| safe` filter later.
    """
    portal = _scripted(503, {"detail": "<script>alert(1)</script> was refused"})

    page = portal.post("/ask", data={"question": GUIDANCE_QUESTION}).text

    assert "<script>alert(1)</script>" not in page, "a refusal sentence was rendered as markup"
    assert "&lt;script&gt;" in page, "the refusal sentence did not reach the reader at all"


def test_the_two_surfaces_say_which_one_acts() -> None:
    """The distinction 028 chose separate pages to make **visible rather than explained**.

    Separate pages were the decision; labels that both read as "talk to the thing" defeated the
    reason for it. The first person to use this went looking for the ask on a thread page and
    found the composer's agent picker instead — which is the failure exactly, since that picker
    starts governed runs and the ask can never start anything.

    So both surfaces state their consequence, and this row keeps them from drifting back into
    synonyms. It asserts the *property* — each page says whether anything happens — rather than
    pinning particular wording, so the copy can improve without the guarantee eroding.
    """
    portal = _portal(_answering_surface())

    ask = _visible(portal.get("/ask").text)
    run = _visible(portal.get("/").text)

    assert "never acts" in ask, "the ask page does not say that nothing happens"
    assert "acts on your behalf" in run, "the run page does not say that something does"

    # And each points at the other, so landing on the wrong one is a click rather than a search.
    assert 'href="/"' in portal.get("/ask").text
    assert 'href="/ask"' in portal.get("/").text
