# SPDX-License-Identifier: Apache-2.0
"""The ask operation — an API operation rather than portal logic (ADR-0034).

**Transport-independent, so MCP reaches this rather than reimplementing it.** ADR-0033 asks for the
same verdict on every transport, and two implementations agreeing by inspection would make that a
measure of how carefully they were written.

**Holds no tool and no grant.** Never-acts is a property of what this path can reach, not of an
instruction given to a model — see `core.answering.answer`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict

from core.answering.answer import ANSWERED, ProviderUnavailable, answer_question
from core.answering.corpus import Corpus, CorpusUnavailable
from core.answering.estate import ANSWERED as ESTATE_ANSWERED
from core.answering.estate import EstateProviderUnavailable, answer_estate_question
from core.answering.record import record_ask
from core.answering.routing import Route, route, window_phrase
from core.answering.scope import visible_event_types
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


def ask_for(
    *,
    question: str,
    subject: AuthenticatedSubject,
    corpus: Corpus,
    provider: Any,
    audit: AuditSink,
    model: str,
    cell: str = "",
    bound_cell: str = "",
    cell_disposition: str = "",
    model_authority: str = "",
) -> dict[str, Any]:
    """Answer or decline, and record that someone asked.

    A provider failure and a corpus failure both **raise**. Neither arrives shaped like a decline,
    because a reader cannot tell "the corpus does not say" from "we could not reach the model", and
    those send them to different places.
    """
    answer = answer_question(question=question, corpus=corpus, provider=provider)

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
    )

    if answer.disposition != ANSWERED:
        return {
            "disposition": answer.disposition,
            "declined_reason": answer.declined_reason,
            "corpus_digest": answer.corpus_digest,
        }
    return {
        "disposition": answer.disposition,
        "corpus_digest": answer.corpus_digest,
        "claims": [
            {
                "statement": claim.statement,
                "citations": [c.url(corpus) for c in claim.citations],
            }
            for claim in answer.claims
        ],
    }


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
    entries, _disposition = read_evidence_for(
        query=query,
        audit=audit,
        subject=subject,
        start_time=start,
        end_time=end,
        event_types=visible,
    )

    answer = answer_estate_question(question=question, records=tuple(entries), provider=provider)

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
    )

    if answer.disposition != ESTATE_ANSWERED:
        return {
            "disposition": answer.disposition,
            "source": answer.source,
            "declined_reason": answer.declined_reason,
        }
    return {
        "disposition": answer.disposition,
        "source": answer.source,
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


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: No corpus and no model parameter. Which corpus is pinned and which model the binding names
    #: are not the caller's to choose — a parameter for either would be a request to widen scope.
    question: str


def build_router(
    *,
    providers: Any = None,
    model: str = "unconfigured",
    evidence_query: Any = None,
    ask_authority: Any = None,
    credential_source: Any = None,
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

        destination = route(body.question)

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
                return estate_answer_for(
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
                )
            except ScopeEmpty as empty:
                raise HTTPException(status.HTTP_403_FORBIDDEN, str(empty)) from empty
            except EstateProviderUnavailable as unreachable:
                raise HTTPException(
                    status.HTTP_503_SERVICE_UNAVAILABLE, str(unreachable)
                ) from unreachable

        if destination is Route.NEITHER:
            # Declined, not coerced. Both doors are named so the asker can rephrase toward one.
            record_ask(
                audit=audit,
                subject=subject,
                corpus_digest="",
                evidence_stream="",
                model=model,
                disposition="declined",
                source=str(Route.NEITHER),
                cell="",
                bound_cell="",
                # No source was consulted, so no cell question arose.
                cell_disposition="not_applicable",
                # No model was called, so no authority was exercised. Empty is the statement.
                model_authority="",
            )
            return {
                "disposition": "declined",
                "source": str(Route.NEITHER),
                "declined_reason": (
                    "this question matches neither the pinned guidance corpus nor your estate "
                    "records; those are the two sources available"
                ),
            }

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

        try:
            corpus = load_corpus()
        except CorpusUnavailable as unavailable:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, str(unavailable)
            ) from unavailable

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
            return ask_for(
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
