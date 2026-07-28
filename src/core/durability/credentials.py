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
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from core.errors import CoreError

DEFAULT_VAULT_ADDR = "http://127.0.0.1:8200"
DEFAULT_JWT_AUTH_PATH = "nomad"
DEFAULT_VAULT_ROLE = "harness"
DEFAULT_CREDS_PATH = "database/creds/harness"

#: How long a trust-fabric read may take before it fails closed (FR-018).
#:
#: **Seconds-scale by requirement, not by taste.** Identity resolution sits on the invoke
#: path, so a generous timeout does not degrade gracefully — it holds a step open, and a
#: step held open indefinitely is a run that neither completes nor suspends. That is worse
#: than a refusal, because nothing notices it.
#:
#: Overridable per deployment, because what is generous depends on where the trust fabric
#: sits relative to the workload. The default exists so the value is never implicitly
#: whatever the HTTP library chose.
DEFAULT_RESOLUTION_TIMEOUT_SECONDS = 5.0


class CredentialUnavailableError(CoreError):
    """No credential could be obtained. Fail closed — never fall back to a static one."""

    def __init__(self, message: str, *, correlation_id: str | None = None) -> None:
        super().__init__(message, correlation_id=correlation_id)
        self.reason_code = "credential_unavailable"


class VaultReadFailed(CoreError):
    """A trust-fabric read did not answer.

    Distinct from "the path is not there", which :meth:`VaultDatabaseCredentials.read_path`
    reports by returning ``None``. **Absence is data; unreachability is an error**, and
    collapsing them would let a deleted ceiling record look exactly like a network
    partition — one of which is a configuration mistake and the other an outage, with
    opposite responses.

    ``timed_out`` distinguishes the two failure modes the fabric maps to different reason
    codes: a fabric that refused to answer and one that took too long.
    """

    def __init__(
        self,
        message: str,
        *,
        timed_out: bool = False,
        status: int | None = None,
        detail: str = "",
        correlation_id: str | None = None,
    ) -> None:
        super().__init__(message, correlation_id=correlation_id)
        self.timed_out = timed_out
        #: HTTP status and body, carried because **absence is engine-specific**. KV v2
        #: answers a missing key with 404; the `agent_registry` engine answers a missing
        #: registration with 400 and a message. A caller that knows which engine it is
        #: talking to can recognise its absence signature; this class deliberately does
        #: not guess, because guessing wrong turns "no such record" into "outage".
        self.status = status
        self.detail = detail
        self.reason_code = "fabric_timeout" if timed_out else "fabric_unreachable"


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
        timeout: float = DEFAULT_RESOLUTION_TIMEOUT_SECONDS,
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

    def login(self) -> str:
        """Exchange this workload's attested identity for a Vault token.

        Extracted from :meth:`fetch` so the same identity can reach more than one path.
        The identity fabric reads several unrelated ones — a registration, a ceiling
        record, a role binding — and a second class that authenticated its own way would
        be a second authentication path to the trust fabric, which is the shape Principle
        II forbids for tools and is no more attractive here.
        """
        login = self._post(
            f"auth/{self._auth_path}/login",
            {"role": self._role, "jwt": self._identity.jwt()},
        )
        token: str = login["auth"]["client_token"]
        return token

    def read_path(self, path: str, *, token: str | None = None) -> dict[str, Any] | None:
        """Read one Vault path as this workload. ``None`` means the path is not there.

        **The return type carries the distinction that matters.** A missing ceiling record
        and an unreachable trust fabric are a configuration mistake and an outage
        respectively, with opposite responses — so absence returns ``None`` and everything
        else raises :class:`VaultReadFailed`. A reader that collapsed them would refuse
        identically for both and send whoever investigates to the wrong system.

        Pass ``token`` to reuse a login across reads. Logging in per read would multiply
        the timeout budget by the number of paths, which is how a bounded wait stops being
        bounded in the only case that matters — the slow one.
        """
        try:
            tok = token if token is not None else self.login()
            return self._get(path, tok)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                # Vault's "no value at path". Data, not failure.
                return None
            try:
                detail = exc.read().decode(errors="replace")[:500]
            except Exception:  # noqa: BLE001 - the original failure is what matters
                detail = ""
            raise VaultReadFailed(
                f"trust fabric refused {path!r} at {self._addr} "
                f"as role {self._role!r}: HTTP {exc.code} {detail}",
                status=exc.code,
                detail=detail,
            ) from exc
        except TimeoutError as exc:
            raise VaultReadFailed(
                f"trust fabric did not answer {path!r} at {self._addr} within {self._timeout}s",
                timed_out=True,
            ) from exc
        except OSError as exc:
            # urllib wraps socket timeouts in URLError, so the timeout arrives here rather
            # than as TimeoutError — checking the cause is what keeps a slow fabric
            # distinguishable from an absent one.
            timed_out = isinstance(getattr(exc, "reason", None), TimeoutError)
            raise VaultReadFailed(
                f"trust fabric unreachable for {path!r} at {self._addr}: {type(exc).__name__}",
                timed_out=timed_out,
            ) from exc

    def list_path(self, path: str, *, token: str | None = None) -> list[str] | None:
        """List the keys under a Vault path. ``None`` means the folder is not there.

        Vault's LIST is a GET with ``?list=true`` rather than a distinct verb, which is the
        kind of detail that costs an afternoon exactly once — a plain GET on a folder
        returns 404 and reads as "nothing is registered" rather than "you asked wrongly".

        Same absence-versus-failure contract as :meth:`read_path`: a missing folder is data
        and returns ``None``; anything else raises.
        """
        response = self.read_path(f"{path}?list=true", token=token)
        if response is None:
            return None
        keys = (response.get("data") or {}).get("keys") or []
        return [str(k) for k in keys]

    def fetch(self) -> DatabaseCredential:
        """Authenticate as this workload and mint a credential."""
        try:
            token = self.login()
            creds = self._get(self._creds_path, token)
        except CredentialUnavailableError:
            raise
        except urllib.error.HTTPError as exc:
            # Vault says WHY in the body, and without it every failure here reads as
            # "HTTPError" — which names the credential path rather than the cause and
            # sends whoever is debugging to the wrong component. A role whose bound claims
            # do not match the presenting workload and an expired identity look identical
            # otherwise.
            try:
                detail = exc.read().decode(errors="replace")[:500]
            except Exception:  # noqa: BLE001 - the original failure is what matters
                detail = ""
            raise CredentialUnavailableError(
                f"could not obtain a database credential from Vault at {self._addr} "
                f"as role {self._role!r}: HTTP {exc.code} {detail}"
            ) from exc
        except Exception as exc:
            raise CredentialUnavailableError(
                f"could not obtain a database credential from Vault at {self._addr} "
                f"as role {self._role!r}: {type(exc).__name__}"
            ) from exc

        data = creds.get("data") or {}
        username, password = data.get("username"), data.get("password")
        if not username or not password:
            raise CredentialUnavailableError("Vault returned no database credential")
        return DatabaseCredential(
            username=username, password=password, lease_id=creds.get("lease_id", "")
        )
