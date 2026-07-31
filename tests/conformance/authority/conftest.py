# SPDX-License-Identifier: Apache-2.0
"""Fixtures for the task-scoped authority rows (016).

**Every row here turns on who refuses.** The property this feature buys is that a run's
credential is bounded by what its task entails, and that the bound holds *outside* the
platform's own process — so a row asserting a refusal our Python produced would be
re-testing Principle III's hooks, which already have rows and already pass.

That is why these are `host_enclave`: they hold an operator token to arrange grants and read
Vault's own verdict, and an allocation deliberately cannot. Every row file carries both
markers::

    pytestmark = [pytest.mark.enclave, pytest.mark.host_enclave]

`enclave` because the stack must be up; `host_enclave` because it cannot run inside something
the scheduler placed. The 013/014 lesson: a marker alone does not run a row that no lane
collects, and a lane alone does not skip a row that cannot run there.

**Reading failures here is unusual and worth knowing before you start.** Vault answers every
rejected grant with a bare ``403 permission denied``. Whether the cause was the signature, the
schema, the entity binding, or the scope appears *only* in the Vault server's log
(``docker logs <vault>``). A row that asserted "403 therefore the scope was enforced" would
pass for the wrong reason on a malformed token, so rows that care about the reason read the
log rather than the status code.
"""

from __future__ import annotations

import base64
import json
import os
import ssl
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Iterator
from typing import Any

import pytest

#: The issuer identity Terraform registers with the resource-server profile. Matched
#: literally by Vault against the grant's `iss`; it is an identifier, not an address.
ISSUER = "https://harness.internal/task-authority"

#: The key id in the profile's `public_keys`, echoed in each grant's JOSE header.
KEY_ID = "grant-issuer-1"

#: Where the signing key lives. The private half never leaves it.
SIGN_PATH = "task-authority/sign/grant-issuer"


def _vault(path: str, payload: Any = None, *, token: str | None = None) -> dict[str, Any]:
    addr = (os.environ.get("VAULT_ADDR") or "https://127.0.0.1:8200").rstrip("/")
    tok = token or os.environ.get("VAULT_TOKEN") or os.environ.get("VAULT_ROOT_TOKEN")
    if not tok:
        pytest.fail(
            "no VAULT_TOKEN/VAULT_ROOT_TOKEN. `make conformance` passes it from .env; a bare "
            "pytest invocation needs it exported. Not skippable — a row that skips itself "
            "reports the same green as one that ran."
        )
    cacert = os.environ.get("VAULT_CACERT")
    context = ssl.create_default_context(cafile=cacert) if cacert else None
    request = urllib.request.Request(  # noqa: S310 — fixed scheme, operator-supplied addr
        f"{addr}/v1/{path}",
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"X-Vault-Token": tok, "Content-Type": "application/json"},
        method="POST" if payload is not None else "GET",
    )
    with urllib.request.urlopen(request, timeout=15, context=context) as response:  # noqa: S310
        body = response.read()
    return json.loads(body) if body else {}


@pytest.fixture
def vault() -> Any:
    """Operator-token access, for arranging and for reading Vault's verdict."""
    return _vault


@pytest.fixture
def entity_of() -> Any:
    """The Identity entity behind a registered agent, as the registry records it."""

    def _lookup(display_name: str) -> str:
        data = _vault(f"agent-registry/registration/display-name/{display_name}")["data"]
        return str(data["entity_id"])

    return _lookup


@pytest.fixture
def mint_grant() -> Any:
    """Mint a task-scoped grant, signed by the key Vault trusts.

    Assembled here rather than imported from ``core`` on purpose: a row that minted through
    the production assembler would pass whenever the assembler and the row agreed, including
    when both were wrong about what Vault accepts. This is the wire format, written out.
    """

    def _mint(
        subject: str,
        paths: dict[str, list[str]],
        *,
        issuer: str = ISSUER,
        ttl_seconds: int = 900,
        omit_jti: bool = False,
    ) -> str:
        def b64(raw: bytes) -> str:
            return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

        now = int(time.time())
        header = b64(
            json.dumps(
                {"alg": "ES256", "typ": "JWT", "kid": KEY_ID}, separators=(",", ":")
            ).encode()
        )
        claims: dict[str, Any] = {
            "iss": issuer,
            "aud": "vault",
            "sub": subject,
            "iat": now,
            "nbf": now - 5,
            "exp": now + ttl_seconds,
            "authorization_details": [
                {"type": "vault:path_access", "path": path, "capabilities": caps}
                for path, caps in paths.items()
            ],
        }
        if not omit_jti:
            # Mandatory. Its absence is a hard schema failure whose reason appears only in
            # Vault's server log — see the module docstring, and the break fixture that
            # exists to make that failure familiar.
            claims["jti"] = uuid.uuid4().hex
        payload = b64(json.dumps(claims, separators=(",", ":")).encode())
        signing_input = f"{header}.{payload}"
        signed = _vault(
            SIGN_PATH,
            {
                "input": base64.b64encode(signing_input.encode()).decode(),
                "hash_algorithm": "sha2-256",
                # ES256 in JWS form. ASN.1 — transit's default — is not something JWS can read.
                "marshaling_algorithm": "jws",
            },
        )["data"]["signature"]
        return f"{signing_input}.{signed.split(':')[-1]}"

    return _mint


@pytest.fixture
def reaches() -> Any:
    """Does this grant reach this path? The answer is Vault's, not ours.

    Returns a bool rather than raising, because both outcomes are results: a row asserting a
    refusal is as much a pass as one asserting access.
    """

    def _reaches(grant: str, path: str) -> bool:
        try:
            _vault(path, token=grant)
        except urllib.error.HTTPError:
            return False
        return True

    return _reaches


@pytest.fixture
def vault_log() -> Iterator[Any]:
    """The Vault server's own account of why it refused.

    Necessary because the HTTP response never says. Yields a callable returning the log lines
    written since the fixture was entered, so a row can assert on the reason for *its* refusal
    rather than on whatever the last one was.
    """
    container = _vault_container()
    marker = subprocess.run(
        ["docker", "logs", "--tail", "1", container], capture_output=True, text=True, check=False
    ).stderr.strip()

    def _since() -> str:
        out = subprocess.run(
            ["docker", "logs", "--tail", "400", container],
            capture_output=True,
            text=True,
            check=False,
        )
        text = out.stderr + out.stdout
        return text.split(marker, 1)[-1] if marker and marker in text else text

    yield _since


def _vault_container() -> str:
    result = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}}"], capture_output=True, text=True, check=False
    )
    names = [n for n in result.stdout.split() if "vault" in n.lower()]
    if not names:
        pytest.fail(
            "the trust store container is not running — `make dev-up` brings it up. Not "
            "skippable: these rows assert what Vault refuses, which cannot be observed if "
            "Vault is not there to refuse it."
        )
    return names[0]
