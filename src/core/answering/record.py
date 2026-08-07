# SPDX-License-Identifier: Apache-2.0
"""Recording that someone asked — and never what they asked or what they were told.

**Shape, never content** (FR-012). 022 established that a record of an access carries the shape of
it and never its content; the same holds here for a stronger reason: the corpus is somebody else's
copyrighted documentation, and copying it into an append-only trail that does not egress by default
would be both a leak and a licensing problem.
"""

from __future__ import annotations

from typing import Any

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
    model_authority: str,
    conversation_id: str = "",
    carried_context: dict[str, Any] | None = None,
    declined_reason: str = "",
    #: How the relevance gate stood for THIS ask (044). Distinguishes an administrator's
    #: decision from a judge that could not be reached — the two send a reader to a person
    #: and to a vendor's status page respectively, and until this field the record could not
    #: tell them apart.
    relevance_gate: str = "",
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

    ``model_authority`` is **required, no default** (027) — the fourth field to be required for
    the same reason, and by now the pattern is the point: a default here would let a call site
    that never obtained a credential claim one silently, which is the exact inversion of what the
    field is for. Pass ``""`` deliberately when no credential was obtained; that is a statement,
    not an omission. It is a **reference, never a key value**.

    ``conversation_id`` and ``carried_context`` are **defaulted, unlike the four above** (035),
    and the asymmetry is deliberate. Those four describe authority, where a silent default would
    let a call site claim something it never obtained. These describe what the model was SHOWN,
    and a standalone ask genuinely has neither — so absence is the honest answer for the ask that
    belongs to no conversation, and only a conversational ask carries them.

    THREE STATES, AND AN AUDITOR MUST TELL THEM APART (FR-020–022). No keys at all: the ask
    belonged to no conversation. ``carried_context`` with an empty ``exchanges`` list: a
    conversation existed and nothing from it was carried. Seqs listed: exactly those exchanges
    were supplied. The seqs resolve against ``ask_exchanges``; the text is deliberately NOT
    duplicated here, because each carried exchange already has its own record and two copies of
    evidence are two things that can disagree.
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
                # WHY it declined, when it did (043). Defaulted, because an answer has no
                # reason to give — but a decline without one is a record an auditor cannot act
                # on: "the corpus does not cover what was asked", "every citation failed to
                # resolve" and "relevance could not be established" send a reader to three
                # different places, and until this field the response carried the distinction
                # and the RECORD did not.
                "declined_reason": declined_reason,
                # WHETHER the gate ran, and why not (044). `checked`, `disabled_by_admin`, or
                # empty where the feature does not apply. Not derivable from the disposition:
                # an answered ask looks identical whether its relevance was verified or the
                # check was switched off, and that is exactly the difference an auditor needs.
                "relevance_gate": relevance_gate,
                # WHICH door was opened. Not derivable from anything else in the payload.
                "source": source,
                # WHETHER the model was allowed to answer, and under which authority (026).
                # `model` says which model answered; only these say whether it was permitted.
                "cell": cell,
                "bound_cell": bound_cell,
                "cell_disposition": cell_disposition,
                # HOW the call was permitted: where the credential lives and which rotation
                # generation was in force. A reference — never the key, never a hash of it.
                "model_authority": model_authority,
                # WHAT THE MODEL WAS SHOWN beyond the question (035). Written only when the ask
                # belonged to a conversation, so their absence is itself the statement that it
                # did not.
                **({"conversation_id": conversation_id} if conversation_id else {}),
                **({"carried_context": carried_context} if carried_context is not None else {}),
            },
        )
    except Exception as exc:  # noqa: BLE001 — an unrecorded ask must not stand
        raise AskNotRecorded("the ask could not be recorded; it is refused") from exc


__all__ = ["ask_stream_for", "AskNotRecorded", "record_ask"]
