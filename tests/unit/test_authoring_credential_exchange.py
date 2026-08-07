# SPDX-License-Identifier: Apache-2.0
"""The App-key exchange, and what must never escape it (041, T002/T006, FR-011, FR-023a).

038 shipped `AuthoringCredentials` with `token_for()` raising `NotImplementedError` and a
comment saying the exchange was "provisioned by the estate and exercised in the enclave lane".
No enclave lane ever ran it. These rows exercise the exchange hermetically against a local
endpoint — which is possible precisely because the class accepts a reader and an API root, and
is *not* possible for the credential itself: nothing here supplies a token, because there is
nowhere to supply one.

**The stub most available here** is asserting the token comes back and stopping. A token that
works while the private key is in a traceback is the failure this file exists for, so the leak
rows outnumber the happy path.
"""

from __future__ import annotations

import functools
import json
import threading
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import pytest

from core.authoring.credential import AuthoringCredentials, InstallationToken
from core.durability.credentials import CredentialUnavailableError


@functools.lru_cache(maxsize=1)
def _key() -> str:
    """An RSA key generated for these rows and valid for nothing.

    Generated rather than checked in, so no secret scanner has to decide whether a `.pem` in
    this tree is real, and no reviewer has to take the answer on trust. Cached because 2048-bit
    generation is slow enough to notice across a dozen rows.
    """
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()


class _Identity:
    """An attested identity, or the analysing task's lack of one."""

    def __init__(self, jwt: str | None = "attested-jwt") -> None:
        self._jwt = jwt

    def jwt(self) -> str:
        if self._jwt is None:
            raise CredentialUnavailableError("no attested identity in this task")
        return self._jwt


class _Reader:
    """A trust-fabric reader. Records what was asked for, so a row can assert the path."""

    def __init__(self, data: dict[str, Any] | None) -> None:
        self._data = data
        self.paths: list[str] = []

    def read_path(self, path: str, *, token: str | None = None) -> dict[str, Any] | None:
        self.paths.append(path)
        return self._data


class _Forge(BaseHTTPRequestHandler):
    seen_auth: list[str] = []
    status = 201

    def do_POST(self) -> None:  # noqa: N802 — BaseHTTPRequestHandler's interface
        _Forge.seen_auth.append(self.headers.get("Authorization", ""))
        body = json.dumps(
            {"token": "ghs_installation_token", "expires_at": "2026-08-07T02:00:00Z"}
        ).encode()
        self.send_response(_Forge.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args: Any) -> None:  # noqa: D102 — silence the test server
        return


@pytest.fixture
def forge() -> Any:
    _Forge.seen_auth = []
    _Forge.status = 201
    server = HTTPServer(("127.0.0.1", 0), _Forge)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()


#: Distinguishes "the row said nothing about the record" from "the row said there is none".
#: Without it, `data=None` — the unseeded-fabric case — silently gets the healthy default, and
#: two rows pass while asserting the opposite of what they read.
_DEFAULT = object()


def _credentials(
    forge_root: str, *, data: Any = _DEFAULT, jwt: str | None = "j"
) -> tuple[AuthoringCredentials, _Reader]:
    record = {"app_id": "123", "private_key": _key()} if data is _DEFAULT else data
    reader = _Reader(record)
    creds = AuthoringCredentials(
        identity=_Identity(jwt), reader=reader, api_root=forge_root, timeout=5.0
    )
    return creds, reader


def test_the_exchange_yields_an_installation_token(forge: str) -> None:
    """The happy path: attested identity → fabric → App assertion → scoped token."""
    creds, reader = _credentials(forge)
    token = creds.token_for("inst-42")
    assert isinstance(token, InstallationToken)
    assert token.token == "ghs_installation_token"
    assert token.installation == "inst-42"
    assert token.expires_at == datetime(2026, 8, 7, 2, 0, tzinfo=UTC)
    assert reader.paths == ["harness-authority/data/authoring/vcs-app"], (
        "the App key must be read from the trust fabric's own mount, never the per-agent "
        "secret space a run can write"
    )


def test_the_assertion_is_signed_and_sent_as_a_bearer(forge: str) -> None:
    """The forge sees an App JWT, and the private key is not what travels."""
    creds, _reader = _credentials(forge)
    creds.token_for("inst-42")
    assert len(_Forge.seen_auth) == 1
    header = _Forge.seen_auth[0]
    assert header.startswith("Bearer ")
    assertion = header.removeprefix("Bearer ")
    assert "PRIVATE KEY" not in assertion
    assert assertion.count(".") == 2, "an RS256 JWT, not the key and not a bare string"


def test_the_analysing_task_cannot_reach_the_key(forge: str) -> None:
    """No attested identity → refused before the fabric is touched (FR-007)."""
    creds, reader = _credentials(forge, jwt=None)
    with pytest.raises(CredentialUnavailableError):
        creds.token_for("inst-42")
    assert reader.paths == [], "the fabric must not be read by a task that cannot publish"
    assert _Forge.seen_auth == [], "and the forge must not be called"


def test_an_unseeded_fabric_refuses_by_name(forge: str) -> None:
    """ADR-0062's credential is operator-seeded; its absence says so."""
    creds, _reader = _credentials(forge, data=None)
    with pytest.raises(CredentialUnavailableError) as exc:
        creds.token_for("inst-42")
    assert "operator-seeded" in str(exc.value)


def test_a_partial_record_refuses_rather_than_signing_nothing(forge: str) -> None:
    """`app_id` without a key is a seeding error, and it fails where seeding happened."""
    creds, _reader = _credentials(forge, data={"app_id": "123"})
    with pytest.raises(CredentialUnavailableError) as exc:
        creds.token_for("inst-42")
    assert "private_key" in str(exc.value)


def test_the_private_key_never_appears_in_an_exception(forge: str) -> None:
    """The leak that no logging policy would have caught.

    Every failure mode is walked, and the key is asserted absent from each one's text —
    including the partial-record case, which is the one that *holds* a key-shaped field.
    """
    key = _key()
    cases = [
        _credentials(forge, data=None),
        _credentials(forge, data={"app_id": "123"}),
        _credentials(forge, data={"private_key": key}),
        _credentials(forge, jwt=None),
    ]
    for creds, _reader in cases:
        with pytest.raises(CredentialUnavailableError) as exc:
            creds.token_for("inst-42")
        text = f"{exc.value}{exc.traceback if hasattr(exc, 'traceback') else ''}"
        assert key not in text
        assert "PRIVATE KEY" not in text


def test_the_token_is_redacted_in_its_own_repr(forge: str) -> None:
    """038's redaction, asserted through the path that now actually produces a token."""
    creds, _reader = _credentials(forge)
    token = creds.token_for("inst-42")
    rendered = repr(token)
    assert "ghs_installation_token" not in rendered
    assert "<redacted>" in rendered
    assert "inst-42" in rendered, "the installation is not secret, and an operator needs it"


def test_a_refusing_forge_names_the_installation_and_not_the_assertion(forge: str) -> None:
    """An HTTP failure must not put the request's headers into a traceback."""
    creds, _reader = _credentials(forge)
    _Forge.status = 403
    with pytest.raises(CredentialUnavailableError) as exc:
        creds.token_for("inst-42")
    message = str(exc.value)
    assert "inst-42" in message
    assert "Bearer" not in message
    assert _key() not in message


def test_holding_the_credentials_opens_nothing() -> None:
    """The analysing task holds one of these to prove it cannot publish.

    Constructing it must therefore need no fabric and no network — otherwise the object whose
    purpose is to demonstrate an absence would itself require the thing it demonstrates.
    """
    creds = AuthoringCredentials(identity=_Identity(None))
    assert creds.available() is False
