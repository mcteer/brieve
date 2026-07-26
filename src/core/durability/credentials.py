# SPDX-License-Identifier: Apache-2.0
"""Database credentials, obtained by the workload as itself (FR-017a, FR-017b).

The chain, concretely (ADR-0048):

    Nomad workload identity JWT -> Vault JWT auth -> dynamic Postgres credential

Two things about the shape are deliberate and easy to get wrong:

**The workload performs the exchange itself.** Nomad can broker secrets into a task
through a ``vault`` stanza and ``template``, and that is the path most people reach for
first. It is not used here: a brokered secret lands in the task's environment or
filesystem and stays there for the life of the allocation, and it renews on Nomad's
schedule — so the workload could not re-fetch in response to the database's rejection,
which is the signal FR-017b actually reacts to.

**Refresh is reactive, not clock-driven.** A timer handles only the expiry it predicts.
An authentication failure is authoritative, and it also covers a credential revoked
early, a lease invalidated by a Vault operation, or a database restarted underneath the
run — with no clock agreement required between Vault, Postgres, and this process.

Note the vocabulary. The *run* re-authenticates to Vault on resume, which is a
Principle IV guarantee. The *provider* refreshes a database credential, which is
plumbing. They are not the same event and must not share a word.
"""

from __future__ import annotations

import json
import os
import ssl
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from core.errors import CoreError

DEFAULT_VAULT_ADDR = "http://127.0.0.1:8200"
DEFAULT_JWT_AUTH_PATH = "nomad"
DEFAULT_VAULT_ROLE = "harness"
DEFAULT_CREDS_PATH = "database/creds/harness"


class CredentialUnavailableError(CoreError):
    """No credential could be obtained. Fail closed — never fall back to a static one."""

    def __init__(self, message: str, *, correlation_id: str | None = None) -> None:
        super().__init__(message, correlation_id=correlation_id)
        self.reason_code = "credential_unavailable"


@dataclass(frozen=True)
class DatabaseCredential:
    """A Vault-minted, per-workload Postgres login. Never checkpointed, never logged."""

    username: str
    password: str
    lease_id: str

    def __repr__(self) -> str:  # pragma: no cover - defensive
        # Without this, a traceback or a debugger repr would print the password.
        return f"DatabaseCredential(username={self.username!r}, password=<redacted>)"


class WorkloadIdentity(Protocol):
    """Supplies the attestation. Fakes implement it; nothing here reads a static token."""

    def jwt(self) -> str:
        """Return the current workload identity JWT."""
        ...


class NomadWorkloadIdentity:
    """Reads the identity Nomad delivers to the task.

    Nomad exposes a named identity as ``NOMAD_TOKEN_<name>`` in the environment and, if
    ``file = true``, at ``secrets/nomad_<name>.jwt``. The file is preferred: it is
    re-read on every call, so a re-issued identity is picked up without a restart.
    """

    def __init__(self, name: str = "vault") -> None:
        self._name = name

    def jwt(self) -> str:
        secrets_dir = os.environ.get("NOMAD_SECRETS_DIR")
        if secrets_dir:
            path = Path(secrets_dir) / f"nomad_{self._name}.jwt"
            if path.is_file():
                return path.read_text().strip()
        token = os.environ.get(f"NOMAD_TOKEN_{self._name}")
        if token:
            return token.strip()
        raise CredentialUnavailableError(
            f"no Nomad workload identity {self._name!r} available. This process has no "
            "attested identity, so it cannot reach Vault or the database. Running the "
            "durability suite outside a Nomad allocation is the usual cause."
        )


class VaultDatabaseCredentials:
    """Exchange a workload identity for a dynamic Postgres credential."""

    def __init__(
        self,
        *,
        identity: WorkloadIdentity,
        vault_addr: str | None = None,
        auth_path: str = DEFAULT_JWT_AUTH_PATH,
        role: str = DEFAULT_VAULT_ROLE,
        creds_path: str = DEFAULT_CREDS_PATH,
        timeout: float = 10.0,
    ) -> None:
        self._identity = identity
        self._addr = (vault_addr or os.environ.get("VAULT_ADDR") or DEFAULT_VAULT_ADDR).rstrip("/")
        self._auth_path = auth_path
        self._role = role
        self._creds_path = creds_path
        self._timeout = timeout
        # The control plane serves TLS from its own CA, which is not in any system trust
        # store. urllib does NOT read VAULT_CACERT — that is a Vault CLI convention — so
        # without building the context here every request fails verification, and the
        # error surfaces as a credential problem rather than a certificate one.
        cacert = os.environ.get("VAULT_CACERT")
        self._ssl_context = ssl.create_default_context(cafile=cacert) if cacert else None

    def _post(
        self, path: str, payload: dict[str, object], token: str | None = None
    ) -> dict[str, Any]:
        request = urllib.request.Request(  # noqa: S310 — fixed scheme, operator-supplied addr
            f"{self._addr}/v1/{path}",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}
            | ({"X-Vault-Token": token} if token else {}),
            method="POST",
        )
        with urllib.request.urlopen(  # noqa: S310
            request, timeout=self._timeout, context=self._ssl_context
        ) as response:
            parsed: dict[str, Any] = json.loads(response.read())
            return parsed

    def _get(self, path: str, token: str) -> dict[str, Any]:
        request = urllib.request.Request(  # noqa: S310
            f"{self._addr}/v1/{path}", headers={"X-Vault-Token": token}
        )
        with urllib.request.urlopen(  # noqa: S310
            request, timeout=self._timeout, context=self._ssl_context
        ) as response:
            parsed: dict[str, Any] = json.loads(response.read())
            return parsed

    def fetch(self) -> DatabaseCredential:
        """Authenticate as this workload and mint a credential."""
        try:
            login = self._post(
                f"auth/{self._auth_path}/login",
                {"role": self._role, "jwt": self._identity.jwt()},
            )
            token = login["auth"]["client_token"]
            creds = self._get(self._creds_path, token)
        except CredentialUnavailableError:
            raise
        except Exception as exc:
            raise CredentialUnavailableError(
                f"could not obtain a database credential from Vault at {self._addr}: "
                f"{type(exc).__name__}"
            ) from exc

        data = creds.get("data") or {}
        username, password = data.get("username"), data.get("password")
        if not username or not password:
            raise CredentialUnavailableError("Vault returned no database credential")
        return DatabaseCredential(
            username=username, password=password, lease_id=creds.get("lease_id", "")
        )
