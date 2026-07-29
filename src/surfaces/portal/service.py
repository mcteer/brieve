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
        ),
        # Defaults to secure. A deployment that wants otherwise has to say so, which is the
        # right direction for a flag whose wrong value is invisible until it matters.
        secure_cookies=os.environ.get("PORTAL_SECURE_COOKIES", "1") != "0",
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
    uvicorn.run(
        build(),  # type: ignore[arg-type]  # FastAPI is an ASGI app; `build` returns object
        host=host or "127.0.0.1",
        port=int(port or 8082),
        log_level="info",
    )


if __name__ == "__main__":  # pragma: no cover - process entrypoint
    main()
