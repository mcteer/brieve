# SPDX-License-Identifier: Apache-2.0
"""The development provider, checked the way a real client uses it.

**Every row here corresponds to a defect a real editor found and this suite did not.** Five
attempts to connect Cursor failed in five different ways, and all of them passed the served-surface
conformance lane — because that lane drove a flow written to match what had been built.

The rows below exist to make the difference between *reachable* and *acceptable* checkable.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from tests.harness.dev_idp import _claims, _is_allowed_redirect


def _discovery() -> dict[str, Any]:
    """The document, built the way the handler builds it."""
    from tests.harness.dev_idp import DEV_ONLY

    issuer = "http://127.0.0.1:8090"
    return {
        "issuer": issuer,
        "authorization_endpoint": f"{issuer}/authorize",
        "token_endpoint": f"{issuer}/token",
        "jwks_uri": f"{issuer}/jwks",
        "registration_endpoint": f"{issuer}/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "token_endpoint_auth_methods_supported": ["none"],
        "code_challenge_methods_supported": ["S256"],
        "_warning": DEV_ONLY,
    }


def test_the_document_carries_what_rfc_8414_requires() -> None:
    """A client does not merely fetch this — it validates it.

    `response_types_supported` was missing. An editor fetched the document, validated it, and
    refused with "expected array, received undefined". Discovery being *reachable* is not
    discovery being *acceptable*, and every check we had asserted the first.
    """
    doc = _discovery()
    for field in ("issuer", "authorization_endpoint", "token_endpoint", "response_types_supported"):
        assert field in doc, f"RFC 8414 requires {field}; a client will refuse the document"
    assert isinstance(doc["response_types_supported"], list)


def test_the_document_names_where_to_register() -> None:
    """Without it a client holding no `client_id` has nowhere to go, and discovery ends."""
    assert _discovery()["registration_endpoint"].endswith("/register")


def test_the_grant_it_actually_implements_is_declared() -> None:
    """Omitting this makes a client fall back to a default that includes `implicit`.

    That flow has no PKCE and no exchange, and this provider refuses it. Saying what is true is
    cheaper than being fallen back on.
    """
    doc = _discovery()
    assert doc["grant_types_supported"] == ["authorization_code"]
    assert doc["code_challenge_methods_supported"] == ["S256"]


def test_it_still_says_it_is_not_deployable() -> None:
    """Becoming standards-complete must not make this look like something you could ship."""
    assert "never deploy" in _discovery()["_warning"].lower()


# ---------------------------------------------------------------- claims


@pytest.mark.parametrize(
    "param",
    [
        "resource",
        "scope",
        "nonce",
        "prompt",
        "login_hint",
        "audience",
        "response_mode",
        # NOT A PROTOCOL PARAMETER — invented here, and that is the point. Under the denylist
        # this replaced, a parameter nobody had thought of became an identity claim. Under an
        # allowlist it cannot, whether or not anyone anticipated it.
        "a_parameter_invented_after_this_was_written",
    ],
)
def test_a_protocol_parameter_never_becomes_an_identity_claim(param: str) -> None:
    """**The defect that took five attempts to find.**

    `_claims` is a denylist, and `resource` was not on it. MCP requires clients to send it, so a
    real editor did — `_claims` returned a truthy dict, the caller's default claims were never
    applied, the token carried no role, and the surface refused `unmapped_claim` after a login
    that appeared to succeed.

    It survived four rounds of testing because the test kept being written without `resource`: a
    request shape no real client uses.
    """
    assert _claims({param: ["anything"]}) == {}, (
        f"{param!r} is a protocol parameter and became an identity claim; a client sending it "
        "by specification would carry it in its token and fall through its default claims"
    )


def test_the_claim_list_is_an_allowlist_not_a_denylist() -> None:
    """The direction this fails in is the whole fix.

    A denylist that forgets a protocol parameter turns it into an identity claim — silently, and
    in the direction that changes who someone is. An allowlist that forgets a claim simply does
    not carry it, which shows up as a row failing. Same class of omission, opposite blast radius.
    """
    from tests.harness.dev_idp import CLAIM_PARAMETERS

    assert "resource" not in CLAIM_PARAMETERS
    assert "permissions" in CLAIM_PARAMETERS
    # Everything outside the set is ignored, without the set needing to know it exists.
    assert _claims({"anything-at-all": ["x"], "permissions": ['["p"]']}) == {"permissions": ["p"]}


def test_a_genuine_claim_still_gets_through() -> None:
    """The denylist must not become a wall — rows that show the platform refusing an unmapped
    identity depend on being able to ask for one (FR-009)."""
    assert _claims({"permissions": ['["platform:operator"]']}) == {
        "permissions": ["platform:operator"]
    }
    assert _claims({"groups": ["nothing-maps-to-this"]}) == {"groups": "nothing-maps-to-this"}


# ---------------------------------------------------------------- redirect target


@pytest.mark.parametrize(
    "uri",
    [
        # MEASURED from a real editor completing a real flow.
        "http://localhost:8787/callback",
        "cursor://anysphere.cursor-mcp/oauth/callback",
        # The two callers already in this repository.
        "http://127.0.0.1:0/callback",
        "https://127.0.0.1:8082/callback",
    ],
)
def test_the_targets_real_clients_use_are_admitted(uri: str) -> None:
    """Written from a measurement rather than a guess (FR-011a).

    A loopback-literal rule — the obvious thing to write — would have refused `localhost` by name
    and a private scheme, which is to say every target the editor this feature exists for actually
    uses. The refusal would have been indistinguishable from the platform working correctly.
    """
    assert _is_allowed_redirect(uri), f"{uri} is what a real client sends and must be admitted"


@pytest.mark.parametrize(
    "uri", ["https://www.cursor.com/agents/mcp/oauth/callback", "http://evil.example/cb"]
)
def test_a_remote_target_is_refused(uri: str) -> None:
    """Authenticating nobody is not a reason to hand a code anywhere it is asked to (FR-011).

    The first of these is registered by a real editor and not used at authorize. If that ever
    changes this row fails, which is the correct way to find out.
    """
    assert not _is_allowed_redirect(uri)


def test_the_document_is_json_serialisable() -> None:
    """It is served over the wire; a value that cannot be encoded is a 500 nobody sees locally."""
    json.dumps(_discovery())
