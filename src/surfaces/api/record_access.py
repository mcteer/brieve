# SPDX-License-Identifier: Apache-2.0
"""Recording that someone was shown a record about a run or a thread.

**A sibling of `evidence.py`, not an abstraction over it.** That module records who read the
audit plane; this one records who read records *about* runs and threads. The shape is
deliberately the same — a stable per-tenant stream, a payload carrying the shape of the access
and never its content, and a write whose failure fails the operation — because the arguments
for each of those were made once already and transfer unchanged (Principle VII).

**Why a second stream and not `evidence-access`.** One stream is simpler and genuinely tempting:
one chain per tenant, one query answering "who looked at anything". It was rejected on volume
profile. An evidence read is a deliberate act by someone conducting a review; `list_runs` is what
a connected editor calls while idling. Merged, the routine listings would permanently bury the
high-signal reads in the one stream an auditor opens first — and the trail is never sampled
(Principle IX), so that cannot be corrected later by filtering at write time.

**The cost of that choice, stated rather than discovered**: an auditor asking who looked at
anything in a tenant now queries two streams.

**Never the chain being read.** A read record refers to a run by correlation id; it is never
appended to that run's chain. Reading a run must not alter it — and 021's `RunReport` compiles
from a run's chain, so a read appended there would put "who read this run" inside the report of
that run, including reads of the report, growing every time anyone looked.
"""

from __future__ import annotations

from typing import Any, Final

from core.audit.schema import AuditEventType
from core.audit.sink import AuditSink
from core.errors import CoreError
from core.identity.types import AuthenticatedSubject

#: One stream per tenant, stable across reads.
#:
#: Stable, not per-read — the same reason `EVIDENCE_STREAM_PREFIX` gives: a fresh correlation ID
#: each time would make every record a chain of one, linked to nothing and removable without
#: trace, which defeats the reason a record of who read what exists at all.
RECORD_ACCESS_STREAM_PREFIX: Final[str] = "record-access"


def record_stream_for(tenant_id: str) -> str:
    return f"{RECORD_ACCESS_STREAM_PREFIX}:{tenant_id}"


class RecordAccessUnavailable(CoreError):
    """The access could not be recorded, so it does not happen.

    **A core error, not an `HTTPException`, and that is the point of it existing.**
    `evidence.py::_record_access` raises a FastAPI type from transport-independent code, and
    `surfaces/mcp/transport.py::_read_evidence` does not catch it — so an unrecordable evidence
    read answers 503 with a stated reason on the API and escapes as something else entirely on
    MCP. The failure path has no parity in the one operation whose docstring argues hardest for
    parity. This type is what both transports map to the same verdict, and what keeps 022 from
    copying that shape into seven new call sites.
    """


def record_access(
    *,
    audit: AuditSink,
    subject: AuthenticatedSubject,
    operation: str,
    target_correlation_id: str | None = None,
    target_id: str | None = None,
    result_count: int = 0,
) -> None:
    """Record that this subject was shown these records, or fail the operation.

    **Not best-effort.** `start_governed_run` already refuses when its own audit write fails,
    and the evidence path refuses a read it cannot record. An access that succeeded while its
    record did not is the state this whole feature exists to end, so there is no swallow here
    and no log-and-continue.

    ``result_count`` is a count and never a sample. Zero is meaningful: an empty listing still
    discloses that the caller asked, and a trail omitting fruitless reads cannot show probing.
    """
    _append(
        audit=audit,
        subject=subject,
        event_type=AuditEventType.RECORD_READ,
        operation=operation,
        target_correlation_id=target_correlation_id,
        target_id=target_id,
        disposition="permitted",
        result_count=result_count,
    )


def record_access_refused(
    *,
    audit: AuditSink,
    subject: AuthenticatedSubject,
    operation: str,
    reason_code: str,
    target_correlation_id: str | None = None,
    target_id: str | None = None,
) -> None:
    """Record that this subject was refused, and why — in the trail's terms, not the caller's.

    The caller sees one answer for `no_such_record` and `outside_tenant`; the trail keeps both,
    because a run of the second is someone probing and a trail that had collapsed them would
    show a user who mistypes a lot. A boundary probeable without trace is what this prevents.
    """
    _append(
        audit=audit,
        subject=subject,
        event_type=AuditEventType.RECORD_READ_REFUSED,
        operation=operation,
        target_correlation_id=target_correlation_id,
        target_id=target_id,
        disposition=reason_code,
        result_count=0,
    )


def _append(
    *,
    audit: AuditSink,
    subject: AuthenticatedSubject,
    event_type: AuditEventType,
    operation: str,
    target_correlation_id: str | None,
    target_id: str | None,
    disposition: str,
    result_count: int,
) -> None:
    payload: dict[str, Any] = {
        "subject_user_id": subject.subject_user_id,
        "operation": operation,
        # The correlation id of the thing read, so holding a run id is enough to find who read
        # it through the same governed query (ADR-0009). Null for a listing, which has no
        # single target — and null there rather than absent, so the field's meaning does not
        # depend on whether it appears.
        "target_correlation_id": target_correlation_id,
        "target_id": target_id,
        "disposition": disposition,
        # A count, never the rows. Recording those would copy what this record points at into
        # the record describing it, growing the trail in proportion to reads.
        "result_count": result_count,
    }
    try:
        audit.append_event(
            correlation_id=record_stream_for(subject.tenant_id),
            tenant_id=subject.tenant_id,
            event_type=event_type,
            payload=payload,
        )
    except Exception as exc:  # noqa: BLE001 — every failure to record fails the access
        raise RecordAccessUnavailable(
            "the access could not be recorded; the operation is refused"
        ) from exc


__all__ = [
    "RECORD_ACCESS_STREAM_PREFIX",
    "RecordAccessUnavailable",
    "record_access",
    "record_access_refused",
    "record_stream_for",
]
