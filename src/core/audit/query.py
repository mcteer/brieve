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
    #: The newest N **of each requested type**, rather than N across all of them (029).
    #:
    #: **The defect this exists for is competition, not size.** `limit` alone bounds by row count
    #: over undifferentiated types, so a question about a rare type loses to whatever the estate
    #: does most. Measured on a real tenant: a question about runs received 1,000 of 63,947
    #: entries composed as `effect_observed` 383, `pre_decision` 302, … `run_start` 60. Sixty run
    #: records in a window of a thousand. Raising `limit` would not have helped — at any row count
    #: the common types crowd out the rare ones, which is why this bounds per type instead.
    #:
    #: `None` is **byte-for-byte today's read**, so every existing caller and row is untouched by
    #: its arrival. It narrows within an already-scoped read and can never widen one: `event_types`
    #: still decides what may be seen at all.
    limit_per_type: int | None = None


class SearchResult(list[AuditEntry]):
    """The entries, and — when the read was bounded — what it left out (029).

    **A list subclass, deliberately.** Every caller treats a read's result as a list of entries and
    should continue to: iterate it, count it, compare it to ``[]``. What FR-006 needs is one more
    fact *about* that list — how many of each requested type existed versus how many arrived — and
    a second method returning it would mean a second query, while a tuple return would break a
    dozen call sites to deliver something most of them do not want.

    So the result is still the entries; it simply knows its own provenance. ``window`` is empty
    when nothing was bounded, which is the common case and renders as no note at all.
    """

    def __init__(
        self,
        entries: list[AuditEntry] | None = None,
        *,
        window: dict[AuditEventType, tuple[int, int]] | None = None,
    ) -> None:
        super().__init__(entries or [])
        #: Per requested type: ``(returned, matched)``. A type whose two numbers differ was
        #: truncated, and the answer says so — the asker is the one about to act on it, and the
        #: access record in the trail serves the investigator instead.
        self.window: dict[AuditEventType, tuple[int, int]] = window or {}

    @property
    def truncated(self) -> dict[AuditEventType, tuple[int, int]]:
        """Only the types that were actually cut short. Empty means the answer is complete."""
        return {kind: counts for kind, counts in self.window.items() if counts[0] < counts[1]}


class EvidenceQuery(Protocol):
    """Read-only access to the evidence plane. There is no ``append`` here by design."""

    def search(self, request: EvidenceQueryRequest) -> SearchResult:
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


__all__ = ["EvidenceQuery", "EvidenceQueryRequest", "SearchResult"]
