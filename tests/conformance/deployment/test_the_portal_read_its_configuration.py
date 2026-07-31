# SPDX-License-Identifier: Apache-2.0
"""Row: the portal is deployed and read its own configuration (017).

The portal holds no store and no credential, so it cannot be asserted the way the API is —
answering proves less. What it can be asked for is `/login`, and where that redirect POINTS
is configuration: a process holding defaults sends people somewhere else. The PKCE challenge
proves the OIDC client was constructed rather than stubbed.

`/login` rather than `/`, which renders a sign-in page and proves only that templates load.
The first version of this row asked for `/` and got a 200 — a page, from a surface that had
read its configuration perfectly well. Asserting against the wrong endpoint fails a correct
deployment, which is the way a gate loses trust fastest.
"""

from __future__ import annotations

import os
import urllib.parse

import pytest

from tests.conformance.deployment.conftest import exec_request, require_running

pytestmark = [pytest.mark.enclave, pytest.mark.host_enclave]

PORTAL = "portal"
LOGIN = "http://127.0.0.1:8082/login"


def test_the_portal_reaches_a_working_state() -> None:
    """US1: deployed, placed, and not flapping."""
    assert require_running(PORTAL)


def test_the_portal_redirects_to_the_configured_issuer() -> None:
    """US2: the redirect proves configuration was read, not defaulted."""
    response = exec_request(PORTAL, LOGIN)

    assert response.status in {302, 303, 307}, (
        f"expected a sign-in redirect, got HTTP {response.status}: {response.body[:300]}"
    )
    location = response.header("Location")
    assert location, "redirected with no Location — nothing says where"

    query = urllib.parse.parse_qs(urllib.parse.urlparse(location).query)
    assert query.get("code_challenge_method") == ["S256"], (
        "no PKCE challenge in the authorization request, so the OIDC client was not "
        "constructed — RFC 7636's `plain` is refused by this platform and its absence "
        "entirely means there is nothing to refuse"
    )

    # Where it points is the configuration half. Compared against what the enclave was told
    # rather than against a literal, so this row does not go stale when the provider changes.
    expected = os.environ.get("OIDC_AUTHORIZE_ENDPOINT") or os.environ.get("OIDC_ISSUER")
    if expected:
        assert expected.rstrip("/").split("//")[-1].split("/")[0] in location, (
            f"the portal redirects to {location[:120]!r}, which is not the configured "
            f"issuer. A process holding defaults would emit exactly this."
        )
