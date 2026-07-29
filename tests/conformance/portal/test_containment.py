# SPDX-License-Identifier: Apache-2.0
"""CONFORMANCE — the portal adds nothing.

The portal's obligation is **containment, not equivalence**. Parity binds API↔MCP, because
those two implement the catalogue; the portal consumes it. So the question these rows ask
is not "does it agree with the other transports" but "does it add anything at all" — and a
capability reachable here and absent from the API would be the fourth authorization path
ADR-0033 exists to prevent, wearing the friendliest possible name.

Every row is structural. None of them checks that the portal *did not* do something on one
occasion; each checks that it *cannot*.
"""

from __future__ import annotations

import ast
import json
import pathlib
import re

from fastapi.testclient import TestClient

from surfaces.portal.app import create_portal
from surfaces.portal.oidc import OidcClient, code_challenge_for
from surfaces.portal.relay import ApiRelay, ApiResponse
from surfaces.portal.session import COOKIE_NAME
from tests.harness.api_fixtures import surface_under_test

PORTAL = pathlib.Path(__file__).resolve().parents[3] / "src/surfaces/portal"
SNAPSHOT = (
    pathlib.Path(__file__).resolve().parents[3]
    / "specs/008-northbound-api/contracts/operations.snapshot.json"
)

#: Anything that can reach the network.
HTTP_CLIENTS = ("urllib", "httpx", "requests", "http.client", "aiohttp", "httpcore")

#: The modules permitted to reach the network, and what each may reach.
#:
#: An explicit allowlist with reasons, on the `ENCLAVE_PATHS` pattern — adding a member
#: should be a visible decision rather than a check that quietly stopped applying.
#:
#: **Two doors, and they lead to different places.** `relay.py` reaches the PLATFORM and is
#: the one containment cares about: everything it asks for must be a catalogued operation,
#: which the next row checks request by request. `oidc.py` reaches the IdP, which is
#: outside this platform entirely and exposes no platform capability — a login is not a
#: thing the API could have offered instead. Collapsing them into one module would put the
#: token exchange behind the same door as run dispatch and make both harder to reason
#: about, not easier.
EGRESS_MODULES = {
    "relay.py": "the platform, and only through catalogued operations",
    "oidc.py": "the identity provider, for the authorization-code exchange",
}


def _modules() -> list[pathlib.Path]:
    return sorted(p for p in PORTAL.rglob("*.py") if p.name != "__init__.py")


def test_row_only_declared_modules_can_reach_the_network() -> None:
    """Two doors, both declared. Enumerating what the portal can reach is reading two files."""
    offenders: list[str] = []
    for path in _modules():
        if path.name in EGRESS_MODULES:
            continue
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            for name in names:
                if any(name == c or name.startswith(c + ".") for c in HTTP_CLIENTS):
                    offenders.append(f"{path.name}: {name}")

    assert offenders == [], (
        f"an undeclared portal module can reach the network: {offenders}. "
        f"Declared: {sorted(EGRESS_MODULES)}"
    )


def test_row_the_egress_allowlist_has_not_grown_quietly() -> None:
    """The membership is asserted, not merely allowed.

    Same discipline as the service-loop exemption in `test_surface_never_pauses`: if this
    list grows, someone decided it should, and this row is where they had to say so.
    """
    assert set(EGRESS_MODULES) == {"relay.py", "oidc.py"}


def test_row_every_request_the_portal_makes_is_a_catalogued_operation() -> None:
    """A scripted session over every page and action, checked against the snapshot.

    This is the containment claim in its strongest available form: not an argument about
    the code, but a log of what the portal actually asked for, mapped onto the operations
    the API actually exposes.
    """
    catalogue = json.loads(SNAPSHOT.read_text())
    patterns = [
        (op["method"], re.compile("^" + re.sub(r"\{[^}]+\}", "[^/]+", op["path"]) + "$"))
        for op in catalogue
    ]
    seen: list[tuple[str, str]] = []

    surface = surface_under_test()
    api = TestClient(surface.app)

    def transport(*, method: str, url: str, token: str, json_body: object) -> ApiResponse:
        path = url.replace("http://api.test", "").split("?")[0]
        seen.append((method, path))
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
            relay=ApiRelay(base_url="http://api.test", transport=transport),
            oidc=oidc,
        ),
        base_url="http://testserver",
    )
    state, _ = oidc.begin()
    code = surface.idp.authorize(
        code_challenge=code_challenge_for(oidc._pending[state].verifier),
        subject="alice",
        claims={"groups": ["platform"]},
    )
    signed = portal.get(f"/callback?code={code}&state={state}", follow_redirects=False)
    portal.cookies.set(COOKIE_NAME, str(signed.cookies.get(COOKIE_NAME)))

    # Every page and every action this portal offers.
    portal.get("/")
    thread_path = portal.post("/threads", follow_redirects=False).headers["location"]
    portal.get(thread_path)
    portal.post(
        thread_path + "/turns",
        data={"message": "plan it", "agent_definition_id": "planner"},
        follow_redirects=False,
    )
    portal.get(thread_path)
    detail = api.get(thread_path, headers=surface.bearer())
    run_id = detail.json()["turns"][0]["run_id"]
    portal.post(
        f"/runs/{run_id}/stop",
        data={"thread_id": thread_path.rsplit("/", 1)[-1]},
        follow_redirects=False,
    )
    portal.get(thread_path + "/delete")
    portal.post(thread_path + "/delete", follow_redirects=False)

    assert seen, "the scripted session reached nothing; the row proves nothing"
    uncatalogued = [
        (method, path)
        for method, path in seen
        if not any(method == m and pattern.match(path) for m, pattern in patterns)
    ]
    assert uncatalogued == [], (
        f"the portal reached something the API does not expose: {uncatalogued}"
    )


def test_row_the_portal_holds_no_credential_of_its_own() -> None:
    """No Vault, no database, no client secret, no static key. Nothing to authenticate as."""
    forbidden = ("vault", "pg8000", "client_secret", "VAULT_TOKEN", "database/creds")
    offenders: list[str] = []
    for path in _modules():
        text = path.read_text().lower()
        # Strip prose: this file's own docstrings discuss what it does not hold.
        code = ast.unparse(_without_docstrings(ast.parse(path.read_text()))).lower()
        for word in forbidden:
            if word.lower() in code and word.lower() in text:
                offenders.append(f"{path.name}: {word}")

    assert offenders == [], f"the portal holds something credential-shaped: {offenders}"


def _without_docstrings(tree: ast.Module) -> ast.Module:
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            body = getattr(node, "body", [])
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                node.body = body[1:]
    return tree


def test_row_the_served_client_is_small_enough_to_read() -> None:
    """SC-006 verified against the delivered client, which is the point of having no build.

    A bundle can be trusted; a file can be checked. If this ever fails on size, the honest
    response is to ask what was added rather than to raise the number.
    """
    script = PORTAL / "static/portal.js"
    body = script.read_text()

    assert len(body.splitlines()) < 80, (
        "the client script has grown past the point where a row can meaningfully read it"
    )


def test_row_the_served_client_reaches_nothing_but_this_origin() -> None:
    """No fetch beyond the portal, no model endpoint, no storage, no decisions."""
    raw = (PORTAL / "static/portal.js").read_text()
    # Comments discuss what the script deliberately does NOT do — including naming
    # `innerHTML` to explain why `textContent` is used instead. Checking the prose would
    # make the file's own honesty trip the check, which is a defect in the row.
    body = re.sub(r"//.*", "", raw)

    assert "http://" not in body and "https://" not in body, (
        "the client script names an absolute URL"
    )
    for forbidden in ("localStorage", "sessionStorage", "indexedDB", "document.cookie"):
        assert forbidden not in body, f"the client script touches {forbidden}"
    for forbidden in ("anthropic", "openai", "completion", "/v1/messages"):
        assert forbidden not in body.lower(), f"the client script names {forbidden}"
    assert "innerHTML" not in body, "the client script writes markup rather than text"


def test_row_nothing_the_browser_holds_survives_the_session() -> None:
    """FR-020b, checked on the delivered response rather than on intent."""
    surface = surface_under_test()

    def transport(*, method: str, url: str, token: str, json_body: object) -> ApiResponse:
        return ApiResponse(status=200, payload={"threads": []})

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
            relay=ApiRelay(base_url="http://api.test", transport=transport),
            oidc=oidc,
        ),
        base_url="http://testserver",
    )
    state, _ = oidc.begin()
    code = surface.idp.authorize(code_challenge=code_challenge_for(oidc._pending[state].verifier))
    signed = portal.get(f"/callback?code={code}&state={state}", follow_redirects=False)

    cookies = signed.headers.get_list("set-cookie")
    assert len(cookies) == 1, f"the portal set more than the session cookie: {cookies}"
    assert "httponly" in cookies[0].lower()
    # The value is an opaque id: not a JWT, not a token, not the subject.
    value = str(signed.cookies.get(COOKIE_NAME))
    assert "." not in value and "alice" not in value


def test_row_the_client_does_not_reload_unconditionally() -> None:
    """The reload loop, pinned.

    The first version of `portal.js` reloaded on every stream close. A thread with nothing
    running closes its stream immediately, so the page reloaded, opened a new stream,
    closed, and reloaded — forever, hammering the API and making the portal unusable. No
    hermetic row could see it, because none of them execute this file; the accessibility
    gate found it in about a second.

    This row is cheap insurance against it coming back: a reload must be guarded.
    """
    body = re.sub(r"//.*", "", (PORTAL / "static/portal.js").read_text())

    assert "location.reload" in body, "the row is stale — the script no longer reloads"
    guarded = re.search(r"if\s*\([^)]*\)\s*\{\s*\n?\s*window\.location\.reload", body)
    assert guarded, (
        "window.location.reload() is not inside a condition; an unconditional reload on "
        "stream close is an infinite loop"
    )
