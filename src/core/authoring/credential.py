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

import os
from dataclasses import dataclass
from datetime import datetime, timedelta

from core.durability.credentials import CredentialUnavailableError, WorkloadIdentity

#: Where the App key lives. The trust fabric's own mount, operator-authored and read-only to
#: runs — never the per-agent secret space a pack tool reaches, which a run can write.
DEFAULT_APP_KEY_PATH = "harness-authority/data/authoring/vcs-app"

#: An hour, matching the workload identity's own TTL. Long enough to open a proposal, short
#: enough that a leaked token is a window rather than a key.
DEFAULT_TTL = timedelta(hours=1)


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
        app_key_path: str = DEFAULT_APP_KEY_PATH,
        ttl: timedelta = DEFAULT_TTL,
    ) -> None:
        self._identity = identity
        self._app_key_path = app_key_path
        self._ttl = ttl

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

    def token_for(self, installation: str) -> InstallationToken:
        """Mint a token scoped to one installation.

        Raises:
            CredentialUnavailableError: this task holds no attested identity — which is the
                expected answer in the analysing task, and the reason it cannot publish.
        """
        jwt = self._identity.jwt()
        if not jwt:
            raise CredentialUnavailableError(
                "no attested workload identity; this task cannot read the App key and "
                "therefore cannot publish"
            )
        raise NotImplementedError(  # pragma: no cover - reached only against a live estate
            "the trust fabric's App-key exchange is provisioned by the estate and exercised in "
            "the enclave lane; it is deliberately absent from the hermetic path, which has no "
            "fabric to read and must not pretend otherwise"
        )


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
    "DEFAULT_APP_KEY_PATH",
    "DEFAULT_TTL",
    "InstallationToken",
    "AuthoringCredentials",
    "analysing_task_holds_no_credential",
]
