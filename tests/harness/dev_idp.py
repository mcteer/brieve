# SPDX-License-Identifier: Apache-2.0
"""A **dev-only** OIDC provider, served over HTTP so a browser can walk the flow.

**This is not production code and must never become it.** It is the same
`FakeOIDCProvider` every hermetic row uses, given a socket — because the portal's login is
a browser redirect, and a browser cannot redirect to a Python object. The customer's IdP is
the one thing outside this platform's boundary (008's recorded rule), so it is the one
thing this repository doubles; a real deployment points `OIDC_ISSUER` at the
organization's own provider and nothing else changes.

**It authenticates nobody.** `/authorize` issues a code for whatever subject the query
string names, with no password and no consent. That is exactly why it may never be
deployed: it is a machine for minting tokens for anyone who asks. It lives in `tests/`
rather than `src/` so that the packaging boundary says so too — `pyproject.toml` publishes
`core`, `adapters`, and `surfaces`, and this is in none of them.
"""

from __future__ import annotations

import json
import os
import secrets
import urllib.parse
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from tests.harness.fake_oidc_provider import AuthorizationRefused, FakeOIDCProvider

#: The banner every response carries, so a stray screenshot of this in a real environment
#: is self-incriminating.
#: ASCII only, and the hyphen is load-bearing. This value goes into an HTTP header, and
#: header values must encode as latin-1 — an em-dash raised `UnicodeEncodeError` inside the
#: handler, so **every** request to this provider died before returning anything. The
#: warning is the same warning either way; the punctuation was the whole defect.
#:
#: Found on 2026-07-31 by 017's deployment lane, which is the first thing that ever ran
#: `portal-up`'s development-provider path in CI. It had been broken in place, and the JSON
#: body below carries the same text where a wider character would have been harmless.
DEV_ONLY = "DEVELOPMENT IDENTITY PROVIDER - authenticates nobody, never deploy"


class _Handler(BaseHTTPRequestHandler):
    provider: FakeOIDCProvider
    issuer: str

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003 - stdlib signature
        # Quiet: allocation logs are for the platform's own output, and every request here
        # is a browser redirect nobody needs narrated.
        return

    def do_GET(self) -> None:  # noqa: N802 - stdlib signature
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)

        # BOTH DISCOVERY PATHS, ONE BODY. An MCP client probes
        # `/.well-known/oauth-authorization-server` first; this server answered 404 there while
        # serving only the OpenID Connect path, which is where an editor's discovery stopped —
        # observed in the surface's own access log. They describe the same authorization server,
        # so one body is served twice: two bodies could drift, one cannot.
        if parsed.path in (
            "/.well-known/openid-configuration",
            "/.well-known/oauth-authorization-server",
        ):
            self._json(self._discovery())
        elif parsed.path == "/jwks":
            self._json(self.provider.jwks())
        elif parsed.path == "/authorize":
            self._authorize(query)
        else:
            self._json({"error": "not_found", "_warning": DEV_ONLY}, status=404)

    def _discovery(self) -> dict[str, Any]:
        """What this provider says about itself. Built once, served at both paths."""
        return {
            "issuer": self.issuer,
            "authorization_endpoint": f"{self.issuer}/authorize",
            "token_endpoint": f"{self.issuer}/token",
            "jwks_uri": f"{self.issuer}/jwks",
            # Without this a client holding no `client_id` has nowhere to obtain one, and its
            # discovery ends here (RFC 7591). Its absence is why an editor could find this
            # provider and still not begin a flow.
            "registration_endpoint": f"{self.issuer}/register",
            # REQUIRED BY RFC 8414, and its absence is not cosmetic: a real editor fetched this
            # document, validated it, and refused the connection with "expected array, received
            # undefined". Discovery reaching a client is not the same as a client accepting it,
            # and only connecting one showed the difference.
            "response_types_supported": ["code"],
            # The flow this provider actually implements. Omitting it makes a client fall back to
            # the specification's default, which includes `implicit` — a flow with no PKCE and no
            # exchange, and one this provider would refuse. Better to say what is true.
            "grant_types_supported": ["authorization_code"],
            # A public client: it holds no secret, and PKCE is what stands in for one.
            "token_endpoint_auth_methods_supported": ["none"],
            "code_challenge_methods_supported": ["S256"],
            # STAYS. Becoming more standards-complete must not make this look deployable — it
            # authenticates nobody, which is the entire reason it lives under `tests/`.
            "_warning": DEV_ONLY,
        }

    def do_OPTIONS(self) -> None:  # noqa: N802 - stdlib signature
        """Answer a preflight instead of 404ing it.

        Part of this flow can run from a browser origin, and a browser that gets a 404 for its
        preflight reports nothing useful — the request simply never happens and the client waits.
        """
        print(f"::dev-idp:: OPTIONS {self.path} origin={self.headers.get('Origin')}", flush=True)
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", self.headers.get("Origin", "*"))
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Max-Age", "600")
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802 - stdlib signature
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/register":
            self._register()
            return
        if parsed.path != "/token":
            self._json({"error": "not_found", "_warning": DEV_ONLY}, status=404)
            return
        length = int(self.headers.get("Content-Length", "0") or 0)
        form = urllib.parse.parse_qs(self.rfile.read(length).decode())
        print(
            f"::dev-idp:: token keys={sorted(form)} redirect={form.get('redirect_uri')}", flush=True
        )
        try:
            token = self.provider.exchange(
                code=_one(form, "code"),
                code_verifier=_one(form, "code_verifier"),
                redirect_uri=_one(form, "redirect_uri"),
                lifetime=_token_lifetime(),
            )
        except AuthorizationRefused as refused:
            # The same refusals the hermetic rows assert on, over the wire — so a browser
            # walking the flow exercises the real rejections rather than a happy path.
            print(f"::dev-idp:: token REFUSED {refused.reason}", flush=True)
            self._json({"error": refused.reason, "_warning": DEV_ONLY}, status=400)
            return
        # `expires_in` IS NOT OPTIONAL IN PRACTICE. A client that renews on its own — which is
        # the entire point of a browser login — needs to know when to. RFC 6749 calls it
        # RECOMMENDED; a client with nothing to schedule against has no way to keep a session
        # alive without asking a person, which is the thing being removed here.
        self._json(
            {
                "access_token": token,
                "token_type": "Bearer",
                "expires_in": int(_token_lifetime().total_seconds()),
                "_warning": DEV_ONLY,
            }
        )

    def _register(self) -> None:
        """Issue a client identifier. Holds nothing.

        **Stateless on purpose.** This provider authenticates nobody and has no client to tell
        apart, so a record would buy nothing and would accumulate — editors re-register on every
        reconnect. Registration must therefore succeed every time it is asked, and asking twice
        must not be an error.

        It must also never become an authentication step. The moment it decides *who* may
        register, this has begun authenticating someone and is no longer the quarantined thing.
        """
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length).decode() if length else "{}"
        try:
            request = json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError:
            self._json({"error": "invalid_client_metadata", "_warning": DEV_ONLY}, status=400)
            return

        redirect_uris = request.get("redirect_uris") or []
        # OBSERVED, NOT YET CONSTRAINED (023 T015). No redirect from a real MCP editor has ever
        # been measured against this provider — the one client watched never reached `/authorize`
        # because discovery broke first. Editors commonly use `localhost` by name rather than the
        # loopback literal, or a private scheme. A constraint written from a guess would refuse
        # exactly the clients this exists for, so the value is recorded first and the rule comes
        # from what arrives.
        print(f"::dev-idp:: register redirect_uris={redirect_uris!r}", flush=True)
        self._json(
            {
                "client_id": f"dev-client-{secrets.token_hex(8)}",
                "redirect_uris": redirect_uris,
                "token_endpoint_auth_method": "none",
                "_warning": DEV_ONLY,
            },
            status=201,
        )

    def _authorize(self, query: dict[str, list[str]]) -> None:
        redirect_uri = _one(query, "redirect_uri")
        # Same reason as `_register`: measure before constraining (023 T015).
        print(f"::dev-idp:: authorize redirect_uri={redirect_uri!r}", flush=True)
        state = _one(query, "state")
        try:
            code = self.provider.authorize(
                code_challenge=_one(query, "code_challenge"),
                code_challenge_method=_one(query, "code_challenge_method") or "S256",
                redirect_uri=redirect_uri,
                # Whoever asks. There is no authentication here, which is the whole reason
                # this file is quarantined in tests/.
                subject=_one(query, "subject") or "alice",
                tenant=_one(query, "tenant") or "tenant-test",
                # CLAIMS THE CALLER ASKS FOR, because a fixed set makes the platform's own
                # refusal unfalsifiable. This was `{"groups": ["platform"]}` always — so
                # every development token carried the same claim, and a row could never
                # present one that maps to a role and one that does not. The platform
                # refuses an unmapped claim correctly; a harness that can only ever produce
                # unmapped claims cannot tell that from the platform being broken.
                #
                # JSON values so a list survives the query string; a bare word is taken as
                # itself, which keeps the common case readable.
                # THE DEFAULT MUST BE A CLAIM THIS PLATFORM ACTUALLY MAPS, or a browser login
                # completes and every call is then refused `unmapped_claim` — which is the
                # platform working correctly and is indistinguishable, to the person signing in,
                # from it being broken.
                #
                # `{"groups": ["platform"]}` is what the in-process harness maps; the SERVED
                # surface reads its mappings from the trust store and the conformance lane mints
                # `permissions=["platform:operator"]`. A browser client sends no claims of its
                # own, so it fell through to the wrong default and looped: obtain a token, be
                # refused, start again.
                #
                # A caller can still ask for anything, including something that maps to nothing —
                # that is FR-009, and the rows that show this platform refusing an unmapped
                # identity depend on it.
                claims=_claims(query) or {"permissions": ["platform:operator"]},
            )
        except AuthorizationRefused as refused:
            self._json({"error": refused.reason, "_warning": DEV_ONLY}, status=400)
            return
        separator = "&" if "?" in redirect_uri else "?"
        location = f"{redirect_uri}{separator}code={code}&state={urllib.parse.quote(state)}"
        self.send_response(302)
        self.send_header("Location", location)
        self.send_header("X-Dev-Only", DEV_ONLY)
        self.end_headers()

    def _json(self, body: dict[str, Any], *, status: int = 200) -> None:
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("X-Dev-Only", DEV_ONLY)
        self.send_header("Access-Control-Allow-Origin", self.headers.get("Origin", "*"))
        self.end_headers()
        self.wfile.write(payload)


def _claims(query: dict[str, list[str]]) -> dict[str, Any]:
    """Everything the caller asked to carry, minus the protocol's own parameters."""
    # A DENYLIST, and its gaps are silent — which is how this went wrong.
    #
    # `resource` was missing. MCP requires a client to send it (RFC 8707), so every real editor
    # did, `_claims` returned `{"resource": ...}`, that was truthy, and the caller in `_authorize`
    # therefore never fell back to its default claims. The token carried `resource` and nothing
    # that maps to a role, and every call was refused `unmapped_claim` — after a browser login
    # that appeared to succeed. A hand-driven flow that sent only the parameters this list already
    # knew about worked perfectly, which is why it survived being tested.
    #
    # Everything the authorization request may legitimately carry, so that a parameter a client
    # sends by specification never becomes an identity claim by accident.
    protocol = {
        "response_type",
        "response_mode",
        "client_id",
        "redirect_uri",
        "state",
        "code_challenge",
        "code_challenge_method",
        "subject",
        "tenant",
        "scope",
        "nonce",
        # RFC 8707, and required by the MCP authorization specification.
        "resource",
        "audience",
        "prompt",
        "display",
        "login_hint",
        "max_age",
        "acr_values",
        "ui_locales",
        "id_token_hint",
        "request",
        "request_uri",
    }
    out: dict[str, Any] = {}
    for key, values in query.items():
        if key in protocol or not values:
            continue
        raw = values[0]
        try:
            out[key] = json.loads(raw)
        except (json.JSONDecodeError, TypeError, ValueError):
            out[key] = raw
    return out


def _one(values: dict[str, list[str]], key: str) -> str:
    found = values.get(key) or [""]
    return found[0]


#: How long a token this provider mints stays valid, in minutes.
#:
#: **Five is right for a test and wrong for a person.** The rows walk the flow and present the
#: result in the same breath, so five minutes is generous. A developer pasting the token into an
#: editor's MCP config has to open a file, save it, and reconnect — and the token is dead before
#: the editor finishes starting, which presents as `HTTP 401 ... while using configured
#: Authorization header` with nothing in the surface's log, because the refusal happens in the
#: SDK's auth middleware before any of our code runs.
#:
#: Observed exactly that way on 2026-08-01, the first time anyone connected an editor.
#:
#: The default is unchanged, so no row moves. `DEV_IDP_TOKEN_MINUTES=480` is what a person
#: setting up an editor wants.
TOKEN_MINUTES_ENV = "DEV_IDP_TOKEN_MINUTES"
DEFAULT_TOKEN_MINUTES = 5


def _token_lifetime() -> timedelta:
    """The configured lifetime, or the five minutes every row already assumes.

    **A bad value fails loudly rather than falling back.** A silent default here would hand
    someone who typed `DEV_IDP_TOKEN_MINUTES=8h` a five-minute token and let them spend the
    afternoon debugging an editor.
    """
    raw = os.environ.get(TOKEN_MINUTES_ENV, "").strip()
    if not raw:
        return timedelta(minutes=DEFAULT_TOKEN_MINUTES)
    try:
        minutes = int(raw)
    except ValueError as exc:
        raise ValueError(f"{TOKEN_MINUTES_ENV}={raw!r} is not a whole number of minutes") from exc
    if minutes < 1:
        raise ValueError(f"{TOKEN_MINUTES_ENV}={raw!r} must be at least 1")
    return timedelta(minutes=minutes)


def serve(*, host: str = "127.0.0.1", port: int = 8090) -> None:  # pragma: no cover
    """Run until killed. Called by `make dev-up`, never by anything shipped."""
    issuer = os.environ.get("DEV_IDP_ISSUER", f"http://{host}:{port}")
    # THE PROVIDER MUST MINT WHAT THE DOCUMENT ANNOUNCES, and it did not.
    #
    # This said `FakeOIDCProvider()`, so the discovery document announced `issuer` while every
    # token carried the class default `https://idp.test.invalid/`. Any verifier checking `iss`
    # against the discovered issuer refuses all of them — with a mismatch that names the
    # issuer rather than this line.
    #
    # It was invisible because nothing walked a full development sign-in through to a
    # verifier: the deployment rows assert the portal REDIRECTS, and stop there. 019's rows
    # are the first to redeem a code and present the result to a surface that verifies it.
    # `portal-up` has the same exposure — it tells the API to expect
    # `http://127.0.0.1:8090` — so this fixes a defect on a path nobody had run either.
    handler = type(
        "_BoundHandler",
        (_Handler,),
        {"provider": FakeOIDCProvider(issuer=issuer), "issuer": issuer},
    )
    print(f"{DEV_ONLY} — listening on {host}:{port}, issuer {issuer}", flush=True)
    # THREADING, because a browser is not the conformance harness.
    #
    # This was `HTTPServer`, which serves one request at a time. Every automated row here makes
    # strictly sequential `urllib` calls and closes each connection, so nothing ever noticed. A
    # real editor does not: it opens the authorize URL in a browser, the browser holds its
    # connection open with keep-alive, and the token POST that follows queues behind it forever.
    #
    # Observed exactly that way — a client that completed discovery, registration, and
    # authorization, then hung on "Exchanging token...". The third defect in this chain that only
    # a real client could surface.
    ThreadingHTTPServer((host, port), handler).serve_forever()


if __name__ == "__main__":  # pragma: no cover
    serve(
        host=os.environ.get("DEV_IDP_HOST", "127.0.0.1"),
        port=int(os.environ.get("DEV_IDP_PORT", "8090")),
    )
