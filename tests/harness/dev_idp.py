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
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
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

        if parsed.path == "/.well-known/openid-configuration":
            self._json(
                {
                    "issuer": self.issuer,
                    "authorization_endpoint": f"{self.issuer}/authorize",
                    "token_endpoint": f"{self.issuer}/token",
                    "jwks_uri": f"{self.issuer}/jwks",
                    "code_challenge_methods_supported": ["S256"],
                    "_warning": DEV_ONLY,
                }
            )
        elif parsed.path == "/jwks":
            self._json(self.provider.jwks())
        elif parsed.path == "/authorize":
            self._authorize(query)
        else:
            self._json({"error": "not_found", "_warning": DEV_ONLY}, status=404)

    def do_POST(self) -> None:  # noqa: N802 - stdlib signature
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/token":
            self._json({"error": "not_found", "_warning": DEV_ONLY}, status=404)
            return
        length = int(self.headers.get("Content-Length", "0") or 0)
        form = urllib.parse.parse_qs(self.rfile.read(length).decode())
        try:
            token = self.provider.exchange(
                code=_one(form, "code"),
                code_verifier=_one(form, "code_verifier"),
                redirect_uri=_one(form, "redirect_uri"),
            )
        except AuthorizationRefused as refused:
            # The same refusals the hermetic rows assert on, over the wire — so a browser
            # walking the flow exercises the real rejections rather than a happy path.
            self._json({"error": refused.reason, "_warning": DEV_ONLY}, status=400)
            return
        self._json({"access_token": token, "token_type": "Bearer", "_warning": DEV_ONLY})

    def _authorize(self, query: dict[str, list[str]]) -> None:
        redirect_uri = _one(query, "redirect_uri")
        state = _one(query, "state")
        try:
            code = self.provider.authorize(
                code_challenge=_one(query, "code_challenge"),
                code_challenge_method=_one(query, "code_challenge_method") or "S256",
                redirect_uri=redirect_uri,
                # Whoever asks. There is no authentication here, which is the whole reason
                # this file is quarantined in tests/.
                subject=_one(query, "subject") or "alice",
                claims={"groups": ["platform"]},
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
        self.end_headers()
        self.wfile.write(payload)


def _one(values: dict[str, list[str]], key: str) -> str:
    found = values.get(key) or [""]
    return found[0]


def serve(*, host: str = "127.0.0.1", port: int = 8090) -> None:  # pragma: no cover
    """Run until killed. Called by `make dev-up`, never by anything shipped."""
    issuer = os.environ.get("DEV_IDP_ISSUER", f"http://{host}:{port}")
    handler = type("_BoundHandler", (_Handler,), {"provider": FakeOIDCProvider(), "issuer": issuer})
    print(f"{DEV_ONLY} — listening on {host}:{port}, issuer {issuer}", flush=True)
    HTTPServer((host, port), handler).serve_forever()


if __name__ == "__main__":  # pragma: no cover
    serve(
        host=os.environ.get("DEV_IDP_HOST", "127.0.0.1"),
        port=int(os.environ.get("DEV_IDP_PORT", "8090")),
    )
