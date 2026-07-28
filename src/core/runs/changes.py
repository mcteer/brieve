# SPDX-License-Identifier: Apache-2.0
"""Submitted authority changes, so their outcome can be collected.

008 reasoned carefully about returning 202 rather than 403 when Control Groups gate a
change — *"a client that reads 403 stops asking, so a change approved twenty minutes later
is never collected"* — and then shipped no way to ask again. The accessor reached the
caller and nothing stored it. This is that record.

**The record is the authorization, not a cache.** Vault's `sys/control-group/request`
takes an accessor and answers whoever presents one. Without a requester and a tenant to
compare against, the accessor is a bearer capability that crosses tenants — hold one, poll
anything. Vault stays authoritative for the *disposition*; this record is authoritative for
*who may ask*.

**Collect cannot approve, and that is structural rather than careful.** The status endpoint
has no authorization semantics; authorizing is `sys/control-group/authorize`, a different
call this module never makes. FR-002 holds because the capability is absent, not because
the code is disciplined.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from core.errors import CoreError
from core.runs.refusals import OperationRefused


class ChangeStoreError(CoreError):
    """The change store could not be read or written. Never swallowed into "not found"."""


@dataclass(frozen=True)
class ChangeRequestRecord:
    """A change awaiting quorum, and who is entitled to ask about it."""

    accessor: str
    requester: str
    tenant_id: str
    claim_name: str
    claim_value: str
    role: str
    submitted_at: datetime


@dataclass(frozen=True)
class CollectedDisposition:
    """What the trust fabric says about a change now.

    ``pending`` is a legitimate answer indefinitely, and the field exists so a caller
    cannot mistake it for a failure — which is the mistake 008 predicted clients would make
    with a 403, one layer along.
    """

    accessor: str
    disposition: str
    #: How many approvals the fabric has recorded so far.
    approvals: int = 0
    #: What the pending change would write, as the fabric reports it. Useful to a person
    #: deciding whether the thing they asked for is the thing that is queued.
    request_path: str = ""

    # **There is deliberately no `required` field.** The status endpoint reports who has
    # approved (`authorizations`) and does not report how many approvals are needed — a
    # first version of this model carried `required` and it was always 0, which a caller
    # would read as "no approvals needed", i.e. approved. A field that is always the most
    # dangerous possible value is worse than an absent one, and the enclave row is what
    # surfaced it: the hermetic double had happily returned a plausible number.


class ChangeRequestStore(Protocol):
    """Where submitted changes are remembered until someone collects them."""

    def record(self, request: ChangeRequestRecord) -> None: ...

    def get(self, *, accessor: str, tenant_id: str) -> ChangeRequestRecord | None:
        """Tenant-scoped. ``None`` covers absent and another tenant's, deliberately."""
        ...


@dataclass
class InMemoryChangeRequestStore:
    """For hermetic rows and any surface assembled without a database."""

    requests: dict[str, ChangeRequestRecord] = field(default_factory=dict)

    def record(self, request: ChangeRequestRecord) -> None:
        self.requests[request.accessor] = request

    def get(self, *, accessor: str, tenant_id: str) -> ChangeRequestRecord | None:
        found = self.requests.get(accessor)
        if found is None or found.tenant_id != tenant_id:
            return None
        return found


class PostgresChangeRequestStore:
    """The real store, under the credentials the surface already holds."""

    def __init__(
        self,
        *,
        credentials: Any,
        host: str = "127.0.0.1",
        port: int = 5432,
        dbname: str = "brieve",
    ) -> None:
        self._credentials = credentials
        self._host = host
        self._port = port
        self._dbname = dbname

    def _connect(self) -> Any:
        import pg8000.dbapi

        cred = self._credentials.fetch()
        return pg8000.dbapi.connect(
            host=self._host,
            port=self._port,
            database=self._dbname,
            user=cred.username,
            password=cred.password,
        )

    def _run(self, work: Any) -> Any:
        conn = None
        try:
            conn = self._connect()
            return work(conn)
        except Exception as exc:
            raise ChangeStoreError(
                f"change store unavailable: {type(exc).__name__}: {exc}"
            ) from exc
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:  # noqa: BLE001 — a close failure must not mask the real one
                    pass

    def record(self, request: ChangeRequestRecord) -> None:
        def work(conn: Any) -> None:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO authority_change_requests "
                "(accessor, requester, tenant_id, claim_name, claim_value, role, submitted_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (accessor) DO NOTHING",
                (
                    request.accessor,
                    request.requester,
                    request.tenant_id,
                    request.claim_name,
                    request.claim_value,
                    request.role,
                    request.submitted_at,
                ),
            )
            conn.commit()

        self._run(work)

    def get(self, *, accessor: str, tenant_id: str) -> ChangeRequestRecord | None:
        def work(conn: Any) -> ChangeRequestRecord | None:
            cur = conn.cursor()
            cur.execute(
                "SELECT accessor, requester, tenant_id, claim_name, claim_value, role, "
                "       submitted_at FROM authority_change_requests "
                "WHERE accessor = %s AND tenant_id = %s",
                (accessor, tenant_id),
            )
            row = cur.fetchone()
            if row is None:
                return None
            stamp = row[6]
            return ChangeRequestRecord(
                accessor=str(row[0]),
                requester=str(row[1]),
                tenant_id=str(row[2]),
                claim_name=str(row[3]),
                claim_value=str(row[4]),
                role=str(row[5]),
                submitted_at=stamp if stamp.tzinfo else stamp.replace(tzinfo=UTC),
            )

        found: ChangeRequestRecord | None = self._run(work)
        return found


#: How the trust fabric says an accessor names nothing.
#:
#: **400 with this in the body, not 404** — probed against the live enclave rather than
#: assumed, because 010 was bitten by exactly this: the agent registry answers 400 for a
#: missing definition while KV answers 404, so absence is engine-specific and a reader that
#: generalised reported an outage for a thing that simply was not there.
CONTROL_GROUP_ABSENT_SIGNATURE = "invalid accessor"


class VaultChangeStatus:
    """Asks the trust fabric what has become of a gated change.

    **Status only.** Approving is `sys/control-group/authorize`, which this class does not
    know how to call — so FR-002's read-only property is held by an absent capability
    rather than by a careful implementation. That is the difference between a rule and a
    structure, and it is why the break fixture (a collect that authorizes) can only fail
    if someone reaches for a different endpoint on purpose.
    """

    def __init__(
        self,
        *,
        vault_addr: str | None = None,
        token: str | None = None,
        cacert: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        import os
        import ssl

        self._addr = (vault_addr or os.environ.get("VAULT_ADDR") or "http://127.0.0.1:8200").rstrip(
            "/"
        )
        self._token = token
        self._timeout = timeout
        # The control plane serves TLS from its own CA and urllib does not read
        # VAULT_CACERT — that is a CLI convention. Without this the failure surfaces as a
        # change-status problem rather than a certificate one, sending whoever debugs it to
        # the wrong component. The same trap `authority_submit.py` documents.
        ca = cacert or os.environ.get("VAULT_CACERT")
        self._ssl = ssl.create_default_context(cafile=ca) if ca else None

    def status_of(self, accessor: str) -> CollectedDisposition:
        """Current disposition, or refuse.

        An accessor the fabric does not know is `no_such_record` — the same answer a
        caller gets for another tenant's, so a caller cannot distinguish "never existed"
        from "not yours" by whether the fabric happens to remember it.
        """
        import json
        import urllib.error
        import urllib.request

        request = urllib.request.Request(  # noqa: S310 — fixed scheme, operator-supplied addr
            f"{self._addr}/v1/sys/control-group/request",
            data=json.dumps({"accessor": accessor}).encode(),
            headers={"Content-Type": "application/json"}
            | ({"X-Vault-Token": self._token} if self._token else {}),
            method="PUT",
        )
        try:
            with urllib.request.urlopen(  # noqa: S310
                request, timeout=self._timeout, context=self._ssl
            ) as response:
                body = json.loads(response.read())
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode(errors="replace")[:500]
            except Exception:  # noqa: BLE001 — the original failure is what matters
                pass
            if exc.code == 400 and CONTROL_GROUP_ABSENT_SIGNATURE in detail:
                raise OperationRefused(
                    "no such change request", reason_code="no_such_record"
                ) from exc
            raise ChangeStoreError(
                f"the trust fabric answered {exc.code} for accessor status: {detail}"
            ) from exc
        except Exception as exc:
            raise ChangeStoreError(
                f"the trust fabric could not be asked about {accessor!r}: {type(exc).__name__}"
            ) from exc

        data = body.get("data") or {}
        # `approved` is the fabric's own word for it. Anything else is still pending —
        # including states this platform has not seen — because guessing that an unknown
        # state means approved is the one direction that grants something.
        approved = bool(data.get("approved"))
        # `authorizations` is a LIST of who has approved, or null before anyone has —
        # not a count, which is what a first reading of the field name suggests.
        authorizations = data.get("authorizations") or []
        return CollectedDisposition(
            accessor=accessor,
            disposition="approved" if approved else "pending",
            approvals=len(authorizations) if isinstance(authorizations, list) else 0,
            request_path=str(data.get("request_path") or ""),
        )


def authorize_collect(
    record: ChangeRequestRecord | None,
    *,
    subject_user_id: str,
) -> ChangeRequestRecord:
    """Decide whether this caller may ask about this change, or refuse.

    Separate from the store because it is the *decision*, and a decision in its own
    function is one a row can exercise without a database. Two refusals, and only one of
    them tells the caller anything:

    - the record is absent or another tenant's — ``no_such_record`` / ``outside_tenant``,
      indistinguishable on the wire, because a response that told them apart would let
      anyone confirm an accessor exists somewhere else;
    - the record is this tenant's but someone else's — ``not_permitted``. The caller can
      already see the change exists, so the refusal names the reason.
    """
    if record is None:
        raise OperationRefused("no such change request", reason_code="no_such_record")
    if record.requester != subject_user_id:
        raise OperationRefused(
            "this change was requested by someone else", reason_code="not_permitted"
        )
    return record


__all__ = [
    "ChangeRequestRecord",
    "ChangeRequestStore",
    "ChangeStoreError",
    "CONTROL_GROUP_ABSENT_SIGNATURE",
    "CollectedDisposition",
    "InMemoryChangeRequestStore",
    "PostgresChangeRequestStore",
    "VaultChangeStatus",
    "authorize_collect",
]
