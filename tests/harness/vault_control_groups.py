# SPDX-License-Identifier: Apache-2.0
"""Fixtures for exercising Vault Control Groups against the real trust store.

**There is no fake here, deliberately.** A fake that always approves proves the caller can
proceed; one that never approves proves it handles denial. Neither proves the gate holds,
which is the only claim worth making — the same reasoning that put the durability rows on
real Postgres.

One constraint worth knowing before reading further: **a root token bypasses Control
Groups entirely.** Verified against a running Vault — root wrote to a gated path with no
approval and no denial. So every assertion here must run under a NON-ROOT identity. Using
the root token would produce a green suite that proves nothing, which is worse than a red
one.

That is also why the production profile revokes the bootstrap credential: revocation is
not hygiene, it is what makes the gate real.
"""

from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _env_value(key: str) -> str:
    env = _repo_root() / ".env"
    if not env.is_file():
        return ""
    for line in env.read_text().splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip().strip('"')
    return ""


@dataclass
class VaultAdmin:
    """A privileged client used only to SET UP a test — never to assert with.

    Named for what it is so nobody reaches for it in an assertion: writes made through
    this client bypass the gate, which is exactly the thing under test.
    """

    addr: str = field(default_factory=lambda: _env_value("VAULT_ADDR") or "http://127.0.0.1:8200")
    token: str = field(
        default_factory=lambda: os.environ.get("VAULT_TOKEN") or _env_value("VAULT_ROOT_TOKEN")
    )
    cacert: str = field(default_factory=lambda: _env_value("VAULT_CACERT"))

    def _context(self) -> ssl.SSLContext | None:
        return ssl.create_default_context(cafile=self.cacert) if self.cacert else None

    def request(
        self,
        path: str,
        payload: dict[str, object] | None = None,
        *,
        method: str = "POST",
        token: str | None = None,
    ) -> tuple[int, dict[str, object]]:
        """Return (status, body). Never raises on 4xx — the status IS the assertion."""
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(  # noqa: S310
            f"{self.addr.rstrip('/')}/v1/{path}",
            data=data,
            headers={"X-Vault-Token": token or self.token, "Content-Type": "application/json"},
            method=method,
        )
        try:
            with urllib.request.urlopen(req, timeout=10, context=self._context()) as response:  # noqa: S310
                body = response.read()
                parsed: dict[str, object] = json.loads(body) if body else {}
                return response.status, parsed
        except urllib.error.HTTPError as exc:
            body = exc.read()
            try:
                err: dict[str, object] = json.loads(body) if body else {}
                return exc.code, err
            except json.JSONDecodeError:
                return exc.code, {"raw": body.decode(errors="replace")}

    def token_for(self, policy: str) -> str:
        """A NON-ROOT token carrying one policy. The only identity assertions may use."""
        status, body = self.request("auth/token/create", {"policies": [policy], "ttl": "10m"})
        assert status == 200, f"could not create a non-root token: {body}"
        auth = body["auth"]
        assert isinstance(auth, dict)
        token: str = auth["client_token"]
        return token


def reachable() -> bool:
    try:
        status, _ = VaultAdmin().request("sys/health", method="GET")
        return status in (200, 429, 473, 501, 503)
    except OSError:
        return False
