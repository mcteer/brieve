# SPDX-License-Identifier: Apache-2.0
"""Recording that someone asked — and never what they asked or what they were told.

**Shape, never content** (FR-012). 022 established that a record of an access carries the shape of
it and never its content; the same holds here for a stronger reason: the corpus is somebody else's
copyrighted documentation, and copying it into an append-only trail that does not egress by default
would be both a leak and a licensing problem.
"""

from __future__ import annotations

from core.answering.streams import ask_stream_for
from core.audit.schema import AuditEventType
from core.audit.sink import AuditSink
from core.identity.types import AuthenticatedSubject


class AskNotRecorded(Exception):
    """The ask could not be recorded, so it does not happen.

    Same posture as 022's covered reads and `start_governed_run`: an act that succeeded while its
    record did not is the state those features exist to end.
    """


def record_ask(
    *,
    audit: AuditSink,
    subject: AuthenticatedSubject,
    corpus_digest: str,
    evidence_stream: str,
    model: str,
    disposition: str,
    source: str,
    cell: str,
    bound_cell: str,
    cell_disposition: str,
) -> None:
    """Write the ask record, or fail the ask.

    ``source`` is **required, with no default** (025). A default would mean every call site that
    forgot it silently claimed the corpus, and the field exists precisely because asking now
    happens in one place and the platform decides the door — which is unrecoverable from the rest
    of the payload. 022 made audit dispositions required for the same reason.

    ``cell``, ``bound_cell`` and ``cell_disposition`` are **required, no defaults** (026), for the
    same reason ``source`` is: a default would let every call site that forgot one silently claim
    an authorisation it never resolved. See `AuditEventType.ASK_ANSWERED`.

    ``corpus_digest`` and ``evidence_stream`` name **different things** and are never
    interchangeable: a corpus digest is content, a stream id is a location. One field holding
    either — which an earlier version of this record did — made a query over it return two kinds
    of value depending on ``source``. See `AuditEventType.ASK_ANSWERED`.
    """
    try:
        audit.append_event(
            correlation_id=ask_stream_for(subject.tenant_id),
            tenant_id=subject.tenant_id,
            event_type=AuditEventType.ASK_ANSWERED,
            payload={
                "subject_user_id": subject.subject_user_id,
                # WHICH corpus, not what it said.
                "corpus_digest": corpus_digest,
                "evidence_stream": evidence_stream,
                # WHICH model the binding named. A model verdict, never an approval — ADR-0039
                # and Principle IX, and `MODEL_GATE` already keeps that distinction for runs.
                "model": model,
                "disposition": disposition,
                # WHICH door was opened. Not derivable from anything else in the payload.
                "source": source,
                # WHETHER the model was allowed to answer, and under which authority (026).
                # `model` says which model answered; only these say whether it was permitted.
                "cell": cell,
                "bound_cell": bound_cell,
                "cell_disposition": cell_disposition,
            },
        )
    except Exception as exc:  # noqa: BLE001 — an unrecorded ask must not stand
        raise AskNotRecorded("the ask could not be recorded; it is refused") from exc


__all__ = ["AskNotRecorded", "record_ask"]
