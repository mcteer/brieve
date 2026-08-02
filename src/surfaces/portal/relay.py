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
        timeout: float | None = None,
    ) -> ApiResponse:
        """One operation, as this person. Every portal call goes through here.

        ``timeout`` is **per-operation patience**, and `None` means this relay's own — so every
        existing call site is untouched by its arrival (028).

        **A parameter rather than a second relay.** Asking takes far longer than anything else the
        portal does: measured 2026-08-02, roughly two minutes, because the model reasons before it
        answers and retrieval runs over an 856K corpus. Two relays with two defaults would be two
        egress points for the containment rows to reason about, and raising the shared default
        above would spend an ask's patience on a thread listing — the exact harm the ten seconds
        was chosen to avoid. One number stays the rule; one caller states its own exception.

        **The injected-transport branch deliberately does not receive it.** Both harnesses that
        inject a transport share a keyword-only signature, and widening it would touch every
        fixture for a value none of them uses. Patience is therefore asserted at *this* seam.
        """
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
            patience = self.timeout if timeout is None else timeout
            with urllib.request.urlopen(req, timeout=patience) as response:  # noqa: S310
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
