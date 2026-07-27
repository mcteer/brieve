# SPDX-License-Identifier: Apache-2.0
"""Submitting an authority change to the trust fabric.

The surface **requests**; Vault's Control Groups decide. This module is the wire between
them, and it exists as its own module because the alternative — a function inside the
route that always returns "pending" — is a passing stub in the shape ADR-0047 forbids: the
row goes green while nothing was ever submitted anywhere.

Vault distinguishes the three outcomes natively, and the mapping is the whole job:

- **200 with a non-null ``wrap_info``** — queued for approval. The wrapping token is the
  pending request; the change has *not* happened.
- **200 without ``wrap_info``** — applied. Either no gate is attached to this path, or the
  caller's token already satisfied it.
- **403** — denied. Not queued, not pending: refused.

``wrap_info`` is present as a key with value ``null`` on **every** Vault response, so
``"wrap_info" in body`` is true for all inputs and proves nothing. 007 found this the hard
way: three tests passed regardless of behaviour. Truthiness is the only real signal, and
the mistake is invisible because the passing case looks identical.
"""

from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.request
from typing import Any

from core.authority.changes import BlockedPendingApprovalError, ChangeDisposition
from core.errors import CoreError
from core.identity.claims import ClaimMapping


class AuthorityChangeRefused(CoreError):
    """The trust fabric refused the change outright. Not pending — denied."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.reason_code = "authority_change_denied"


class AuthoritySubmitUnavailable(CoreError):
    """The trust fabric could not be reached.

    Fail closed: an unreachable approval mechanism blocks the *change*. Runs already
    holding authority are unaffected — failing closed on the wrong thing here would halt
    the platform during a Vault blip.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.reason_code = "authority_fabric_unavailable"


class VaultAuthoritySubmitter:
    """Writes a claim-to-role mapping change to a Control-Group-gated Vault path."""

    def __init__(
        self,
        *,
        vault_addr: str | None = None,
        controlled_path: str,
        token: str | None = None,
        cacert: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._addr = (vault_addr or os.environ.get("VAULT_ADDR") or "http://127.0.0.1:8200").rstrip(
            "/"
        )
        self._path = controlled_path.strip("/")
        self._token = token
        self._timeout = timeout
        # Explicit first, environment second. The control plane serves TLS from its own
        # CA, which is in no system trust store — and urllib does not read VAULT_CACERT,
        # that is a Vault CLI convention. Without this the failure surfaces as "the trust
        # fabric is unreachable" rather than as a certificate problem, which sends whoever
        # is debugging it to look at the wrong component entirely.
        ca = cacert or os.environ.get("VAULT_CACERT")
        self._ssl = ssl.create_default_context(cafile=ca) if ca else None

    def submit(self, *, requester: str, mapping: ClaimMapping) -> ChangeDisposition:
        """Submit the change; raise if it is pending or denied.

        Returns only on the *applied* path, which in a gated deployment should not happen
        — and that asymmetry is deliberate. A caller that treats "returned normally" as
        success cannot accidentally treat a queued request as an applied one.
        """
        payload = {
            "data": {
                "claim_name": mapping.claim_name,
                "claim_value": mapping.claim_value,
                "role": mapping.role,
                "requested_by": requester,
            }
        }
        status, body = self._post(payload)

        if status == 403:
            raise AuthorityChangeRefused(
                f"the trust fabric denied the mapping change requested by {requester}"
            )
        if status >= 400:
            raise AuthoritySubmitUnavailable(f"the trust fabric answered {status} for {self._path}")

        wrap = body.get("wrap_info")
        if wrap:
            accessor = wrap.get("accessor") if isinstance(wrap, dict) else None
            raise BlockedPendingApprovalError(
                f"claim mapping {mapping.claim_name}={mapping.claim_value} -> {mapping.role} "
                f"requested by {requester} is awaiting quorum",
                accessor=str(accessor) if accessor else None,
            )

        # No wrapping token: the write went through. Correct when no gate is attached,
        # which is the development default and must never be the production one.
        return ChangeDisposition.APPROVED

    def _post(self, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        request = urllib.request.Request(  # noqa: S310 — fixed scheme, operator-supplied addr
            f"{self._addr}/v1/{self._path}",
            data=json.dumps(payload).encode(),
            headers={
                "Content-Type": "application/json",
                **({"X-Vault-Token": self._token} if self._token else {}),
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(  # noqa: S310
                request, timeout=self._timeout, context=self._ssl
            ) as response:
                raw = response.read()
                parsed: dict[str, Any] = json.loads(raw) if raw else {}
                return response.status, parsed
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            try:
                return exc.code, json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                return exc.code, {}
        except OSError as exc:
            raise AuthoritySubmitUnavailable(
                f"the trust fabric is unreachable at {self._addr}: {exc}"
            ) from exc


__all__ = [
    "AuthorityChangeRefused",
    "AuthoritySubmitUnavailable",
    "VaultAuthoritySubmitter",
]
