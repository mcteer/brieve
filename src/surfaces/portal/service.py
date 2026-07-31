# SPDX-License-Identifier: Apache-2.0
"""The portal as a served process.

Reads the environment, builds the relay and the OIDC client, hands them to
`create_portal`. Like the API's service module, it decides nothing — and it is separate
from `app.py` for the same reason: the app a test builds and the app that ships must be
the same object assembled two ways, not two objects.

**There is no credential to read here.** No client secret, no Vault address, no database.
The longest thing this file does is refuse to start without knowing where the IdP is.
"""

from __future__ import annotations

import os

from surfaces.portal.app import create_portal
from surfaces.portal.oidc import OidcClient
from surfaces.portal.relay import ApiRelay


def build() -> object:
    """Assemble the production portal. Raises if the environment is incomplete."""
    return create_portal(
        relay=ApiRelay(base_url=_required("API_BASE_URL")),
        oidc=OidcClient(
            issuer=_required("OIDC_ISSUER"),
            client_id=os.environ.get("PORTAL_CLIENT_ID", "harness-portal"),
            redirect_uri=_required("PORTAL_REDIRECT_URI"),
            authorize_endpoint=_required("OIDC_AUTHORIZE_ENDPOINT"),
            token_endpoint=_required("OIDC_TOKEN_ENDPOINT"),
            # Optional, because the development provider does not use it. Against a
            # real provider its absence produces an opaque token the API refuses.
            audience=os.environ.get("OIDC_AUDIENCE", "").strip() or None,
        ),
    )


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(
            f"{name} is not set. The portal is a thin client and knows nothing it is not "
            "told; starting without this would produce a surface that cannot sign anyone in."
        )
    return value


def main() -> None:  # pragma: no cover - process entrypoint
    import uvicorn

    bind = os.environ.get("PORTAL_BIND", "127.0.0.1:8082")
    host, _, port = bind.rpartition(":")

    # TLS, BECAUSE THE SESSION COOKIE IS `Secure` AND THAT IS NOT NEGOTIABLE.
    #
    # `session.cookie_attributes` explains why the flag cannot come back, and it is right.
    # What its docstring claimed — "browsers treat http://localhost and http://127.0.0.1 as
    # trustworthy origins, so a Secure cookie is accepted there" — is true of Chromium and
    # Firefox and NOT of Safari, which wants an actual https scheme.
    #
    # The whole platform's accessibility suite drives Chromium (`tests/a11y/conftest.py`), so
    # the claim was only ever tested where it holds. In Safari the callback succeeds, the
    # cookie is discarded silently, and the next request renders the sign-in page again —
    # observed 2026-07-31 with an empty cookie store and a `303` in the access log.
    #
    # So the portal serves TLS when handed a certificate. Unset, it serves plain HTTP exactly
    # as before, which keeps every test client and the a11y lane working unchanged.
    cert = os.environ.get("PORTAL_TLS_CERT", "").strip()
    key = os.environ.get("PORTAL_TLS_KEY", "").strip()
    if bool(cert) != bool(key):
        raise RuntimeError(
            "PORTAL_TLS_CERT and PORTAL_TLS_KEY must be set together. One without the other "
            "would serve plain HTTP while looking configured for TLS — and the failure is a "
            "sign-in page that silently never signs anyone in."
        )

    uvicorn.run(
        build(),  # type: ignore[arg-type]  # FastAPI is an ASGI app; `build` returns object
        host=host or "127.0.0.1",
        port=int(port or 8082),
        log_level="info",
        ssl_certfile=cert or None,
        ssl_keyfile=key or None,
    )


if __name__ == "__main__":  # pragma: no cover - process entrypoint
    main()
