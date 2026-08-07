# SPDX-License-Identifier: Apache-2.0
"""The ask operation — an API operation rather than portal logic (ADR-0034).

**Transport-independent, so MCP reaches this rather than reimplementing it.** ADR-0033 asks for the
same verdict on every transport, and two implementations agreeing by inspection would make that a
measure of how carefully they were written.

**Holds no tool and no grant.** Never-acts is a property of what this path can reach, not of an
instruction given to a model — see `core.answering.answer`.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict

from core.answering.answer import (
    ANSWERED,
    RELEVANCE_DISABLED,
    ProviderUnavailable,
    answer_question,
)
from core.answering.context import MAX_CARRIED_EXCHANGES, build_context
from core.answering.conversations.postgres import ConversationStoreError
from core.answering.conversations.records import ExchangeDisposition
from core.answering.corpus import Corpus, CorpusUnavailable
from core.answering.endorsed.corpus import (
    CUSTOMER_ENDORSED,
    CombinedCorpus,
    EndorsedCorpus,
    provenance_of,
)
from core.answering.estate import ANSWERED as ESTATE_ANSWERED
from core.answering.estate import (
    EstateProviderUnavailable,
    answer_estate_question,
    describe_window,
)
from core.answering.focus import focus_types
from core.answering.ground import describe_ground
from core.answering.record import ask_stream_for, record_ask
from core.answering.routing import Route, route_with_signal, window_phrase
from core.answering.scope import visible_event_types
from core.audit.schema import AuditEventType
from core.audit.sink import AuditSink
from core.identity.types import AuthenticatedSubject
from surfaces.api.dependencies import AuditDep, SubjectDep
from surfaces.api.evidence import evidence_stream_for, read_evidence_for


class ScopeEmpty(Exception):
    """The subject's roles map to no visible record type.

    **A refusal, raised before any read.** FR-004c: empty means refuse, never a default scope —
    and refusing here rather than reading-then-finding-nothing is what keeps an unscoped subject
    from leaving an access record for a read they were never entitled to make.
    """


#: The source an ask consulted, for the record. 025 adds estate routing; until the
#: estate branch lands, every ask that reaches this module consulted the corpus.
GUIDANCE_SOURCE = str(Route.GUIDANCE)

#: How many records of **each** requested type an estate answer may rest on.
#:
#: Per type rather than per read, because the defect a shared bound cannot fix is competition:
#: measured on a real tenant, a question about runs received 60 run records in a window of 1,000
#: while `effect_observed` took 383 and `pre_decision` 302. Raising a shared number would not have
#: helped at any value.
#:
#: 200 is enough for a question about a day's activity to rest on something representative, and
#: small enough that a handful of types stays inside a model's context. When it truncates, the
#: answer says so (`describe_window`) rather than presenting a slice as the whole.
RECORDS_PER_TYPE = 200


def _record_relevance_gate(
    *,
    audit: AuditSink,
    subject: AuthenticatedSubject,
    answer: Any,
    model: str,
    cell: str,
) -> None:
    """`MODEL_GATE` for the relevance verdict — the event type's first production writer (043).

    **Counts and the cell, never statements.** The ask record already carries the surviving
    claims once; a second copy here would be a second place a reader must redact, and the gate's
    job is to say a model decided, not to restate what it decided about.
    """
    audit.append_event(
        correlation_id=ask_stream_for(subject.tenant_id),
        tenant_id=subject.tenant_id,
        event_type=AuditEventType.MODEL_GATE,
        payload={
            "subject_user_id": subject.subject_user_id,
            "gate": "relevance",
            # A MODEL judged, and the payload says so in the shape Principle IX asks for: a
            # gate, distinguishable from an approval a policy assigns to a person.
            "model": model,
            "cell": cell,
            "disposition": answer.disposition,
            "kept_count": len(answer.claims),
            "irrelevant_count": len(answer.irrelevant),
        },
    )


def ask_for(
    *,
    question: str,
    subject: AuthenticatedSubject,
    #: The pinned corpus, or a `CombinedCorpus` composing it with the customer's endorsed
    #: material (045). Widened rather than overloaded: both satisfy `resolves`/`url_for`/
    #: `digest`, which is the whole contract this path uses, and research R1's design is that
    #: there is a second implementation rather than a modified first one.
    corpus: Corpus | CombinedCorpus,
    provider: Any,
    audit: AuditSink,
    model: str,
    cell: str = "",
    bound_cell: str = "",
    cell_disposition: str = "",
    model_authority: str = "",
    now: datetime | None = None,
    context: str = "",
    conversation_id: str = "",
    carried_context: dict[str, Any] | None = None,
    relevance: Any = None,
    #: An administrator has switched the gate off (044). **Explicit rather than inferred from
    #: `relevance is None`**: absent-judge and disabled-gate both arrive as `None`, and the
    #: two must produce different answers — one is a governance gap the caller already refused
    #: on, the other is a decision a person made and the reader should be told about.
    relevance_disabled: bool = False,
) -> dict[str, Any]:
    """Answer or decline, and record that someone asked.

    A provider failure and a corpus failure both **raise**. Neither arrives shaped like a decline,
    because a reader cannot tell "the corpus does not say" from "we could not reach the model", and
    those send them to different places.

    `context` is earlier conversation and changes only what is ASKED (035). What ships is decided
    below exactly as before: every citation resolves against the pin or the claim is dropped.
    `carried_context` is what the RECORD will say about that history — written even when nothing
    was carried, because "a conversation existed and none of it was used" and "there was no
    conversation" are different facts and an auditor needs to tell them apart (FR-022).
    """
    answer = answer_question(
        question=question,
        corpus=corpus,
        provider=provider,
        context=context,
        # THE RELEVANCE GATE (043). Supplied here, always, by the route below — the parameter
        # is optional on `answer_question` only so the recorded eval scorers keep working
        # untouched, and a conformance row drives THIS function to prove the surface passes
        # one. A gate nothing calls is the defect 041 spent a feature closing.
        relevance=relevance,
    )

    # `MODEL_GATE`'s FIRST PRODUCTION WRITER. The event type has existed since the audit schema
    # named it and nothing had ever written one — Principle IX requires a model's verdict be
    # distinguishable in the trail from a human approval, and this is the first verdict the
    # platform has taken from a model in a governed path.
    #
    # BEFORE the ask record, on 031's ordering precedent: a reader meets the gate before the
    # outcome it produced, rather than discovering afterwards that something decided.
    #
    # Counts and the cell, never statements — the ask record already carries the surviving
    # claims once, and a second copy in the gate payload would be a second place to redact.
    if relevance is not None and answer.relevance_note:
        _record_relevance_gate(
            audit=audit,
            subject=subject,
            answer=answer,
            model=getattr(relevance, "model", "") or model,
            cell=cell,
        )

    # HOW OLD THE GROUND IS (033), composed HERE for the same reason the estate window note is:
    # `answer_question` has no clock and should not grow one, and a module that calls the clock
    # itself cannot be tested at the boundaries where this wording changes. `now` is injected —
    # the volume rows learned that lesson against a calendar date and a CI run at 00:07 UTC.
    #
    # Carried on the decline as well as the answer: a decline rests on the same corpus, and a
    # reader deciding whether to look elsewhere is exactly who needs the age.
    answer = replace(
        answer, ground_note=describe_ground(corpus.synced_at, now or datetime.now(UTC))
    )

    # THE DISCLOSURE (044, FR-011). Disclosed, never suppressed — 033's rule, and its reason:
    # a disclosure that appears only past some threshold trains readers that silence means
    # complete. So it rides EVERY answer given without its relevance checked, in the field a
    # reader already consults for gate information.
    if relevance_disabled:
        answer = replace(answer, relevance_note=RELEVANCE_DISABLED)

    # Recorded before the answer is returned. An answer delivered while its record failed is the
    # state 022 spent a feature removing.
    record_ask(
        audit=audit,
        subject=subject,
        corpus_digest=answer.corpus_digest,
        evidence_stream="",
        model=model,
        disposition=answer.disposition,
        source=GUIDANCE_SOURCE,
        cell=cell,
        bound_cell=bound_cell,
        cell_disposition=cell_disposition,
        model_authority=model_authority,
        conversation_id=conversation_id,
        carried_context=carried_context,
        declined_reason=answer.declined_reason,
        relevance_gate=(
            "disabled_by_admin" if relevance_disabled else ("checked" if relevance else "")
        ),
        # WHICH endorsed version, beside `corpus_digest` and never folded into it (045,
        # FR-017h). One request is one resolution, so this names exactly one identity — a
        # record listing two would be an ask whose ground moved underneath it.
        endorsed_version=getattr(corpus, "endorsed_version", "") or "",
    )

    # `source` on BOTH paths, which it was not until the third route went away.
    #
    # The estate path has always returned it; guidance never did, and nobody noticed because the
    # `neither` branch returned it too — so every response a caller could receive without reading
    # the corpus carried a source, and the one that did read it did not. With `neither` removed,
    # a caller asking a documentation question got back a body that would not say what answered
    # it. The record always knew (`record_ask` above); this makes the caller's copy agree.
    # `relevance_note` REACHES THE CALLER (044, FR-011), and until now it did not.
    #
    # 043 put the note on the `Answer` and rendered it nowhere: `evals-smoke` printed it and
    # the response never carried it. That was survivable while the note only said "a model
    # judged this" — it is not survivable now, because the note is how a person learns their
    # answer was given *without* its relevance checked. A disclosure that lives only in the
    # audit trail is one the reader of the answer never sees.
    #
    # On the decline as well as the answer, for the reason 033 gives about the ground note: a
    # decline rests on the same configuration, and a reader deciding whether to look elsewhere
    # is exactly who needs to know a check was switched off.
    if answer.disposition != ANSWERED:
        return {
            "disposition": answer.disposition,
            "source": GUIDANCE_SOURCE,
            "declined_reason": answer.declined_reason,
            "corpus_digest": answer.corpus_digest,
            "ground_note": answer.ground_note,
            "relevance_note": answer.relevance_note,
        }
    return {
        "disposition": answer.disposition,
        "source": GUIDANCE_SOURCE,
        "corpus_digest": answer.corpus_digest,
        # WHICH endorsed version the reader was shown, when one was in force. Alongside the
        # digest for the same reason both are on the record: an answer a person keeps should
        # name the ground it rested on well enough to look at it again.
        **(
            {"endorsed_version": getattr(corpus, "endorsed_version", "")}
            if getattr(corpus, "endorsed_version", "")
            else {}
        ),
        "ground_note": answer.ground_note,
        "relevance_note": answer.relevance_note,
        # WHAT THIS ANSWER RESTS ON, in one sentence (045, FR-016). Validated designs, the
        # organisation's own endorsed material, or both — because "the platform says so" and
        # "your own standard says so" are different claims and a reader acting on one should
        # not believe they are acting on the other.
        **({"grounding_note": _grounding_note(answer)} if _grounding_note(answer) else {}),
        "claims": [
            {
                "statement": claim.statement,
                "citations": [
                    # PROVENANCE AS DATA, per citation (clarify Q2, research R2). Derivable
                    # from the path and emitted explicitly anyway: deriving it in every
                    # consumer is a convention, and 038's payload table records what
                    # conventions become.
                    {"url": c.url(corpus), "provenance": provenance_of(c.path)}
                    for c in claim.citations
                ],
            }
            for claim in answer.claims
        ],
    }


def _grounding_note(answer: Any) -> str:
    """One sentence naming what an answer rests on.

    Composed from the citations rather than from configuration, so it describes what was
    actually cited. An answer that could have used endorsed material and did not must not
    claim it did — that would be a disclosure that misleads in the direction of authority.
    """
    kinds = {provenance_of(c.path) for claim in answer.claims for c in claim.citations}
    if not kinds:
        return ""
    if kinds == {CUSTOMER_ENDORSED}:
        return "This answer rests on your organisation's endorsed material."
    if CUSTOMER_ENDORSED in kinds:
        return (
            "This answer rests on both HashiCorp validated designs and your organisation's "
            "endorsed material; each citation says which."
        )
    return "This answer rests on HashiCorp validated designs."


def estate_answer_for(
    *,
    question: str,
    subject: AuthenticatedSubject,
    query: Any,
    audit: AuditSink,
    model: str,
    provider: Any,
    now: datetime | None = None,
    cell: str = "",
    bound_cell: str = "",
    cell_disposition: str = "",
    model_authority: str = "",
    context: str = "",
    conversation_id: str = "",
    carried_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Answer an estate question from the asker's own records, or decline.

    **The order is the security argument.** Scope is computed, an empty scope refuses *before any
    read happens* — so a subject with no mapped roles leaves no access record, because no access
    was attempted — and only then is the governed read performed, narrowed to what that subject
    may see. Narrowing the request rather than filtering its results is what keeps out-of-scope
    entries from ever being read at all.

    ``now`` is injected rather than read here (analysis U4): a window phrase resolves against it,
    and ambient time inside an answering path is how an eval lane stops being reproducible.
    """
    visible = visible_event_types(subject.roles)
    if not visible:
        # No read attempted, so no access record — and the ask itself still records, because a
        # boundary a caller can probe without trace is what 022 removed.
        record_ask(
            audit=audit,
            subject=subject,
            corpus_digest="",
            evidence_stream=evidence_stream_for(subject.tenant_id),
            model=model,
            disposition="scope_empty",
            source=str(Route.ESTATE),
            # Resolution SUCCEEDED; the ask failed on scope afterwards. Keeping the resolution
            # outcome is what preserves the fact that governance passed.
            cell=cell,
            bound_cell=bound_cell,
            cell_disposition=cell_disposition,
            # A credential may have been obtained before scope refused; carrying it keeps the
            # record honest about what authority was in hand when the ask stopped.
            model_authority=model_authority,
        )
        raise ScopeEmpty(
            "no records are visible to this subject's roles; an estate answer would have "
            "nothing it may rest on"
        )

    start, end = _window(question, now)
    # FOCUS ∩ VISIBLE, and the intersection is the whole safety argument (029).
    #
    # `visible` decides what this subject may see at all; `focus` decides what the question is
    # about. Intersecting means a question can only ever narrow an already-scoped read — a focus
    # that could add a type would be a scope defect wearing a relevance feature's clothes.
    #
    # An empty intersection falls back to `visible` rather than refusing: "your role cannot see
    # the thing you asked about" must read as an ordinary empty estate, not as a scope refusal,
    # while the visibility question stays open (029 FR-009).
    focus = focus_types(question)
    narrowed = (focus & visible) or visible if focus is not None else visible
    entries, _disposition = read_evidence_for(
        query=query,
        audit=audit,
        subject=subject,
        start_time=start,
        end_time=end,
        event_types=narrowed,
        # PER TYPE, because one bound over undifferentiated types is a competition the estate's
        # noisiest activity always wins: measured at 60 run records in a window of 1,000.
        limit_per_type=RECORDS_PER_TYPE,
    )

    answer = answer_estate_question(
        context=context,
        question=question,
        records=tuple(entries),
        provider=provider,
        window_note=describe_window(getattr(entries, "window", {})),
    )

    # Recorded before the answer is returned, pointing at the access STREAM (stable per tenant,
    # 022) rather than a single record — one hop, and the read is locatable within it by subject
    # and time. See `AuditEventType.ASK_ANSWERED`.
    record_ask(
        audit=audit,
        subject=subject,
        corpus_digest="",
        evidence_stream=evidence_stream_for(subject.tenant_id),
        model=model,
        disposition=answer.disposition,
        source=answer.source,
        cell=cell,
        bound_cell=bound_cell,
        cell_disposition=cell_disposition,
        model_authority=model_authority,
        conversation_id=conversation_id,
        carried_context=carried_context,
    )

    if answer.disposition != ESTATE_ANSWERED:
        return {
            "disposition": answer.disposition,
            "source": answer.source,
            "declined_reason": answer.declined_reason,
            "window_note": answer.window_note,
        }
    return {
        "disposition": answer.disposition,
        "source": answer.source,
        "window_note": answer.window_note,
        "claims": [
            {
                "statement": claim.statement,
                "references": [ref.entry_hash for ref in claim.references],
            }
            for claim in answer.claims
        ],
    }


def _window(question: str, now: datetime | None) -> tuple[datetime | None, datetime | None]:
    """Resolve a recognised temporal phrase against the injected clock.

    An unrecognised phrase — or none — yields no bounds, and the read's own ``limit`` is the bound
    instead. **No general time parsing**: a window guessed wrong returns records from the wrong
    period while looking entirely correct.
    """
    phrase = window_phrase(question)
    if phrase is None or now is None:
        return None, None
    day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    match phrase:
        case "today":
            return day, now
        case "yesterday":
            return day - timedelta(days=1), day
        case "last night" | "overnight":
            return day - timedelta(hours=8), day + timedelta(hours=6)
        case "this week":
            return day - timedelta(days=day.weekday()), now
        case "last week":
            monday = day - timedelta(days=day.weekday())
            return monday - timedelta(days=7), monday
        case _:  # pragma: no cover - window_phrase only returns the above
            return None, None


#: What a resolution refusal is called on the ask record. The reason vocabulary is the
#: platform's; this maps it to the three the trail and the caller see (data-model.md).
_GOVERNANCE_DISPOSITION: dict[str, str] = {
    "unbound_ask_source": "unbound",
    "fabric_unreachable": "matrix_unreadable",
    "fabric_timeout": "matrix_unreadable",
}


class AskCredentialUnavailable(Exception):
    """The cell is qualified and the platform holds no authority to call the vendor (027).

    **Recorded before it is raised**, like every other ask refusal: someone asked, and a boundary
    a caller can probe without trace is what 022 removed.

    Deliberately its own type rather than a `provider_unavailable`. Those two send an operator to
    different people — one to whoever governs the credential, one to the vendor or the network —
    and the whole design of the refusal ladder is that a person reading the trail knows which door
    to knock on without guessing.
    """

    disposition = "credential_unavailable"


def _remember(
    *,
    conversations: Any,
    conversation_id: str | None,
    subject: AuthenticatedSubject,
    question: str,
    source: str,
    body: dict[str, Any],
    context: Any,
) -> dict[str, Any]:
    """Persist the exchange and hand back the body the caller sees (035).

    **The transcript only ever holds asks the platform actually answered, declined or
    refused.** A provider fault raises above this and never reaches here, so a conversation
    cannot accumulate an exchange nobody got an answer to — reopening one would then show a
    question with nothing under it and no way to tell why.

    The stored `outcome` is this body verbatim. Reopening re-renders what the person SAW,
    rather than re-deriving it against a corpus that may since have been re-pinned.
    """
    if conversations is None:
        return body

    stated = str(body.get("disposition") or "")
    disposition = ExchangeDisposition(stated if stated in _EXCHANGE_DISPOSITIONS else "answered")

    if conversation_id:
        exchange = conversations.append(
            conversation_id=conversation_id,
            tenant_id=subject.tenant_id,
            subject_user_id=subject.subject_user_id,
            question=question,
            source=source,
            disposition=disposition,
            outcome=body,
        )
        # Resolution succeeded before the model was called; a `None` here means the
        # conversation went away underneath the ask. The answer still stands and is returned —
        # it was produced and recorded — but it belongs to no transcript.
        if exchange is None:
            return body
        seq, resolved_id = exchange.seq, conversation_id
    else:
        conversation, exchange = conversations.start(
            conversation_id=str(uuid4()),
            tenant_id=subject.tenant_id,
            subject_user_id=subject.subject_user_id,
            question=question,
            source=source,
            disposition=disposition,
            outcome=body,
        )
        seq, resolved_id = exchange.seq, conversation.conversation_id

    enriched = dict(body)
    enriched["conversation_id"] = resolved_id
    enriched["exchange_seq"] = seq
    # Present only when the conversation outgrew the bound — an unconditional caveat gets
    # skipped, which costs exactly the case it exists for (the window note's own lesson).
    if context.note:
        enriched["context_note"] = context.note
    return enriched


#: The dispositions an exchange can hold. Anything else the surface produces is not a
#: transcript entry — it raised before reaching the store.
_EXCHANGE_DISPOSITIONS = frozenset({"answered", "declined", "refused"})


class ConversationNotFound(Exception):
    """The conversation is not this subject's — or does not exist. One answer for both."""


def _resolve_conversation(
    *, conversations: Any, conversation_id: str | None, subject: AuthenticatedSubject
) -> tuple[Any, ...]:
    """The exchanges this ask may build on, or a refusal — and never a hint (FR-012/013).

    Returns `()` for a new conversation. Raises `ConversationNotFound` for an id that is
    absent, another subject's, or another tenant's, all with one wording, because a distinct
    response for "exists but not yours" confirms that it exists.

    **Reached before routing, governance, the corpus and any vendor call.** A caller probing
    identifiers must not be able to spend a model call or leave a governance record doing it.
    """
    if not conversation_id:
        return ()
    if conversations is None:
        # A surface with no store cannot honour a conversation, and pretending the id was
        # simply unknown would be the same lie in a friendlier tone.
        raise ConversationNotFound("no such conversation")
    found = conversations.get(
        conversation_id=conversation_id,
        tenant_id=subject.tenant_id,
        subject_user_id=subject.subject_user_id,
    )
    if found is None:
        raise ConversationNotFound("no such conversation")
    _, exchanges = found
    return tuple(exchanges[-MAX_CARRIED_EXCHANGES:])


def obtain_ask_credential(
    *,
    credential_source: Any,
    model: str,
    subject: AuthenticatedSubject,
    audit: AuditSink,
    source: str,
    cell: str,
    bound_cell: str,
    cell_disposition: str,
    corpus_digest: str = "",
    evidence_stream: str = "",
) -> Any:
    """Broker the credential for **this ask**, or record a refusal and raise.

    Called **after** `authorise_ask` and **before** any provider is built: governance decides
    whether a model may answer, and only then does the platform go looking for the authority to
    call one. The reverse order would send an operator to write a credential for a cell they are
    not permitted to use.

    **The vendor is derived from the bound model**, not configured separately — ``anthropic`` from
    ``anthropic/claude-opus@5``. So the matrix decides which vendor's credential is needed, and a
    deployment cannot end up holding authority for a vendor no cell qualifies.

    **There is no environment fallback and no default source.** `None` refuses. A path that fell
    back to `EVAL_PROVIDER_API_KEY` would work on the operator's laptop, fail in the enclave, and
    pass every row except the one written to catch it (T014).
    """
    from core.authority.errors import ResolutionRefused

    vendor = model.split("/", 1)[0].strip()
    detail = ""
    if credential_source is None:
        detail = (
            "no model credential source is configured for this surface; a qualified cell is not "
            "authority to call a vendor"
        )
    else:
        try:
            return credential_source.obtain(vendor)
        except ResolutionRefused as refused:
            # `fabric_unreachable` arrives here too, and it is deliberately NOT flattened into
            # the caller-facing disposition: the trail keeps `credential_unavailable` as the ask's
            # outcome while the detail names the store fault, because a caller learning that the
            # trust store is down learns something about the platform's internals that a refusal
            # should not teach.
            detail = str(refused)

    record_ask(
        audit=audit,
        subject=subject,
        corpus_digest=corpus_digest,
        evidence_stream=evidence_stream,
        model=model,
        disposition=AskCredentialUnavailable.disposition,
        source=source,
        # Resolution SUCCEEDED; the ask failed on the credential afterwards. Keeping the
        # resolution outcome is what preserves the fact that governance passed.
        cell=cell,
        bound_cell=bound_cell,
        cell_disposition=cell_disposition,
        # No credential was obtained, so none was exercised. Empty is the statement.
        model_authority="",
    )
    raise AskCredentialUnavailable(detail)


class AskNotQualified(Exception):
    """Governance refused this ask before any provider was contacted.

    Carries the disposition the record and the caller both see. `unqualified_cell` deliberately
    does not distinguish absent / withdrawn / wrong-role **to the caller** — the resolver collapses
    them too, so no caller can learn which it was; the trail's `bound_cell` and the matrix record
    answer that for an investigator.
    """

    def __init__(self, disposition: str, detail: str) -> None:
        super().__init__(detail)
        self.disposition = disposition


def _available(model: str, providers: Any) -> frozenset[str]:  # noqa: D417
    """Exactly the model this surface can build a provider for — never wider.

    **Analysis U2's requirement, and the reason is record/actual agreement.** A wider set lets
    fallback select a cell for a model this provider cannot call: the ask record would then name
    cell X while the provider called model Y, and the trail would carry an authorisation for a
    model that never ran. On an attestation-relevant record that is the worst available outcome.

    ``providers`` is a **factory** as of 027 rather than a built provider, because a provider is
    now built per ask from material brokered for that ask. What this function asks of it is
    unchanged: whether this surface can call the bound model at all.
    """
    return frozenset() if providers is None else frozenset({model})


def authorise_ask(
    *,
    source: str,
    subject: AuthenticatedSubject,
    audit: AuditSink,
    authority: Any,
    available: frozenset[str],
) -> tuple[str, str, str]:
    """Resolve the cell this ask may use, or refuse — **before any provider is contacted**.

    Returns `(cell, bound_cell, cell_disposition)` for the record. Raises `AskNotQualified` on a
    governance refusal, having recorded it: someone asked, and a boundary a caller can probe
    without trace is what 022 removed.

    **Called first, always** — governance precedes scope and precedes provider availability. An
    unbound surface refuses `unbound` even with no provider configured, because "nobody decided
    which model may answer" is the answer an operator needs before "nothing is wired". The reverse
    order would have told them to go configure a provider they are not yet permitted to use.
    """
    from core.authority.errors import ResolutionRefused

    if authority is None:
        disposition = "unbound"
        detail = (
            "no ask binding is configured for this surface; a configured provider is not a "
            "qualification"
        )
    else:
        try:
            cell, fallback = authority.resolve(source, available=available)
        except ResolutionRefused as refused:
            disposition = _GOVERNANCE_DISPOSITION.get(refused.reason_code, "unqualified_cell")
            detail = str(refused)
        else:
            bound = fallback.pinned_cell if fallback is not None else cell.reference
            return (
                cell.reference,
                bound,
                f"fallback:{fallback.reason}" if fallback is not None else "pinned",
            )

    record_ask(
        audit=audit,
        subject=subject,
        corpus_digest="",
        evidence_stream="",
        model="unresolved",
        disposition=disposition,
        source=source,
        cell="",
        bound_cell="",
        cell_disposition=f"refused:{disposition}",
        # Governance refused BEFORE any credential was sought. Empty here is load-bearing: a
        # reference would claim an authority the platform never exercised.
        model_authority="",
    )
    raise AskNotQualified(disposition, detail)


#: Reason codes this path may name in the record as-is. Anything outside it becomes
#: `relevance_unqualified`, because a disposition an auditor cannot look up is worse than a
#: coarse one — but every code the resolver actually raises belongs here.
RELEVANCE_DISPOSITIONS: frozenset[str] = frozenset(
    {"relevance_unbound", "relevance_unqualified", "self_judged_relevance"}
)


def relevance_enabled_for(authority: Any) -> bool:
    """Whether an administrator has left the relevance gate on (044, FR-010).

    **Absent means enabled, and an unreadable record means enabled too.** The binding parser
    already defaults the field that way for compatibility; this adds the second half — a
    fabric that cannot be read must not silently switch the gate off. Failing *open* would be
    wrong for a credential and is right for a check: a check that stops running because a
    read failed is a check nobody knows stopped.

    An unreadable fabric still refuses later, at `relevance_judge_for`, where the refusal
    names the fabric rather than pretending an administrator decided something.
    """
    if authority is None:
        return True

    from core.authority.ask_binding import parse_ask_binding_record

    # **The reader is resolved OUTSIDE the try**, and that placement is a finding rather than
    # a style choice. The first version called `authority.read_binding()` — a private
    # attribute, not a method — inside a `try/except Exception: return True`. The
    # `AttributeError` was swallowed by the fail-open branch, so the toggle silently did
    # nothing and every row about it failed pointing at the wrong thing.
    #
    # A fail-open default is right for this check and dangerous around a wiring error: it
    # turns "the code is wrong" into "the estate must have it enabled". So only the READ is
    # guarded.
    reader = authority.read_binding_record
    try:
        record = reader()
    except Exception:  # noqa: BLE001 — unreadable is not "disabled by somebody"
        return True
    try:
        return parse_ask_binding_record(record).relevance_enabled
    except Exception:  # noqa: BLE001 — a malformed record refuses later, at resolution
        return True


def relevance_judge_for(
    *,
    subject: AuthenticatedSubject,
    audit: AuditSink,
    authority: Any,
    judges: Any,
    available: frozenset[str],
) -> Any:
    """The relevance judge this surface may use, or refuse (043, FR-017).

    **Same ordering as `authorise_ask`, and for the same reason.** Governance precedes
    availability: `relevance_unbound` means nobody decided which model may judge relevance, and
    an operator needs that before "the judge could not be reached". The reverse order sends
    them to a vendor's status page during a governance gap.

    **Refusing is not optional.** An ask that cannot establish relevance must not proceed as
    though the gate passed — so this raises, and the route turns it into a refusal the record
    names. A `None` judge would be a silently absent gate, which is the shape 041 spent a
    feature closing one layer over.
    """
    from core.authority.errors import ResolutionRefused

    if authority is None or judges is None:
        raise AskNotQualified(
            "relevance_unbound",
            "no relevance judge is configured for this surface; an answer whose relevance "
            "nobody can establish is not an answer this platform will give",
        )

    try:
        cell, _fallback = authority.resolve_relevance(available=available)
    except ResolutionRefused as refused:
        # The reason code carried through, not bucketed. An earlier version collapsed
        # everything that was not `relevance_unbound` into `relevance_unqualified`, which
        # swallowed ADR-0067's `self_judged_relevance` the day it was added: the operator
        # would have been sent to re-run the eval lane for a cell that is already qualified,
        # watched it pass, and been no closer. The whole value of a distinct code is that it
        # survives to the record.
        disposition = (
            refused.reason_code
            if refused.reason_code in RELEVANCE_DISPOSITIONS
            else "relevance_unqualified"
        )
        record_ask(
            audit=audit,
            subject=subject,
            corpus_digest="",
            evidence_stream="",
            model="unresolved",
            disposition=disposition,
            source=GUIDANCE_SOURCE,
            cell="",
            bound_cell="",
            cell_disposition=f"refused:{disposition}",
            model_authority="",
            declined_reason=str(refused),
        )
        raise AskNotQualified(disposition, str(refused)) from refused

    return judges(cell.reference)


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: No corpus and no model parameter. Which corpus is pinned and which model the binding names
    #: are not the caller's to choose — a parameter for either would be a request to widen scope.
    question: str

    #: Which conversation this question belongs to (035). Absent starts one; present appends to
    #: it, and an id that is not this subject's own is a 404 before anything else happens.
    #:
    #: **Still not a widening.** A conversation groups a person's own questions and gives a
    #: follow-up its subject; it grants no source, no model, and no scope the same question asked
    #: standalone would not have.
    conversation_id: str | None = None


def build_router(
    *,
    providers: Any = None,
    model: str = "unconfigured",
    evidence_query: Any = None,
    conversations: Any = None,
    ask_authority: Any = None,
    credential_source: Any = None,
    relevance_judges: Any = None,
    #: Which model this surface can build a relevance JUDGE for (043). Separate from
    #: `ask_model` and narrow for the same reason `_available` is: a wider set would let
    #: fallback pick a judge cell this surface cannot call, and the record would name a
    #: judgement that never happened.
    relevance_model: str = "unconfigured",
    #: 045's second corpus, as a zero-argument reader returning an `EndorsedCorpus`.
    #:
    #: `None` means this deployment has no customer material, which is what every deployment
    #: has until an administrator endorses something — and the answering path is then exactly
    #: what it was before, which is US6 holding at the assembly layer as well as in the code.
    endorsed_reader: Any = None,
) -> APIRouter:
    """The provider is a **parameter**, so a deployment can supply one and a test can share one.

    An earlier draft read it off the router with `getattr`, which meant nothing could ever set it:
    the operation was permanently 503 in every assembly, and the parity rows could only compare two
    surfaces failing. A collaborator that cannot be injected is a collaborator the surfaces cannot
    be shown to share — the exact asymmetry `surface_under_test` exists to prevent.

    **`providers` is a factory as of 027, not a built provider**: `(source, secret) -> provider`,
    called once per ask with material brokered for that ask. A surface holding a built provider
    would hold whatever credential built it for the life of the process, which is the standing
    credential this feature exists to remove — one layer above the reader that refuses to cache.

    **`credential_source` defaults to `None`, and `None` refuses.** A default that supplied one
    would rebuild "configured means permitted" one level below where 026 broke it.
    """
    router = APIRouter(tags=["ask"])

    @router.post("/ask")
    def ask(body: AskRequest, subject: SubjectDep, audit: AuditDep) -> dict[str, Any]:
        """Answer from whichever source the question needs, or decline. Never act.

        **One place to ask** (FR-010): the platform decides what the question needs rather than
        making the caller declare it. Routing is deterministic and recorded, and a decline names
        the door that was opened so nobody who asked about their estate is told the documentation
        does not cover it.

        **The provider is resolved per deployment and may be absent.** A surface with no model
        configured fails here rather than answering from the corpus alone — FR-011a forbids a
        model-less path, because a second path no gate scores is how this feature's own gates
        reached the state it was written to fix.
        """
        from core.answering.corpus import load_corpus

        # THE CONVERSATION, RESOLVED BEFORE ANYTHING ELSE HAPPENS (035).
        #
        # Before routing, before governance, before the corpus is loaded and long before a
        # vendor is called: an id that is not this subject's own must cost nothing and reveal
        # nothing. `resolve_conversation` returns the exchanges this ask may see — empty for a
        # new conversation — and raises 404 for absent, somebody else's, and another tenant's
        # alike, because a different answer for "exists but not yours" says it exists.
        try:
            prior = _resolve_conversation(
                conversations=conversations,
                conversation_id=body.conversation_id,
                subject=subject,
            )
        except ConversationNotFound as missing:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "no_such_conversation") from missing
        except ConversationStoreError as unavailable:
            # NOT a 404, and not a context-free answer either. "Could not look" and "not yours"
            # send a person to different places — one waits, the other goes and asks who owns
            # it. And answering the follow-up as though it had no history would hand them an
            # answer read in isolation with nothing saying so, which is the quietest wrong
            # answer this feature could produce.
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "this conversation could not be read just now, so the question was not asked. "
                "Nothing is lost — try again in a moment.",
            ) from unavailable

        # EXPLICIT SIGNAL WINS; SILENCE INHERITS (FR-017/017a).
        #
        # `route_with_signal` reports the fact `route` discards: whether the question said
        # anything the router recognises. A question that did is routed on its own words and
        # the conversation cannot move it — that half is what keeps "which runs failed?" a
        # records question wherever it is asked. A question that did not — "what about
        # multi-region?" — inherits the source of the exchange it follows, because a bare
        # follow-up has no words to route on and the guidance floor would answer a records
        # conversation from the documentation.
        destination, had_signal = route_with_signal(body.question)
        inherited = False
        if not had_signal and prior:
            destination = Route(prior[-1].source)
            inherited = True

        context = build_context(prior, inherited_route=inherited)

        if destination is Route.ESTATE:
            # GOVERNANCE FIRST — before scope, before provider availability, before the evidence
            # plane is even looked at. An unqualified model must be unreachable, not merely unused.
            try:
                cell, bound_cell, cell_disposition = authorise_ask(
                    source=str(Route.ESTATE),
                    subject=subject,
                    audit=audit,
                    authority=ask_authority,
                    available=_available(model, providers),
                )
            except AskNotQualified as refused:
                raise HTTPException(status.HTTP_403_FORBIDDEN, str(refused)) from refused

            if evidence_query is None:
                raise HTTPException(
                    status.HTTP_503_SERVICE_UNAVAILABLE,
                    "no evidence plane is configured; estate questions cannot be answered",
                )
            if providers is None:
                raise HTTPException(
                    status.HTTP_503_SERVICE_UNAVAILABLE,
                    "no model is configured for `ask`; the records alone are not an answer",
                )
            # THE CREDENTIAL, between governance and the vendor (027). Before the evidence plane
            # is read, so an ask the platform cannot complete does not leave an access record for
            # a read that answered nobody.
            try:
                credential = obtain_ask_credential(
                    credential_source=credential_source,
                    model=model,
                    subject=subject,
                    audit=audit,
                    source=str(Route.ESTATE),
                    cell=cell,
                    bound_cell=bound_cell,
                    cell_disposition=cell_disposition,
                    evidence_stream=evidence_stream_for(subject.tenant_id),
                )
            except AskCredentialUnavailable as unavailable:
                raise HTTPException(
                    status.HTTP_503_SERVICE_UNAVAILABLE, str(unavailable)
                ) from unavailable
            try:
                answered = estate_answer_for(
                    question=body.question,
                    subject=subject,
                    query=evidence_query,
                    audit=audit,
                    model=model,
                    provider=providers(str(Route.ESTATE), credential.secret),
                    now=datetime.now(UTC),
                    cell=cell,
                    bound_cell=bound_cell,
                    cell_disposition=cell_disposition,
                    model_authority=credential.reference,
                    context=context.text,
                    conversation_id=body.conversation_id or "",
                    carried_context=context.descriptor if body.conversation_id else None,
                )
                return _remember(
                    conversations=conversations,
                    conversation_id=body.conversation_id,
                    subject=subject,
                    question=body.question,
                    source=str(Route.ESTATE),
                    body=answered,
                    context=context,
                )
            except ScopeEmpty as empty:
                raise HTTPException(status.HTTP_403_FORBIDDEN, str(empty)) from empty
            except EstateProviderUnavailable as unreachable:
                raise HTTPException(
                    status.HTTP_503_SERVICE_UNAVAILABLE, str(unreachable)
                ) from unreachable

        # NO THIRD BRANCH ANY MORE. A question that is not estate-shaped falls through to
        # guidance, which consults the corpus and declines for itself when it cannot help.
        # The branch that used to sit here declined WITHOUT consulting anything, on the
        # strength of a keyword list — and told the asker "this matches neither source", which
        # was a claim about coverage that nothing had checked.

        # GOVERNANCE FIRST here too — the corpus is not even loaded for an ask nobody permitted.
        try:
            cell, bound_cell, cell_disposition = authorise_ask(
                source=GUIDANCE_SOURCE,
                subject=subject,
                audit=audit,
                authority=ask_authority,
                available=_available(model, providers),
            )
        except AskNotQualified as refused:
            raise HTTPException(status.HTTP_403_FORBIDDEN, str(refused)) from refused

        # THE ADMINISTRATOR'S SWITCH (044), read before the gate's governance.
        #
        # **Ordering matters, and this is the honest one.** A disabled gate needs no bound
        # cell and no reachable judge, so resolving governance first would refuse
        # `relevance_unbound` for an estate that deliberately turned the check off — telling
        # an operator to decide something they have already decided.
        #
        # The toggle rides the ask-binding record the surface already reads per ask, so a
        # change is in force for the NEXT question with no restart and no extra fabric read.
        gate_enabled = relevance_enabled_for(ask_authority)

        # THE RELEVANCE GATE'S OWN GOVERNANCE (043), resolved beside the answering cell and
        # before the corpus is loaded — one qualification does not license the other, and an
        # ask nobody permitted to be checked is an ask this surface does not answer.
        relevance = None
        if gate_enabled:
            try:
                relevance = relevance_judge_for(
                    subject=subject,
                    audit=audit,
                    authority=ask_authority,
                    judges=relevance_judges,
                    available=_available(relevance_model, relevance_judges),
                )
            except AskNotQualified as refused:
                raise HTTPException(status.HTTP_403_FORBIDDEN, str(refused)) from refused

        try:
            pinned = load_corpus()
        except CorpusUnavailable as unavailable:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, str(unavailable)
            ) from unavailable

        # **RESOLVED ONCE, HERE** (045, FR-017f). One question is one resolution, so there is
        # no window in which an adoption could move the ground under a single answer — the ask
        # path gets run isolation for free, and only the dispatched path needs a pin.
        #
        # A reader that fails resolves nothing rather than raising: customer material becoming
        # temporarily uncitable narrows the answer and is disclosed, whereas taking the whole
        # ask down would let a customer's own repository outage stop the platform answering
        # from the corpus it ships with.
        endorsed = EndorsedCorpus()
        if endorsed_reader is not None:
            try:
                endorsed = endorsed_reader()
            except Exception:  # noqa: BLE001 — see the note above
                endorsed = EndorsedCorpus()

        # **WITH NOTHING ENDORSED, THE PINNED CORPUS IS PASSED UNCHANGED**, and that is US6
        # holding at the assembly layer rather than only in the code. It is also what the tree
        # asked for: composing unconditionally broke ten answering rows whose provider doubles
        # distinguish guidance from estate by `isinstance(material, Corpus)`. They were right
        # to notice. An estate that has endorsed nothing should be byte-for-byte the platform
        # it was before this feature, not a platform running a new code path that happens to
        # be empty.
        corpus: Corpus | CombinedCorpus = pinned
        if not endorsed.empty:
            corpus = CombinedCorpus(pinned=pinned, endorsed=endorsed)

        if providers is None:
            # RECORDED ANYWAY. Someone asked; the platform could not attempt it. 022 established
            # that a refusal records — a boundary a caller can probe without trace is the thing
            # that prevents — and repeated asks against a surface with no model is exactly the
            # shape a trail should show rather than swallow.
            record_ask(
                audit=audit,
                subject=subject,
                corpus_digest=corpus.digest,
                evidence_stream="",
                model="unconfigured",
                disposition="provider_unavailable",
                source=GUIDANCE_SOURCE,
                # Resolution SUCCEEDED; the ask failed later. Overwriting the resolution outcome
                # here would erase the fact that governance passed.
                cell=cell,
                bound_cell=bound_cell,
                cell_disposition=cell_disposition,
                # No provider, so no vendor call, so no credential was exercised.
                model_authority="",
            )
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "no model is configured for `ask`; the corpus alone is not an answer",
            )
        try:
            credential = obtain_ask_credential(
                credential_source=credential_source,
                model=model,
                subject=subject,
                audit=audit,
                source=GUIDANCE_SOURCE,
                cell=cell,
                bound_cell=bound_cell,
                cell_disposition=cell_disposition,
                corpus_digest=corpus.digest,
            )
        except AskCredentialUnavailable as unavailable:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, str(unavailable)
            ) from unavailable

        try:
            answered = ask_for(
                relevance_disabled=not gate_enabled,
                question=body.question,
                subject=subject,
                corpus=corpus,
                provider=providers(GUIDANCE_SOURCE, credential.secret),
                audit=audit,
                model=model,
                cell=cell,
                bound_cell=bound_cell,
                cell_disposition=cell_disposition,
                model_authority=credential.reference,
                context=context.text,
                conversation_id=body.conversation_id or "",
                carried_context=context.descriptor if body.conversation_id else None,
                relevance=relevance,
            )
            return _remember(
                conversations=conversations,
                conversation_id=body.conversation_id,
                subject=subject,
                question=body.question,
                source=GUIDANCE_SOURCE,
                body=answered,
                context=context,
            )
        except ProviderUnavailable as unreachable:
            # NOT a decline. A reader cannot tell "the corpus does not say" from "we could not
            # reach the model", and those send them to different people.
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, str(unreachable)
            ) from unreachable

    return router


__all__ = [
    "AskCredentialUnavailable",
    "AskRequest",
    "CorpusUnavailable",
    "ProviderUnavailable",
    "ask_for",
    "build_router",
    "obtain_ask_credential",
]
