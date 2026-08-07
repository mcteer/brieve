# SPDX-License-Identifier: Apache-2.0
"""The publishing credential (038, ADR-0062; research R9).

**A run that opens a pull request must authenticate as something, and this platform held
nothing it could use.** Measured across `src/`, `infra/` and `.github/` before 038: no
version-control credential anywhere. 037's precedent does not transfer — its proposal is opened
by *CI*, which holds a token by virtue of being CI. A run holds nothing.

033 already refused the obvious answer and recorded the consequence rather than acquiring a
credential to hide it: a personal access token is the standing credential Principle IV forbids.
That refusal stands. What 033 did not need, and this does, is a credential a **run** can hold.

So this takes the shape every other credential here takes — attested workload identity → Vault →
something short-lived — and it is **Principle IV's third named exception**, amended into the
constitution in the same change rather than argued out of the enumeration.

**Here rather than in `core/durability/`** so a new credential class does not widen sealed core
beyond the four audit members this feature already carries there.

**Never mounted into the hardened tier.** The `analyzer` task holds no credential that could
publish; the `proposer` task never mounts the subject. That is a fact about which task holds
what, not a promise about behaviour — and it is why the two tasks exist.
"""

from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from core.durability.credentials import CredentialUnavailableError, WorkloadIdentity

#: Where the App key lives. The trust fabric's own mount, operator-authored and read-only to
#: runs — never the per-agent secret space a pack tool reaches, which a run can write.
DEFAULT_APP_KEY_PATH = "harness-authority/data/authoring/vcs-app"

#: An hour, matching the workload identity's own TTL. Long enough to open a proposal, short
#: enough that a leaked token is a window rather than a key.
DEFAULT_TTL = timedelta(hours=1)

#: The forge's API root. Overridable for GitHub Enterprise — and, more usefully here, so a row
#: can point the exchange at a local endpoint without the handler learning it is under test.
DEFAULT_API_ROOT = "https://api.github.com"

#: The App JWT's own lifetime. GitHub refuses anything over ten minutes; nine leaves room for
#: clock skew in both directions without approaching the ceiling. This token is never returned
#: to a caller — it exists for one request and dies inside `token_for`.
_APP_JWT_TTL = timedelta(minutes=9)

#: How far back the App JWT is dated. GitHub rejects a future `iat`, and a workload whose clock
#: runs slightly fast would otherwise mint tokens the forge refuses — a failure that reads as a
#: credential problem and is a clock problem. This estate has already been bitten by VM clock
#: drift breaking attestation, so the margin is deliberate rather than superstitious.
_APP_JWT_BACKDATE = timedelta(seconds=60)


class TrustStoreReader(Protocol):
    """Reads one path from the trust fabric under the caller's own attested identity.

    A *reader*, never a credential: `AuthoringCredentials` still accepts nothing that could
    authenticate to a forge. This exists so the App-key read goes through the same
    login-and-read path every other trust-fabric read uses, rather than a second one.
    """

    def read_path(self, path: str, *, token: str | None = None) -> dict[str, Any] | None:
        """Return the path's data, or ``None`` when it is not there."""
        ...


@dataclass(frozen=True)
class InstallationToken:
    """A short-lived, installation-scoped token. Never checkpointed, never logged.

    ``__repr__`` is overridden for the reason `DatabaseCredential`'s is: without it, a traceback
    or a debugger repr prints the token, and a credential that leaks through an exception path
    is one no policy about logging would have caught.
    """

    token: str
    installation: str
    expires_at: datetime

    def __repr__(self) -> str:  # pragma: no cover - defensive
        return (
            f"InstallationToken(installation={self.installation!r}, "
            f"expires_at={self.expires_at!r}, token=<redacted>)"
        )


class AuthoringCredentials:
    """Exchange this task's attested identity for an installation token.

    **Accepts no credential from a caller**, which is the property the whole design rests on:
    there is nowhere to pass a token in, so no jobspec, no dispatch payload and no checkpoint
    can carry one. `NomadWorkloadIdentity` reads what Nomad delivered to *this task*, and the
    two tasks are delivered different identities.
    """

    def __init__(
        self,
        *,
        identity: WorkloadIdentity,
        reader: TrustStoreReader | None = None,
        app_key_path: str = DEFAULT_APP_KEY_PATH,
        ttl: timedelta = DEFAULT_TTL,
        api_root: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._identity = identity
        self._reader = reader
        self._app_key_path = app_key_path
        self._ttl = ttl
        self._api_root = (api_root or os.environ.get("GITHUB_API_URL") or DEFAULT_API_ROOT).rstrip(
            "/"
        )
        self._timeout = timeout

    def _trust_store(self) -> TrustStoreReader:
        """The trust-fabric reader, which a caller supplies.

        **Supplied rather than constructed, because `core` is product-blind.** An earlier draft
        of this method imported the concrete trust-fabric client here and was caught by the
        repository's own guard: naming the substrate in `core` is how product knowledge gets in,
        and 038's record already lists one instance of it (`terraform_apply` hardcoded in a
        hook). The surface that knows which fabric this deployment runs constructs the reader;
        this module knows only that something can read a path.
        """
        if self._reader is None:
            raise CredentialUnavailableError(
                "no trust-fabric reader was supplied; `core` does not know which fabric this "
                "deployment runs, so the surface that does must pass one"
            )
        return self._reader

    def available(self) -> bool:
        """Whether this task holds an attested identity at all.

        The `analyzer` task does not, and that is the point rather than a failure — so a caller
        can assert the absence structurally instead of catching an exception and hoping it meant
        what it looked like.
        """
        try:
            self._identity.jwt()
        except CredentialUnavailableError:
            return False
        return True

    def _app_key(self) -> tuple[str, str]:
        """The App's id and private key, read from the trust fabric.

        Returns the pair rather than caching it on the instance: the key is the long-lived
        secret in this whole path, and holding it as process state for the life of a task
        widens the window in which a heap dump contains it. Reading it twice costs one trust-store
        round trip and is the cheaper mistake.
        """
        data = self._trust_store().read_path(self._app_key_path)
        if not data:
            raise CredentialUnavailableError(
                f"no App key at {self._app_key_path!r}; the authoring credential is "
                f"operator-seeded (ADR-0062) and this deployment has not seeded it"
            )
        # `read_path` returns the KV v2 inner data. Both spellings are accepted because the
        # seeding is operator work and a mismatch here would surface as a signing failure,
        # which names the wrong thing.
        app_id = str(data.get("app_id") or data.get("application_id") or "").strip()
        private_key = str(data.get("private_key") or data.get("pem") or "")
        if not app_id or not private_key.strip():
            raise CredentialUnavailableError(
                "the App key record is missing `app_id` or `private_key`; a partially seeded "
                "credential fails here rather than producing an unsigned request"
            )
        return app_id, private_key

    def _app_jwt(self, app_id: str, private_key: str, *, now: datetime) -> str:
        """Sign the App-level assertion. Never returned to a caller; it lives for one request."""
        import jwt as pyjwt  # `pyjwt[crypto]`, pinned in the `surfaces` extra

        claims = {
            "iat": int((now - _APP_JWT_BACKDATE).timestamp()),
            "exp": int((now + _APP_JWT_TTL).timestamp()),
            "iss": app_id,
        }
        signed: str = pyjwt.encode(claims, private_key, algorithm="RS256")
        return signed

    def token_for(self, installation: str) -> InstallationToken:
        """Mint a token scoped to one installation.

        Three steps, and the ordering is the security property: this task's **own** attested
        identity opens the trust fabric, the fabric yields the App key, and the App key buys a
        token scoped to one installation. Nothing here accepts material from a caller, so there
        is no path by which a jobspec, a dispatch payload or a checkpoint could supply one.

        Raises:
            CredentialUnavailableError: this task holds no attested identity — which is the
                expected answer in the analysing task, and the reason it cannot publish — or
                the fabric holds no App key, or the forge refused the assertion.
        """
        jwt = self._identity.jwt()
        if not jwt:
            raise CredentialUnavailableError(
                "no attested workload identity; this task cannot read the App key and "
                "therefore cannot publish"
            )
        app_id, private_key = self._app_key()
        now = datetime.now(UTC)
        assertion = self._app_jwt(app_id, private_key, now=now)
        request = urllib.request.Request(  # noqa: S310 — fixed scheme, operator-supplied root
            f"{self._api_root}/app/installations/{installation}/access_tokens",
            data=b"",
            headers={
                "Authorization": f"Bearer {assertion}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:  # noqa: S310
                payload: dict[str, Any] = json.loads(response.read())
        except urllib.error.HTTPError as exc:  # pragma: no cover - exercised in the enclave
            # The body may name the installation, never the key. Raising the raw error would
            # put the request's headers — including the assertion — into a traceback.
            raise CredentialUnavailableError(
                f"the forge refused the App assertion for installation {installation!r} "
                f"(HTTP {exc.code}); the App may not be installed on the target repository"
            ) from None
        token = str(payload.get("token") or "")
        if not token:
            raise CredentialUnavailableError(
                "the forge returned no token for this installation; refusing rather than "
                "proceeding with an empty credential"
            )
        return InstallationToken(
            token=token,
            installation=installation,
            expires_at=_expiry(payload.get("expires_at"), fallback=now + self._ttl),
        )


def _expiry(raw: object, *, fallback: datetime) -> datetime:
    """The forge's stated expiry, or our own bound when it says nothing usable.

    Falling back rather than raising: a token that works with an expiry we inferred is more
    useful than a refusal, and the fallback is never *longer* than what we asked for — so an
    unparseable value cannot extend the credential's life.
    """
    if isinstance(raw, str) and raw.strip():
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return fallback
    return fallback


def analysing_task_holds_no_credential(env: dict[str, str] | None = None) -> tuple[bool, str]:
    """Whether the current environment is one that could publish, and why.

    Returns a reason rather than a bare boolean because the row asserting it needs to say which
    clause held — an assertion that reports only `False` tells an operator nothing about what
    changed when it starts reporting `True`.
    """
    environ = env if env is not None else dict(os.environ)
    for name in sorted(environ):
        upper = name.upper()
        if "GITHUB" in upper and ("TOKEN" in upper or "KEY" in upper or "SECRET" in upper):
            return False, f"{name} is present in this task's environment"
        if upper in {"VCS_TOKEN", "VCS_APP_KEY"}:
            return False, f"{name} is present in this task's environment"
    return True, ""


__all__ = [
    "DEFAULT_API_ROOT",
    "DEFAULT_APP_KEY_PATH",
    "DEFAULT_TTL",
    "InstallationToken",
    "AuthoringCredentials",
    "TrustStoreReader",
    "analysing_task_holds_no_credential",
]
