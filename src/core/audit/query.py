# SPDX-License-Identifier: Apache-2.0
"""The evidence read seam.

Deliberately a *different* protocol from :class:`~core.audit.sink.AuditSink`, with no
write method of any kind. Mutation is not unimplemented here and does not raise — it is
absent from the type, so there is nothing to call.

That is defence #1 of two. It holds while application code is correct, and it is the one a
future refactor removes by handing the evidence path a writable connection. Defence #2 is
the Vault dynamic role behind :class:`~core.audit.postgres_query.PostgresEvidenceQuery`,
which holds ``SELECT`` and nothing else, so Postgres refuses the write regardless of what
the Python does. ADR-0035 requires this be "an implementation property to prove rather
than assert", and one application-layer check is a convention that survives exactly until
someone passes the wrong object.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from core.audit.schema import AuditEntry, AuditEventType


class EvidenceQueryRequest(BaseModel):
    """A bounded read against the evidence plane.

    Every field a caller supplies can only **narrow**. The bounding dimension —
    ``tenant_id`` — comes from the authenticated subject and is not accepted from the
    request, because a caller-supplied tenant would be a request to widen scope.

    Which is what makes FR-011's cross-tenant case reachable in only one way: narrowing to
    a ``correlation_id`` belonging to another tenant. There is no tenant parameter to
    misuse, so a check written against one would assert something the surface does not
    expose and pass regardless of behaviour.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    #: From the subject, never from the request.
    tenant_id: str
    correlation_id: str | None = None
    #: 005 defaults a run's ``run_id`` to its correlation ID, so this narrows the same
    #: column rather than implying a second one the entries do not carry.
    run_id: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    event_types: frozenset[AuditEventType] | None = None
    limit: int = 1000


class EvidenceQuery(Protocol):
    """Read-only access to the evidence plane. There is no ``append`` here by design."""

    def search(self, request: EvidenceQueryRequest) -> list[AuditEntry]:
        """Return entries within the request's scope. Never widens it."""
        ...

    def exists_outside_tenant(self, *, correlation_id: str, tenant_id: str) -> bool:
        """Whether this stream exists under some **other** tenant.

        Required for FR-011 to be satisfiable at all. A cross-tenant attempt and a
        legitimately empty query both return zero rows, so the distinction cannot be
        derived from the result — something has to know that the named stream exists but
        is not yours. Without this the trail would record both as "empty", and an
        investigator could never tell "nothing happened" from "you may not see it".

        Returns a **boolean and nothing else**. No content crosses the tenant boundary,
        and the answer never reaches the caller: it selects which disposition is recorded,
        while the caller sees zero rows either way.
        """
        ...


__all__ = ["EvidenceQuery", "EvidenceQueryRequest"]
