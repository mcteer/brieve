# SPDX-License-Identifier: Apache-2.0
"""The portal's one door to the platform.

**This is the only module in `surfaces/portal` that holds an HTTP client**, and a
conformance row asserts exactly that. The rule is what makes the portal's containment claim
checkable: if every request leaves through one function, then enumerating what the portal
can reach is reading one file rather than auditing a codebase.

**It carries the person's token, never a credential of its own.** The portal has no service
identity, no Vault access, and no client secret — the API sees the person, which is why a
run started from the portal is indistinguishable from one started through the API. It *is*
one.

Refusals come back as data rather than exceptions. A 403 from the API is not a portal error;
it is the platform answering, and the page's job is to render that answer honestly rather
than to present it as a malfunction.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

#: How long the portal waits on the API before giving up.
#:
#: Short: every portal request happens while a person is watching a page, and a page that
#: hangs teaches people to reload, which turns one slow request into several.
DEFAULT_TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True)
class ApiResponse:
    """What the API said. Never raises for a refusal — a refusal is an answer."""

    status: int
    payload: Any

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300

    @property
    def reachable(self) -> bool:
        """False only when the API could not be reached at all.

        Distinct from `ok` because the page renders them differently: a refusal says what
        the platform decided, and an unreachable API says the platform could not be asked.
        Collapsing them would show an empty platform to someone whose access is fine.
        """
        return self.status != 0


@dataclass
class ApiRelay:
    """Relays operations to the northbound API as the signed-in person."""

    base_url: str
    timeout: float = DEFAULT_TIMEOUT_SECONDS
    #: Injected by hermetic rows so the portal can be driven without a live API. It is a
    #: callable with this module's own signature, so a row exercises the portal's real
    #: request-shaping rather than a parallel one.
    transport: Any | None = None

    def request(
        self,
        method: str,
        path: str,
        *,
        token: str,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> ApiResponse:
        """One operation, as this person. Every portal call goes through here."""
        supplied = {k: v for k, v in (params or {}).items() if v is not None}
        query = f"?{urllib.parse.urlencode(supplied)}" if supplied else ""
        url = f"{self.base_url.rstrip('/')}{path}{query}"

        if self.transport is not None:
            injected: ApiResponse = self.transport(
                method=method, url=url, token=token, json_body=json_body
            )
            return injected

        data = json.dumps(json_body).encode() if json_body is not None else None
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(  # noqa: S310 — operator-supplied base, fixed scheme
            url, data=data, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:  # noqa: S310
                body = response.read()
                return ApiResponse(
                    status=response.status, payload=json.loads(body) if body else None
                )
        except urllib.error.HTTPError as exc:
            # A refusal, not a failure. Read the body so the page can say what the platform
            # decided rather than inventing a reason.
            try:
                body = exc.read()
                payload = json.loads(body) if body else None
            except Exception:  # noqa: BLE001 — an unparseable refusal is still a refusal
                payload = None
            return ApiResponse(status=exc.code, payload=payload)
        except Exception:  # noqa: BLE001 — the API could not be reached at all
            # Status 0 rather than 502: the portal did not receive a status, and inventing
            # one would make an outage indistinguishable from the API reporting one.
            return ApiResponse(status=0, payload=None)


__all__ = ["ApiRelay", "ApiResponse", "DEFAULT_TIMEOUT_SECONDS"]
