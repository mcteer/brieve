# SPDX-License-Identifier: Apache-2.0
"""The MCP transport — a client of 008's core, as the calling user.

**As the calling user, never as itself** (FR-002a). MCP is a transport, not a principal: an
agent acting on someone's behalf. A service account here would collapse every caller into
one subject and destroy the non-repudiation the whole delegation chain exists for — and it
would do so invisibly, because everything would still work.

**One core, two front doors.** Each operation resolves the same collaborators the API
resolves and calls into the same place. Two implementations that agree by inspection would
make ADR-0033's parity guarantee a measure of how carefully they were written, which is
precisely what a conformance row cannot check.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.audit.query import EvidenceQuery
from core.audit.sink import AuditSink
from core.identity.types import AuthenticatedSubject
from core.runs.changes import ChangeRequestStore, InMemoryChangeRequestStore
from core.runs.index import InMemoryRunIndex, RunIndex
from core.runs.refusals import OperationRefused
from core.threads.store import DEFAULT_PAGE_SIZE, InMemoryThreadStore, ThreadStore

# Module level, unlike the other `surfaces.api` imports in this file, which are deferred to
# break an import cycle. `record_access` imports nothing from `surfaces`, so it cannot
# participate in one — and six handlers catch this error, which is exactly the situation where
# a repeated function-local import stops being a deferral and becomes noise.
from surfaces.api.record_access import RecordAccessUnavailable
from surfaces.dispatch.types import RunDispatcher, RunHandle
from surfaces.mcp.operations import operations


@dataclass
class McpResult:
    """What an MCP call returns, before framing.

    Mirrors the API's dispositions rather than inventing its own vocabulary — parity
    compares verdicts, and a transport with a different set of outcomes could not be
    compared at all.
    """

    ok: bool
    #: The status the API would have returned. Carried so parity compares verdicts rather
    #: than transport-shaped approximations of them.
    status: int
    payload: dict[str, Any]


class McpTransport:
    """Executes MCP operations against the governed core."""

    def __init__(
        self,
        *,
        run_dispatcher: RunDispatcher,
        audit_sink: AuditSink,
        evidence_query: EvidenceQuery | None = None,
        authority_submitter: Any | None = None,
        run_index: RunIndex | None = None,
        durability: Any | None = None,
        change_requests: ChangeRequestStore | None = None,
        change_status: Any | None = None,
        definitions: Any | None = None,
        thread_store: ThreadStore | None = None,
        reconciler: Any | None = None,
        ask_conversations: Any | None = None,
        ask_providers: Any | None = None,
        ask_model: str = "unconfigured",
        ask_authority: Any | None = None,
        relevance_judges: Any | None = None,
        relevance_model: str = "unconfigured",
        credential_source: Any | None = None,
        #: 045's second corpus, mirrored from `create_app` exactly (ADR-0033). A collaborator
        #: only one surface holds is a way for the two to differ that no catalogue comparison
        #: can see — and 043 shipped that asymmetry once, with `relevance_note` reaching the
        #: API's caller and not this one.
        endorsed_reader: Any | None = None,
    ) -> None:
        self._dispatcher = run_dispatcher
        self._audit = audit_sink
        # 024. Absent by default: a surface with no model answers 503 rather than answering from
        # the corpus alone, which FR-011a forbids. Injected like the seven collaborators below,
        # because parity compares what the two surfaces DO and one they cannot be shown to share
        # is one they can silently differ on.
        # 027: a FACTORY, not a built provider — `(source, secret) -> provider`, called once per
        # ask with material brokered for that ask. Holding a built provider would hold whatever
        # credential built it for the life of the process.
        self._ask_conversations: Any = ask_conversations
        self._ask_providers: Any = ask_providers
        self._ask_model: str = ask_model
        self._ask_authority: Any = ask_authority
        self._relevance_judges: Any = relevance_judges
        self._relevance_model: str = relevance_model
        # 027. `None` refuses `credential_unavailable`. A default that supplied one would rebuild
        # "configured means permitted" one level below where 026 broke it.
        self._credential_source: Any = credential_source
        self._endorsed_reader: Any = endorsed_reader
        self._evidence = evidence_query
        self._submitter = authority_submitter
        # Mirrors `create_app`'s collaborators exactly, and the mirroring is the point: the
        # parity row compares what the two surfaces DO, and two surfaces holding different
        # collaborators would diverge in ways no catalogue comparison could see.
        self._index: RunIndex = run_index if run_index is not None else InMemoryRunIndex()
        self._durability = durability
        self._changes: ChangeRequestStore = (
            change_requests if change_requests is not None else InMemoryChangeRequestStore()
        )
        self._change_status = change_status
        self._definitions = definitions
        self._threads: ThreadStore = (
            thread_store if thread_store is not None else InMemoryThreadStore()
        )
        self._reconciler = reconciler

    def tool_names(self) -> list[str]:
        return [op.tool_name for op in operations()]

    def call(
        self, tool_name: str, arguments: dict[str, Any], *, subject: AuthenticatedSubject
    ) -> McpResult:
        """Execute one operation as ``subject``.

        The subject is threaded through unchanged. Anything that rewrote it here would
        make every downstream guarantee about a different person, which is the failure the
        delegation chain exists to prevent.
        """
        handler = {
            "start_run": self._start_run,
            "get_run": self._get_run,
            "read_evidence": self._read_evidence,
            "reconcile_evidence": self._reconcile_evidence,
            "request_mapping_change": self._request_mapping_change,
            "collect_mapping_change": self._collect_mapping_change,
            "list_runs": self._list_runs,
            "get_run_result": self._get_run_result,
            "get_run_report": self._get_run_report,
            "ask": self._ask,
            "propose": self._propose,
            "stop_run": self._stop_run,
            "list_agent_definitions": self._list_agent_definitions,
            "get_agent_definition": self._get_agent_definition,
            "create_thread": self._create_thread,
            "ask_conversations": self._ask_conversations_list,
            "ask_conversation": self._ask_conversation,
            "delete_ask_conversation": self._delete_ask_conversation,
            "list_threads": self._list_threads,
            "get_thread": self._get_thread,
            "delete_thread": self._delete_thread,
            "send_turn": self._send_turn,
        }.get(tool_name)

        if handler is None:
            # Unknown operations refuse. A transport that quietly ignored one would make
            # the coverage half of the parity row unfalsifiable.
            return McpResult(ok=False, status=404, payload={"reason": "no such operation"})

        return handler(arguments, subject)

    # ------------------------------------------------------------------ operations

    def _start_run(self, args: dict[str, Any], subject: AuthenticatedSubject) -> McpResult:
        import uuid

        correlation_id = args.get("correlation_id") or (
            f"mcp-{subject.tenant_id}-{uuid.uuid4().hex[:16]}"
        )
        handle: RunHandle = self._dispatcher.dispatch(
            correlation_id=str(correlation_id),
            subject_user_id=subject.subject_user_id,
            tenant_id=subject.tenant_id,
            agent_definition_id=str(args["agent_definition_id"]),
            requested_tools=frozenset(args.get("requested_tools") or ()),
            # THE CALLER'S ROLES, WITHOUT WHICH THE RUN REFUSES ITSELF.
            #
            # This was missing, and `NomadDispatcher.dispatch` defaults it to the empty set —
            # so every run started through MCP reached its allocation, tried to manufacture
            # authority, and died with `no role for subject`. `surfaces/api/runs.py` has
            # passed them all along; this transport never did.
            #
            # **Invisible for four features, for two reinforcing reasons.** The class rows
            # drive a fake dispatcher that ignores the argument, and nothing had ever started
            # a REAL run through MCP because nothing served MCP. The surface-parity gate
            # compared the two transports and could not see it: both were asked to dispatch,
            # both answered 202, and only one produced a run that could authorize itself.
            #
            # Found by 019's rows on the first live `start_run` — which is the whole reason
            # rows must drive a served process rather than a constructed object.
            subject_roles=frozenset(subject.roles),
        )
        # 202, as the API returns: the work is accepted, not completed.
        return McpResult(ok=True, status=202, payload=handle.model_dump(mode="json"))

    def _get_run(self, args: dict[str, Any], subject: AuthenticatedSubject) -> McpResult:
        from surfaces.api.runs import run_state_for

        try:
            handle = run_state_for(
                run_id=str(args["run_id"]),
                subject=subject,
                dispatcher=self._dispatcher,
                audit=self._audit,
            )
        except RecordAccessUnavailable as unrecordable:
            return McpResult(ok=False, status=503, payload={"reason": str(unrecordable)})
        if handle is None:
            return McpResult(ok=False, status=404, payload={"reason": "no such run"})
        return McpResult(ok=True, status=200, payload=handle.model_dump(mode="json"))

    def _propose(self, args: dict[str, Any], subject: AuthenticatedSubject) -> McpResult:
        """Same Propose intake as the API (047 / ADR-0033)."""
        from core.authoring.request import RequestRefused
        from surfaces.api.propose import ProposeRequest, propose_for
        from surfaces.dispatch.nomad import DispatchError

        try:
            accepted = propose_for(
                subject=subject,
                body=ProposeRequest(
                    message=str(args["message"]) if args.get("message") else None,
                    repository=str(args["repository"]) if args.get("repository") else None,
                    task=str(args["task"]) if args.get("task") else None,
                    correlation_id=str(args["correlation_id"])
                    if args.get("correlation_id")
                    else None,
                ),
                dispatcher=self._dispatcher,
                thread_store=self._threads,
            )
        except RequestRefused as refused:
            code = 403 if refused.reason_code == "repository_not_owned" else 400
            return McpResult(ok=False, status=code, payload={"reason": str(refused)})
        except DispatchError as exc:
            return McpResult(ok=False, status=503, payload={"reason": str(exc)})
        except Exception:  # noqa: BLE001 — fail closed
            reason = "Build could not be started"
            return McpResult(ok=False, status=503, payload={"reason": reason})
        return McpResult(ok=True, status=202, payload=accepted.model_dump(mode="json"))

    def _ask(self, args: dict[str, Any], subject: AuthenticatedSubject) -> McpResult:
        """The same verdict the API gives, from the same implementation (ADR-0033).

        Routing, scope, the estate read and the corpus path are all reached through the shared
        functions rather than restated here — two implementations agreeing by inspection would
        make parity a measure of how carefully they were written.
        """
        from datetime import UTC, datetime

        from core.answering.answer import ProviderUnavailable
        from core.answering.context import build_context
        from core.answering.corpus import CorpusUnavailable, load_corpus
        from core.answering.endorsed.corpus import CombinedCorpus, EndorsedCorpus
        from core.answering.estate import EstateProviderUnavailable
        from core.answering.record import record_ask
        from core.answering.routing import Route, route_with_signal
        from surfaces.api.ask import (
            AskCredentialUnavailable,
            AskNotQualified,
            ConversationNotFound,
            ScopeEmpty,
            _available,
            _remember,
            _resolve_conversation,
            ask_for,
            authorise_ask,
            estate_answer_for,
            obtain_ask_credential,
            relevance_enabled_for,
        )
        from surfaces.api.evidence import evidence_stream_for

        question = str(args["question"])
        conversation_id = args.get("conversation_id") or None

        # THE SAME THREE STEPS THE API TAKES, THROUGH THE SAME FUNCTIONS (035, ADR-0033).
        # Resolution before anything else, inheritance only where the question is silent, and
        # a bounded history block — imported rather than restated, because two implementations
        # agreeing by inspection is what parity rows exist to distrust.
        try:
            prior = _resolve_conversation(
                conversations=self._ask_conversations,
                conversation_id=conversation_id,
                subject=subject,
            )
        except ConversationNotFound:
            return McpResult(ok=False, status=404, payload={"detail": "no_such_conversation"})

        destination, had_signal = route_with_signal(question)
        inherited = False
        if not had_signal and prior:
            destination = Route(prior[-1].source)
            inherited = True
        context = build_context(prior, inherited_route=inherited)

        if destination is Route.ESTATE:
            # GOVERNANCE FIRST, through the same shared function the API calls — parity by
            # construction rather than by twin edits (ADR-0033).
            try:
                cell, bound_cell, cell_disposition = authorise_ask(
                    source=str(Route.ESTATE),
                    subject=subject,
                    audit=self._audit,
                    authority=self._ask_authority,
                    available=_available(self._ask_model, self._ask_providers),
                )
            except AskNotQualified as refused:
                return McpResult(ok=False, status=403, payload={"reason": str(refused)})

            if self._evidence is None:
                return McpResult(
                    ok=False,
                    status=503,
                    payload={"reason": "no evidence plane is configured"},
                )
            if self._ask_providers is None:
                return McpResult(
                    ok=False, status=503, payload={"reason": "no model is configured for `ask`"}
                )
            # THE CREDENTIAL, between governance and the vendor — through the same shared
            # function the API calls, so the two surfaces cannot refuse differently (ADR-0033).
            try:
                credential = obtain_ask_credential(
                    credential_source=self._credential_source,
                    model=self._ask_model,
                    subject=subject,
                    audit=self._audit,
                    source=str(Route.ESTATE),
                    cell=cell,
                    bound_cell=bound_cell,
                    cell_disposition=cell_disposition,
                    evidence_stream=evidence_stream_for(subject.tenant_id),
                )
            except AskCredentialUnavailable as unavailable:
                return McpResult(ok=False, status=503, payload={"reason": str(unavailable)})
            try:
                answered = estate_answer_for(
                    question=question,
                    subject=subject,
                    query=self._evidence,
                    audit=self._audit,
                    model=self._ask_model,
                    provider=self._ask_providers(str(Route.ESTATE), credential.secret),
                    context=context.text,
                    conversation_id=conversation_id or "",
                    carried_context=context.descriptor if conversation_id else None,
                    now=datetime.now(UTC),
                    cell=cell,
                    bound_cell=bound_cell,
                    cell_disposition=cell_disposition,
                    model_authority=credential.reference,
                )
                return McpResult(
                    ok=True,
                    status=200,
                    payload=_remember(
                        conversations=self._ask_conversations,
                        conversation_id=conversation_id,
                        subject=subject,
                        question=question,
                        source=str(Route.ESTATE),
                        body=answered,
                        context=context,
                    ),
                )
            except ScopeEmpty as empty:
                return McpResult(ok=False, status=403, payload={"reason": str(empty)})
            except EstateProviderUnavailable as unreachable:
                return McpResult(ok=False, status=503, payload={"reason": str(unreachable)})

        # NO THIRD BRANCH ANY MORE — see the same removal in `surfaces/api/ask.py`. Parity is
        # kept by both surfaces losing it together, which is what ADR-0033 asks of a change to
        # what a transport answers.

        try:
            guidance_cell, guidance_bound, guidance_disposition = authorise_ask(
                source="guidance",
                subject=subject,
                audit=self._audit,
                authority=self._ask_authority,
                available=_available(self._ask_model, self._ask_providers),
            )
        except AskNotQualified as refused:
            return McpResult(ok=False, status=403, payload={"reason": str(refused)})

        try:
            pinned = load_corpus()
        except CorpusUnavailable as unavailable:
            return McpResult(ok=False, status=503, payload={"reason": str(unavailable)})

        # Resolved once per call, the API's reasoning verbatim: one question is one resolution,
        # so no adoption can move the ground under a single answer. The pinned corpus is passed
        # UNCHANGED when nothing is endorsed — an estate that endorsed nothing is the platform
        # it was before this feature, not a new path that happens to be empty.
        endorsed = EndorsedCorpus()
        if self._endorsed_reader is not None:
            try:
                endorsed = self._endorsed_reader()
            except Exception:  # noqa: BLE001 — customer material becoming temporarily uncitable
                # narrows the answer and is disclosed; taking the ask down would let a
                # customer's own outage stop the platform answering from the corpus it ships.
                endorsed = EndorsedCorpus()
        corpus: Any = pinned if endorsed.empty else CombinedCorpus(pinned=pinned, endorsed=endorsed)

        if self._ask_providers is None:
            # Recorded anyway — see the API's note. Someone asked and the platform could not
            # attempt it, which is a fact about this surface worth having in the trail.
            record_ask(
                audit=self._audit,
                subject=subject,
                corpus_digest=corpus.digest,
                evidence_stream="",
                model="unconfigured",
                disposition="provider_unavailable",
                source="guidance",
                cell=guidance_cell,
                bound_cell=guidance_bound,
                cell_disposition=guidance_disposition,
                # No provider, so no vendor call, so no credential exercised.
                model_authority="",
            )
            return McpResult(
                ok=False, status=503, payload={"reason": "no model is configured for `ask`"}
            )
        try:
            credential = obtain_ask_credential(
                credential_source=self._credential_source,
                model=self._ask_model,
                subject=subject,
                audit=self._audit,
                source="guidance",
                cell=guidance_cell,
                bound_cell=guidance_bound,
                cell_disposition=guidance_disposition,
                corpus_digest=corpus.digest,
            )
        except AskCredentialUnavailable as unavailable:
            return McpResult(ok=False, status=503, payload={"reason": str(unavailable)})

        # THE RELEVANCE GATE, ON THIS TRANSPORT TOO (043). Parity is not a nicety here: the
        # ask parity row compares the AUDIT TRAIL of both surfaces, and a gate wired on one
        # would make the API emit `model_gate` while MCP did not — which is exactly the
        # divergence ADR-0033's row exists to catch, and did.
        from surfaces.api.ask import _available, relevance_judge_for

        # 044's toggle, honoured here as well as on the API — ADR-0033 is a statement about
        # what a DEPLOYMENT does, and a gate switched off on one transport and running on the
        # other would make an administrator's decision depend on which door was used. 043
        # shipped exactly that asymmetry once (the API emitted MODEL_GATE and MCP did not),
        # and only the parity row caught it.
        gate_enabled = relevance_enabled_for(self._ask_authority)

        relevance = None
        if gate_enabled:
            try:
                relevance = relevance_judge_for(
                    subject=subject,
                    audit=self._audit,
                    authority=self._ask_authority,
                    judges=self._relevance_judges,
                    available=_available(self._relevance_model, self._relevance_judges),
                )
            except AskNotQualified as refused:
                return McpResult(ok=False, status=403, payload={"reason": str(refused)})

        try:
            payload = ask_for(
                question=question,
                subject=subject,
                corpus=corpus,
                provider=self._ask_providers("guidance", credential.secret),
                audit=self._audit,
                model=self._ask_model,
                cell=guidance_cell,
                bound_cell=guidance_bound,
                cell_disposition=guidance_disposition,
                model_authority=credential.reference,
                context=context.text,
                conversation_id=conversation_id or "",
                carried_context=context.descriptor if conversation_id else None,
                relevance_disabled=not gate_enabled,
                relevance=relevance,
            )
            payload = _remember(
                conversations=self._ask_conversations,
                conversation_id=conversation_id,
                subject=subject,
                question=question,
                source="guidance",
                body=payload,
                context=context,
            )
        except (CorpusUnavailable, ProviderUnavailable) as unavailable:
            return McpResult(ok=False, status=503, payload={"reason": str(unavailable)})
        return McpResult(ok=True, status=200, payload=payload)

    def _get_run_report(self, args: dict[str, Any], subject: AuthenticatedSubject) -> McpResult:
        """021. Reaches the same `report_for` the API route does.

        Not a reimplementation: ADR-0033 asks for the same verdict on every transport, and two
        implementations agreeing by inspection would make that a measure of how carefully they
        were written rather than a property a row can check.
        """
        if self._evidence is None:
            return McpResult(ok=False, status=503, payload={"reason": "evidence unavailable"})

        from surfaces.api.reports import report_for

        response = report_for(
            run_id=str(args.get("run_id") or ""),
            subject=subject,
            query=self._evidence,
            audit=self._audit,
        )
        return McpResult(ok=True, status=200, payload=response.model_dump(mode="json"))

    def _read_evidence(self, args: dict[str, Any], subject: AuthenticatedSubject) -> McpResult:
        if self._evidence is None:
            return McpResult(ok=False, status=503, payload={"reason": "evidence unavailable"})

        from surfaces.api.evidence import read_evidence_for

        try:
            entries, disposition = read_evidence_for(
                query=self._evidence,
                audit=self._audit,
                subject=subject,
                correlation_id=args.get("correlation_id"),
                run_id=args.get("run_id"),
                limit=int(args.get("limit") or 1000),
            )
        except RecordAccessUnavailable as unrecordable:
            # The same 503 the API returns. Before 022 this escaped uncaught.
            return McpResult(ok=False, status=503, payload={"reason": str(unrecordable)})
        return McpResult(
            ok=True,
            status=200,
            payload={
                "entries": [e.model_dump(mode="json") for e in entries],
                "count": len(entries),
                "disposition": str(disposition),
            },
        )

    def _reconcile_evidence(self, args: dict[str, Any], subject: AuthenticatedSubject) -> McpResult:
        if self._evidence is None:
            return McpResult(ok=False, status=503, payload={"reason": "evidence unavailable"})

        from surfaces.api.app import _AbsentReconciler
        from surfaces.api.evidence import _reconciliation_response, reconcile_evidence_for

        # Defaulted the same way the app defaults it, so an estate with no second copy gives
        # the same ABSENT answer on both transports. A transport that returned 503 where the
        # other returned a posture would be two answers to one governance question.
        report, _ = reconcile_evidence_for(
            correlation_id=str(args["correlation_id"]),
            query=self._evidence,
            audit=self._audit,
            subject=subject,
            reconciler=self._reconciler or _AbsentReconciler(),
        )
        correlation_id = str(args["correlation_id"])
        return McpResult(
            ok=True,
            status=200,
            payload=_reconciliation_response(correlation_id, report).model_dump(mode="json"),
        )

    def _definition_views(self, subject: AuthenticatedSubject) -> Any:
        from surfaces.api.definitions import definition_views

        return definition_views(subject=subject, fabric=self._definitions)

    def _list_agent_definitions(
        self, args: dict[str, Any], subject: AuthenticatedSubject
    ) -> McpResult:
        from core.authority.errors import ResolutionRefused

        if self._definitions is None:
            return McpResult(ok=False, status=503, payload={"reason": "definitions unavailable"})
        try:
            views = self._definition_views(subject)
        except ResolutionRefused:
            return McpResult(ok=False, status=503, payload={"reason": "definitions unavailable"})

        return McpResult(
            ok=True,
            status=200,
            payload={"definitions": [v.model_dump(mode="json") for v in views]},
        )

    def _get_agent_definition(
        self, args: dict[str, Any], subject: AuthenticatedSubject
    ) -> McpResult:
        from core.authority.errors import ResolutionRefused

        if self._definitions is None:
            return McpResult(ok=False, status=503, payload={"reason": "definitions unavailable"})
        wanted = str(args["agent_definition_id"])
        try:
            views = self._definition_views(subject)
        except ResolutionRefused:
            return McpResult(ok=False, status=503, payload={"reason": "definitions unavailable"})

        for view in views:
            if view.agent_definition_id == wanted:
                return McpResult(ok=True, status=200, payload=view.model_dump(mode="json"))
        return McpResult(ok=False, status=404, payload={"reason": "no such agent definition"})

    # ------------------------------------------------------------------ threads
    #
    # Each of these delegates to the SAME function the API route calls. That is what makes
    # verdict parity structural: a divergence would require someone to write a second
    # implementation on purpose, rather than merely to update one surface and forget the
    # other.

    def _create_thread(self, args: dict[str, Any], subject: AuthenticatedSubject) -> McpResult:
        from surfaces.api.threads import _thread_view, create_thread_for

        try:
            record = create_thread_for(subject=subject, store=self._threads, audit_sink=self._audit)
        except RecordAccessUnavailable as unrecordable:
            return McpResult(ok=False, status=503, payload={"reason": str(unrecordable)})
        except OperationRefused as refused:
            return self._refused(refused)
        return McpResult(ok=True, status=201, payload=_thread_view(record).model_dump(mode="json"))

    def _ask_conversations_list(
        self, args: dict[str, Any], subject: AuthenticatedSubject
    ) -> McpResult:
        """035. The same function the API route calls — parity by construction (ADR-0033)."""
        from core.answering.conversations.postgres import ConversationStoreError
        from surfaces.api.ask_conversations import list_conversations

        try:
            listed = list_conversations(subject=subject, store=self._ask_conversations)
        except ConversationStoreError:
            # Never an empty list. Telling somebody they have no conversations when nobody
            # could look is a claim about their history the platform cannot make.
            return McpResult(
                ok=False,
                status=503,
                payload={
                    "reason": "your conversations could not be read just now; nothing is lost"
                },
            )
        return McpResult(ok=True, status=200, payload=listed.model_dump(mode="json"))

    def _ask_conversation(self, args: dict[str, Any], subject: AuthenticatedSubject) -> McpResult:
        from core.answering.conversations.postgres import ConversationStoreError
        from surfaces.api.ask_conversations import NO_SUCH_CONVERSATION, read_conversation

        try:
            found = read_conversation(
                conversation_id=str(args["conversation_id"]),
                subject=subject,
                store=self._ask_conversations,
            )
        except ConversationStoreError:
            return McpResult(
                ok=False,
                status=503,
                payload={"reason": "that conversation could not be read just now"},
            )
        if found is None:
            return McpResult(ok=False, status=404, payload={"detail": NO_SUCH_CONVERSATION})
        return McpResult(ok=True, status=200, payload=found.model_dump(mode="json"))

    def _delete_ask_conversation(
        self, args: dict[str, Any], subject: AuthenticatedSubject
    ) -> McpResult:
        from core.answering.conversations.postgres import ConversationStoreError
        from surfaces.api.ask_conversations import NO_SUCH_CONVERSATION, remove_conversation

        try:
            removed = remove_conversation(
                conversation_id=str(args["conversation_id"]),
                subject=subject,
                store=self._ask_conversations,
            )
        except ConversationStoreError:
            return McpResult(
                ok=False,
                status=503,
                payload={"reason": "that conversation could not be deleted just now"},
            )
        if not removed:
            return McpResult(ok=False, status=404, payload={"detail": NO_SUCH_CONVERSATION})
        return McpResult(ok=True, status=204, payload={})

    def _list_threads(self, args: dict[str, Any], subject: AuthenticatedSubject) -> McpResult:
        from surfaces.api.threads import list_threads_for

        try:
            response = list_threads_for(
                subject=subject,
                store=self._threads,
                audit_sink=self._audit,
                limit=int(args.get("limit", DEFAULT_PAGE_SIZE)),
                cursor=args.get("cursor"),
            )
        except RecordAccessUnavailable as unrecordable:
            return McpResult(ok=False, status=503, payload={"reason": str(unrecordable)})
        return McpResult(ok=True, status=200, payload=response.model_dump(mode="json"))

    def _get_thread(self, args: dict[str, Any], subject: AuthenticatedSubject) -> McpResult:
        from surfaces.api.threads import thread_detail_for

        try:
            response = thread_detail_for(
                subject=subject,
                store=self._threads,
                thread_id=str(args["thread_id"]),
                audit_sink=self._audit,
            )
        except RecordAccessUnavailable as unrecordable:
            return McpResult(ok=False, status=503, payload={"reason": str(unrecordable)})
        except OperationRefused as refused:
            return self._refused(refused)
        return McpResult(ok=True, status=200, payload=response.model_dump(mode="json"))

    def _delete_thread(self, args: dict[str, Any], subject: AuthenticatedSubject) -> McpResult:
        from surfaces.api.threads import delete_thread_for

        try:
            delete_thread_for(
                subject=subject,
                store=self._threads,
                audit_sink=self._audit,
                thread_id=str(args["thread_id"]),
            )
        except OperationRefused as refused:
            return self._refused(refused)
        return McpResult(ok=True, status=204, payload={})

    def _send_turn(self, args: dict[str, Any], subject: AuthenticatedSubject) -> McpResult:
        from surfaces.api.threads import SendTurnRequest, send_turn_for

        body = SendTurnRequest(
            message=str(args["message"]),
            agent_definition_id=args.get("agent_definition_id"),
            requested_tools=frozenset(args.get("requested_tools") or ()),
        )
        try:
            view = send_turn_for(
                subject=subject,
                store=self._threads,
                audit_sink=self._audit,
                dispatcher=self._dispatcher,
                fabric=self._definitions,
                durability=self._durability,
                thread_id=str(args["thread_id"]),
                body=body,
            )
        except OperationRefused as refused:
            return self._refused(refused)
        return McpResult(ok=True, status=200, payload=view.model_dump(mode="json"))

    def _refused(self, refused: OperationRefused) -> McpResult:
        """The same 403/404 split the API makes, from the same property.

        Written once so the two transports cannot drift on which refusals are visible —
        which is the half of parity a catalogue comparison cannot see.
        """
        return McpResult(
            ok=False,
            status=403 if refused.is_visible_to_caller else 404,
            payload={"reason": refused.reason_code},
        )

    def _stop_run(self, args: dict[str, Any], subject: AuthenticatedSubject) -> McpResult:
        from core.runs.refusals import OperationRefused
        from surfaces.api.runs import stop_run_for

        try:
            stopped = stop_run_for(
                run_id=str(args["run_id"]),
                subject=subject,
                index=self._index,
                durability=self._durability,
                audit=self._audit,
            )
        except RecordAccessUnavailable as unrecordable:
            return McpResult(ok=False, status=503, payload={"reason": str(unrecordable)})
        except OperationRefused as refused:
            return McpResult(
                ok=False,
                status=403 if refused.is_visible_to_caller else 404,
                payload={"reason": str(refused)},
            )

        return McpResult(ok=True, status=200, payload=stopped.model_dump(mode="json"))

    def _get_run_result(self, args: dict[str, Any], subject: AuthenticatedSubject) -> McpResult:
        from core.runs.refusals import OperationRefused
        from surfaces.api.runs import run_result_for

        try:
            result = run_result_for(
                run_id=str(args["run_id"]),
                subject=subject,
                index=self._index,
                durability=self._durability,
                audit=self._audit,
                thread_store=self._threads,
            )
        except RecordAccessUnavailable as unrecordable:
            # THE SAME VERDICT THE API RETURNS. Research F7 found the evidence path's
            # equivalent raises an HTTPException that this transport does not catch, so its
            # failure path has no parity in the one operation whose docstring argues hardest
            # for it. 022 does not repeat that.
            return McpResult(ok=False, status=503, payload={"reason": str(unrecordable)})
        except OperationRefused as refused:
            return McpResult(
                ok=False,
                status=403 if refused.is_visible_to_caller else 404,
                payload={"reason": str(refused)},
            )

        return McpResult(ok=True, status=200, payload=result.model_dump(mode="json"))

    def _list_runs(self, args: dict[str, Any], subject: AuthenticatedSubject) -> McpResult:
        from core.runs.index import DEFAULT_PAGE_SIZE, RunIndexError
        from surfaces.api.runs import list_runs_for

        try:
            page = list_runs_for(
                subject=subject,
                index=self._index,
                durability=self._durability,
                audit=self._audit,
                limit=int(args.get("limit") or DEFAULT_PAGE_SIZE),
                cursor=args.get("cursor"),
            )
        except RecordAccessUnavailable as unrecordable:
            return McpResult(ok=False, status=503, payload={"reason": str(unrecordable)})
        except RunIndexError:
            # 503 on both transports, because parity compares verdicts and "we could not
            # look" must never arrive as an empty list on either.
            return McpResult(ok=False, status=503, payload={"reason": "run index unavailable"})

        return McpResult(ok=True, status=200, payload=page.model_dump(mode="json"))

    def _collect_mapping_change(
        self, args: dict[str, Any], subject: AuthenticatedSubject
    ) -> McpResult:
        if self._change_status is None:
            return McpResult(ok=False, status=503, payload={"reason": "trust fabric unavailable"})

        from core.runs.refusals import OperationRefused
        from surfaces.api.mappings import collect_mapping_change

        try:
            disposition = collect_mapping_change(
                accessor=str(args["accessor"]),
                subject=subject,
                change_requests=self._changes,
                change_status=self._change_status,
                audit=self._audit,
            )
        except OperationRefused as refused:
            # The same two-way split the route makes, and it must stay the same: parity
            # compares verdicts, so a transport that reported these differently would fail
            # the row — which is the row working rather than an inconvenience.
            return McpResult(
                ok=False,
                status=403 if refused.is_visible_to_caller else 404,
                payload={"reason": "no such change request"},
            )

        return McpResult(
            ok=True,
            status=200,
            payload={
                "accessor": disposition.accessor,
                "disposition": disposition.disposition,
                "approvals": disposition.approvals,
                "request_path": disposition.request_path,
            },
        )

    def _request_mapping_change(
        self, args: dict[str, Any], subject: AuthenticatedSubject
    ) -> McpResult:
        if self._submitter is None:
            return McpResult(ok=False, status=503, payload={"reason": "trust fabric unavailable"})

        from core.identity.claims import ClaimMapping
        from surfaces.api.mappings import submit_mapping_change

        event = submit_mapping_change(
            submitter=self._submitter,
            audit=self._audit,
            subject=subject,
            mapping=ClaimMapping(**args["mapping"]),
            reason=str(args["reason"]),
        )
        from core.authority.changes import ChangeDisposition

        denied = event.disposition is ChangeDisposition.DENIED
        return McpResult(
            ok=not denied,
            status=403 if denied else 202,
            payload={"disposition": event.disposition.value, "accessor": event.accessor},
        )


__all__ = ["McpResult", "McpTransport"]
