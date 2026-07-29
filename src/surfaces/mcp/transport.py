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
    ) -> None:
        self._dispatcher = run_dispatcher
        self._audit = audit_sink
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
            "request_mapping_change": self._request_mapping_change,
            "collect_mapping_change": self._collect_mapping_change,
            "list_runs": self._list_runs,
            "get_run_result": self._get_run_result,
            "stop_run": self._stop_run,
            "list_agent_definitions": self._list_agent_definitions,
            "get_agent_definition": self._get_agent_definition,
            "create_thread": self._create_thread,
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
        )
        # 202, as the API returns: the work is accepted, not completed.
        return McpResult(ok=True, status=202, payload=handle.model_dump(mode="json"))

    def _get_run(self, args: dict[str, Any], subject: AuthenticatedSubject) -> McpResult:
        handle = self._dispatcher.state_of(str(args["run_id"]))
        if handle is None:
            return McpResult(ok=False, status=404, payload={"reason": "no such run"})
        return McpResult(ok=True, status=200, payload=handle.model_dump(mode="json"))

    def _read_evidence(self, args: dict[str, Any], subject: AuthenticatedSubject) -> McpResult:
        if self._evidence is None:
            return McpResult(ok=False, status=503, payload={"reason": "evidence unavailable"})

        from surfaces.api.evidence import read_evidence_for

        entries, disposition = read_evidence_for(
            query=self._evidence,
            audit=self._audit,
            subject=subject,
            correlation_id=args.get("correlation_id"),
            run_id=args.get("run_id"),
            limit=int(args.get("limit") or 1000),
        )
        return McpResult(
            ok=True,
            status=200,
            payload={
                "entries": [e.model_dump(mode="json") for e in entries],
                "count": len(entries),
                "disposition": str(disposition),
            },
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
            record = create_thread_for(subject=subject, store=self._threads)
        except OperationRefused as refused:
            return self._refused(refused)
        return McpResult(ok=True, status=201, payload=_thread_view(record).model_dump(mode="json"))

    def _list_threads(self, args: dict[str, Any], subject: AuthenticatedSubject) -> McpResult:
        from surfaces.api.threads import list_threads_for

        response = list_threads_for(
            subject=subject,
            store=self._threads,
            limit=int(args.get("limit", DEFAULT_PAGE_SIZE)),
            cursor=args.get("cursor"),
        )
        return McpResult(ok=True, status=200, payload=response.model_dump(mode="json"))

    def _get_thread(self, args: dict[str, Any], subject: AuthenticatedSubject) -> McpResult:
        from surfaces.api.threads import thread_detail_for

        try:
            response = thread_detail_for(
                subject=subject, store=self._threads, thread_id=str(args["thread_id"])
            )
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
            )
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
            )
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
                limit=int(args.get("limit") or DEFAULT_PAGE_SIZE),
                cursor=args.get("cursor"),
            )
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
