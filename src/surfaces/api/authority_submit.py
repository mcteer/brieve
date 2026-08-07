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
from dataclasses import dataclass
from typing import Any

from core.authority.changes import BlockedPendingApprovalError, ChangeDisposition
from core.errors import CoreError
from core.identity.claims import ClaimMapping
from core.identity.mappings_store import mapping_key


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

    def record_path(self, mapping: ClaimMapping) -> str:
        """Where this mapping's record lives — the path `VaultClaimMappings` reads.

        Public because the two ends agreeing is a property worth asserting rather than
        assuming. They agree structurally, by sharing `mapping_key` and the same
        configured prefix, and this is what lets a test say so without a socket.
        """
        return f"{self._path}/{mapping_key(mapping)}"

    @property
    def _mount(self) -> str:
        """The KV mount the configured path sits on — `harness-authority` in practice.

        **Derived from `controlled_path` rather than configured separately**, so the two
        cannot disagree. A second variable would be a second place to get the mount wrong,
        and the failure would be a 404 that reads as "no such record" rather than as
        "misconfigured" — the trap `read_path`'s docstring names for exactly this shape.
        """
        return self._path.split("/", 1)[0]

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
        # One record per mapping. Writing every mapping to the configured path itself —
        # which is what this did — meant the second approved mapping overwrote the first,
        # so granting one person a role revoked someone else's. Nothing caught it because
        # nothing read the records back at all.
        status, body = self._post(payload, self.record_path(mapping))

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

    def submit_change(self, change: ConfigChange) -> ChangeOutcome:
        """Submit a governance change and **return** which of the three things happened.

        **Returns rather than raises, and that is the difference from `submit`.** 007's method
        raises on pending and denied because its caller is an HTTP route mapping each to a
        status code, and the asymmetry protects it: a caller treating "returned normally" as
        success cannot accidentally treat a queued request as an applied one. The console
        needs all three as *data* — it renders pending, applied-and-ungated, and refused as
        three different things on one page — so this returns an outcome and the route decides
        the status.

        The truthiness lesson is 007's and is kept verbatim: `wrap_info` is present as `null`
        on **every** Vault response, so `"wrap_info" in body` is true for all inputs and proves
        nothing. Three tests once passed regardless of behaviour on exactly that.
        """
        body: dict[str, Any] = {"data": {**change.payload, "set_by": f"console/{change.requester}"}}
        if change.cas is not None:
            # KV v2 puts the guard in `options`, not in `data`. A `cas` written into the body
            # would be stored as an ordinary field and guard nothing — a check-and-set that
            # silently is not one.
            body["options"] = {"cas": change.cas}

        status, response = self._post(body, change.path_within(self._mount))

        # **KV v2 answers a failed check-and-set with 400, not 409**, and the live leg is what
        # established that. The first version checked for 409 on the reasonable assumption
        # that a conflict is a conflict — and the hermetic row passed because it scripted the
        # same assumption, which is the shape of a test that agrees with its author rather
        # than with the product.
        #
        # So the discriminator is Vault's own message. A bare 400 is a malformed request and
        # stays `AuthoritySubmitUnavailable`; only the CAS text is `RecordMoved`, because
        # telling an administrator "somebody else got there first" when the truth is "your
        # request was malformed" sends them to look for a colleague who does not exist.
        if status == 400 and _is_cas_mismatch(response):
            raise RecordMoved(
                f"the {change.record} record changed since it was read; re-read it and "
                f"resubmit rather than overwriting somebody else's change"
            )
        if status == 403:
            raise AuthorityChangeRefused(
                f"the trust fabric denied the {change.record} change requested by "
                f"{change.requester}"
            )
        if status >= 400:
            raise AuthoritySubmitUnavailable(
                f"the trust fabric answered {status} for {change.record}"
            )

        wrap = response.get("wrap_info")
        if wrap:
            accessor = wrap.get("accessor") if isinstance(wrap, dict) else None
            return ChangeOutcome(
                state="pending",
                accessor=str(accessor) if accessor else "",
                expires_at=str((wrap or {}).get("creation_time", "")),
            )
        return ChangeOutcome(state="applied")

    def _post(self, payload: dict[str, Any], path: str) -> tuple[int, dict[str, Any]]:
        request = urllib.request.Request(  # noqa: S310 — fixed scheme, operator-supplied addr
            f"{self._addr}/v1/{path}",
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


#: The records the console may request a change to (044, research R2).
#:
#: **A closed set, enumerated here and granted in `authority-submit.tf`**, and the two must
#: agree — `test_console_controlled_paths.py` asserts the grant matches the Control Group's
#: list, and `unknown_record` below refuses anything outside this one before a socket opens.
#: An open-ended record argument would let a caller aim the submitter at `harness-ceilings`,
#: which is the escalation this feature spent its safety case preventing at every other layer.
CONSOLE_RECORDS: frozenset[str] = frozenset(
    {"ask-bindings", "product-connections", "claim-mappings"}
)


def _is_cas_mismatch(response: dict[str, Any]) -> bool:
    """Whether a 400 is Vault's check-and-set refusal rather than a malformed request.

    Matched on the message because Vault gives no code: KV v2 answers
    ``{"errors": ["check-and-set parameter did not match the current version"]}``, verified
    against the real product rather than assumed.

    Matching on prose is ordinarily how a check comes to mean something else after an upgrade
    — this repository has five such findings — so the failure mode is chosen deliberately: an
    unrecognised message falls through to `AuthoritySubmitUnavailable`, which is the safe
    direction. A concurrent edit then reads as an outage (loud, and the administrator retries)
    rather than an outage reading as a concurrent edit (quiet, and they overwrite).
    """
    errors = response.get("errors") or []
    return any("check-and-set" in str(error) for error in errors)


class RecordMoved(CoreError):
    """The record changed between the read and the write (044, FR-020/US5).

    Its own type because the response is its own: not a denial and not an outage, but two
    administrators editing one record. `vault_write` already recorded why an unguarded write
    is the wrong answer — the losing write leaves no trace — and this is that reasoning at the
    configuration layer, where the two writers are people rather than steps.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.reason_code = "record_moved"


@dataclass(frozen=True)
class ChangeOutcome:
    """Which of the three things the fabric did. Never collapsed (FR-006)."""

    #: `applied` or `pending`. Refusals raise — they are not an outcome to render beside
    #: success, and 007's mapping already distinguishes denied from unreachable.
    state: str
    #: The wrapping token's accessor, when pending: what an approver acts on.
    accessor: str = ""
    #: When the pending request stops being actionable. Vault's own withdrawal mechanism,
    #: which is why 044 builds none of its own (research R11).
    expires_at: str = ""

    @property
    def is_pending(self) -> bool:
        return self.state == "pending"


@dataclass(frozen=True)
class ConfigChange:
    """One requested change to one governance record (044).

    Generalises what `ClaimMapping` did for one record type. The submitter's three-outcome
    mapping is unchanged — that logic is 007's and it is the part worth reusing rather than
    reimplementing, because its subtlety (`wrap_info` present-as-null on every response) is
    exactly the kind that gets lost in a second copy.
    """

    #: Which record. Refused unless in :data:`CONSOLE_RECORDS`.
    record: str
    #: The record's own body, already validated by the record's parser — the route does that
    #: **before** submitting, so an unqualified cell never reaches the fabric (FR-009).
    payload: dict[str, Any]
    #: Who asked. Carried into the record as `set_by` so provenance is readable from the
    #: record itself rather than from a second store that could disagree (FR-019).
    requester: str
    #: The KV v2 version the administrator read. A stale value means the record moved under
    #: them, and `vault_write` already recorded why an unguarded write is unresolvable.
    cas: int | None = None
    #: For `claim-mappings`, which mapping — the per-mapping suffix 007 added after finding
    #: that one path for every mapping meant granting one person a role revoked another's.
    key: str = ""

    def path_within(self, mount: str) -> str:
        """Where this change lands, under the configured mount."""
        if self.record not in CONSOLE_RECORDS:
            raise AuthorityChangeRefused(
                f"{self.record!r} is not a record the console may change. The writable set is "
                f"{sorted(CONSOLE_RECORDS)} — anything else is estate governance this feature "
                f"deliberately left in Terraform."
            )
        if self.record == "claim-mappings":
            if not self.key.strip():
                raise AuthorityChangeRefused(
                    "a claim-mapping change names no mapping; one path for every mapping is "
                    "how granting one person a role came to revoke someone else's"
                )
            return f"{mount}/data/claim-mappings/{self.key.strip()}"
        return f"{mount}/data/{self.record}"


__all__ = [
    "CONSOLE_RECORDS",
    "AuthorityChangeRefused",
    "ChangeOutcome",
    "AuthoritySubmitUnavailable",
    "ConfigChange",
    "RecordMoved",
    "VaultAuthoritySubmitter",
]
