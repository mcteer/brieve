# SPDX-License-Identifier: Apache-2.0
"""The MCP operation set — the same four the API exposes, reached the same way.

**Not a reimplementation.** Each operation here calls 008's route handler through the same
dependencies the API resolves, so there is one authorization core with two front doors
rather than two implementations that agree by inspection. ADR-0033's parity guarantee is
only meaningful if the thing being compared shares an implementation; comparing two
independent code paths would measure how carefully they were written, which is exactly
what a conformance row cannot check.

**No tool invocation here either.** The API exposes none (008, FR-007) and neither does
this. Tools are reached by an agent *within* a run; a caller reaching one through a
transport is acting beside the agent rather than through it.

The operation names match the API's snapshot entries deliberately — that snapshot is what
the parity row drives from, and a name that differed would make the two sets look
divergent when they are not.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

#: MCP tool name → the API operation it corresponds to.
#:
#: Explicit rather than derived, because the correspondence is the claim being tested. A
#: mapping computed from the API would make the parity row compare the API against itself.
OPERATION_BY_TOOL: dict[str, tuple[str, str]] = {
    "start_run": ("POST", "/runs"),
    "get_run": ("GET", "/runs/{run_id}"),
    "read_evidence": ("GET", "/evidence"),
    # 015. Reconciliation is a NAMED operation, which ADR-0055 requires precisely so it
    # cannot be an implied capability someone reaches for informally.
    "reconcile_evidence": ("GET", "/evidence/reconciliation"),
    "request_mapping_change": ("POST", "/claim-mappings"),
    "collect_mapping_change": ("GET", "/claim-mappings/{accessor}"),
    "list_runs": ("GET", "/runs"),
    "get_run_result": ("GET", "/runs/{run_id}/result"),
    # 021. A report is what a person actually reads, so it is requestable — and ADR-0033 binds
    # parity across every implemented pair, so it is here as well as on the API. An operation on
    # one surface and not the other is a second authorization path wearing a friendlier name.
    "get_run_report": ("GET", "/runs/{run_id}/report"),
    "stop_run": ("POST", "/runs/{run_id}/stop"),
    "list_agent_definitions": ("GET", "/agent-definitions"),
    "get_agent_definition": ("GET", "/agent-definitions/{agent_definition_id}"),
    # 012. Threads are what make this a conversation rather than a queue, and they are on
    # BOTH transports because an operation on one surface and not the other is a second
    # authorization path wearing a friendlier name — which is exactly what MCP would be
    # tempted to skip, being the surface where "just this one helper" is cheapest.
    "create_thread": ("POST", "/threads"),
    "list_threads": ("GET", "/threads"),
    "get_thread": ("GET", "/threads/{thread_id}"),
    "delete_thread": ("DELETE", "/threads/{thread_id}"),
    "send_turn": ("POST", "/threads/{thread_id}/turns"),
}


#: Whether an operation records a trail entry, and under which rule.
#:
#: **THE RULE: an operation that touches a run or a thread records. One that touches neither
#: does not.** Runs and threads are records of *activity* — what a person asked for, what a
#: model chose, what a tool did. Agent definitions are *configuration*: reading one discloses
#: how the platform is set up, not what anyone did with it. A new operation is classified by
#: which of those two it touches.
#:
#: * ``records`` — writes its own entry. Reads go to ``record-access:{tenant}``; acts on a run
#:   or thread go to that run's or thread's own stream.
#: * ``records_elsewhere`` — the act is recorded, but by the machinery it starts rather than by
#:   the operation. **Must name where.** A disposition saying "recorded somewhere" without
#:   saying where is indistinguishable from a wrong one — and that is not hypothetical: an
#:   earlier draft of 022 classified ``stop_run`` this way, and applying this rule is what
#:   revealed there was no where. It wrote nothing at all.
#: * ``no_record`` — touches neither a run nor a thread. Deliberate, and pinned by a row, so
#:   that widening it later is a decision someone makes rather than a drift nobody notices.
RECORDS: Final[str] = "records"
RECORDS_ELSEWHERE: Final[str] = "records_elsewhere"
NO_RECORD: Final[str] = "no_record"

AUDIT_DISPOSITIONS: Final[frozenset[str]] = frozenset({RECORDS, RECORDS_ELSEWHERE, NO_RECORD})


@dataclass(frozen=True)
class McpOperation:
    """One operation this surface exposes."""

    tool_name: str
    method: str
    path: str
    description: str
    input_schema: dict[str, Any]
    #: Whether this operation records. **Required, with no default** — an operation added
    #: without deciding must be a construction error rather than a missed edit to a list
    #: someone has to remember. Eight operations shipped unrecorded across thirteen additions
    #: under a guard that required a human to notice; this one cannot be skipped.
    audit_disposition: str
    #: Where the record lands, when the disposition is not ``records``. Empty otherwise.
    audit_note: str = ""

    def __post_init__(self) -> None:
        if self.audit_disposition not in AUDIT_DISPOSITIONS:
            raise ValueError(
                f"{self.tool_name}: unknown audit disposition "
                f"{self.audit_disposition!r}; expected one of {sorted(AUDIT_DISPOSITIONS)}"
            )
        if self.audit_disposition == RECORDS_ELSEWHERE and not self.audit_note.strip():
            raise ValueError(
                f"{self.tool_name}: disposition {RECORDS_ELSEWHERE!r} must name where the act "
                "is recorded — a disposition that says 'recorded somewhere' without saying "
                "where is indistinguishable from a wrong one"
            )


def governance_sentence() -> str:
    """What a client is told about recording — **derived from the dispositions, never written**.

    022's FR-011 asks for a check that fails when the surface's self-description asserts coverage
    the service does not provide. A row comparing this sentence to a second hand-written
    expectation would have passed every day the gap existed, because keeping the two in sync is
    exactly the thing that failed: the sentence said *every operation* is recorded while nine of
    seventeen wrote nothing.

    So the sentence cannot overclaim without the catalogue lying first, and the catalogue is
    checked against measured behaviour by its own rows. This is the same argument the feature
    makes about reports — presentation derived from records, never composed beside them.
    """
    recorded = sorted(o.tool_name for o in operations() if o.audit_disposition == RECORDS)
    unrecorded = sorted(o.tool_name for o in operations() if o.audit_disposition == NO_RECORD)
    return (
        f"Every operation executes as the calling user. {len(recorded)} of {len(operations())} "
        "write their own entry to the tamper-evident trail — every operation that touches a run "
        f"or a thread ({', '.join(recorded)}) — and the rest are recorded by the machinery they "
        f"start. {' and '.join(unrecorded)} return configuration rather than activity and are "
        "deliberately not recorded."
    )


def operations() -> list[McpOperation]:
    """Every operation, in the order a client would see them listed."""
    return [
        McpOperation(
            tool_name="start_run",
            audit_disposition=RECORDS_ELSEWHERE,
            audit_note="the run itself writes `authority_issued` and `run_start`",
            method="POST",
            path="/runs",
            description=(
                "Start a governed run and return a handle. Returns immediately — the run "
                "outlives the call, and its state is queried through the handle."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "agent_definition_id": {"type": "string", "minLength": 1},
                    "requested_tools": {"type": "array", "items": {"type": "string"}},
                    "correlation_id": {"type": ["string", "null"]},
                },
                "required": ["agent_definition_id"],
                "additionalProperties": False,
            },
        ),
        McpOperation(
            tool_name="get_run",
            audit_disposition=RECORDS,
            method="GET",
            path="/runs/{run_id}",
            description="Return a run's current state through its handle.",
            input_schema={
                "type": "object",
                "properties": {"run_id": {"type": "string", "minLength": 1}},
                "required": ["run_id"],
                "additionalProperties": False,
            },
        ),
        McpOperation(
            tool_name="read_evidence",
            audit_disposition=RECORDS_ELSEWHERE,
            audit_note="`evidence.py` writes `evidence_read` / `evidence_read_refused`",
            method="GET",
            path="/evidence",
            description=(
                "Read the audit trail, bounded by your own entitlements. Reading evidence "
                "is itself recorded."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "correlation_id": {"type": ["string", "null"]},
                    "run_id": {"type": ["string", "null"]},
                    "limit": {"type": "integer", "minimum": 1},
                },
                # No tenant. Scope comes from the authenticated subject, and a tenant
                # parameter would be a request to widen it — the same absence the API has.
                "additionalProperties": False,
            },
        ),
        McpOperation(
            tool_name="reconcile_evidence",
            audit_disposition=RECORDS_ELSEWHERE,
            audit_note="`emit_reconciled` writes `audit_reconciled`",
            method="GET",
            path="/evidence/reconciliation",
            description=(
                "Compare a stream's audit trail against the second copy held outside this "
                "platform's administrative control, and report any divergence. Reports "
                "locations, never contents, and is itself recorded."
            ),
            input_schema={
                "type": "object",
                "properties": {"correlation_id": {"type": "string", "minLength": 1}},
                # Required, and one stream at a time. An estate-wide sweep would name other
                # tenants' streams to whoever asked; that sweep is the platform's own
                # scheduled pass, run under the platform's identity.
                "required": ["correlation_id"],
                "additionalProperties": False,
            },
        ),
        McpOperation(
            tool_name="request_mapping_change",
            audit_disposition=RECORDS_ELSEWHERE,
            audit_note="the mapping path writes its own decision entry",
            method="POST",
            path="/claim-mappings",
            description=(
                "Request a claim-to-role mapping change. Returns pending: the change is "
                "queued for quorum, which is not a denial."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "mapping": {"type": "object"},
                    "reason": {"type": "string", "minLength": 1},
                },
                "required": ["mapping", "reason"],
                "additionalProperties": False,
            },
        ),
        McpOperation(
            tool_name="list_runs",
            audit_disposition=RECORDS,
            method="GET",
            path="/runs",
            description=(
                "The runs you have started, newest first. Bounded; pass the returned "
                "cursor for the next page. Absent cursor means there is nothing further."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "minimum": 1},
                    "cursor": {"type": ["string", "null"]},
                },
                # No subject and no tenant. Both come from the authenticated caller, and a
                # parameter for either would be a request to list someone else's work.
                "additionalProperties": False,
            },
        ),
        McpOperation(
            tool_name="get_run_result",
            audit_disposition=RECORDS,
            method="GET",
            path="/runs/{run_id}/result",
            description=(
                "What a run produced. Distinguishes still-running, finished with a "
                "result, and ended without one — three states an empty answer would "
                "conflate."
            ),
            input_schema={
                "type": "object",
                "properties": {"run_id": {"type": "string", "minLength": 1}},
                "required": ["run_id"],
                "additionalProperties": False,
            },
        ),
        McpOperation(
            tool_name="get_run_report",
            audit_disposition=RECORDS_ELSEWHERE,
            audit_note="compiling a report writes `evidence_read` through the governed path (021)",
            method="GET",
            path="/runs/{run_id}/report",
            description=(
                "What a run did, compiled from its records: what ran, what was refused, "
                "and what could not be verified. Every claim traces to evidence and "
                "nothing is composed. Observations are facts about run-end, not about "
                "the product now."
            ),
            input_schema={
                "type": "object",
                "properties": {"run_id": {"type": "string", "minLength": 1}},
                "required": ["run_id"],
                "additionalProperties": False,
            },
        ),
        McpOperation(
            tool_name="stop_run",
            audit_disposition=RECORDS,
            method="POST",
            path="/runs/{run_id}/stop",
            description=(
                "End a run you started. Terminal and unilateral — not a pause, and "
                "nothing resumes it. The step in flight finishes first, so a stop is not "
                "instant."
            ),
            input_schema={
                "type": "object",
                "properties": {"run_id": {"type": "string", "minLength": 1}},
                "required": ["run_id"],
                "additionalProperties": False,
            },
        ),
        McpOperation(
            tool_name="list_agent_definitions",
            audit_disposition=NO_RECORD,
            method="GET",
            path="/agent-definitions",
            description=(
                "Agent definitions you can see, each marked with whether you may start "
                "it. Ones you cannot start still appear — so you know what to ask for."
            ),
            input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        ),
        McpOperation(
            tool_name="get_agent_definition",
            audit_disposition=NO_RECORD,
            method="GET",
            path="/agent-definitions/{agent_definition_id}",
            description="One agent definition's public view.",
            input_schema={
                "type": "object",
                "properties": {"agent_definition_id": {"type": "string", "minLength": 1}},
                "required": ["agent_definition_id"],
                "additionalProperties": False,
            },
        ),
        McpOperation(
            tool_name="collect_mapping_change",
            audit_disposition=RECORDS_ELSEWHERE,
            audit_note="the mapping path writes its own collection entry",
            method="GET",
            path="/claim-mappings/{accessor}",
            description=(
                "Report what became of a change you requested. Pending is a legitimate "
                "answer for as long as approvers have not acted — it is not a failure, "
                "and asking again never advances the request."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "accessor": {"type": "string", "minLength": 1},
                },
                "required": ["accessor"],
                # No requester. Who is asking comes from the authenticated subject, and a
                # requester parameter would be a request to read someone else's change.
                "additionalProperties": False,
            },
        ),
        McpOperation(
            tool_name="create_thread",
            audit_disposition=RECORDS,
            method="POST",
            path="/threads",
            description="Start a conversation. Returns its identifier.",
            input_schema={
                "type": "object",
                # No subject and no tenant. Both come from the authenticated caller, and a
                # parameter for either would be a request to start someone else's thread.
                "properties": {},
                "additionalProperties": False,
            },
        ),
        McpOperation(
            tool_name="list_threads",
            audit_disposition=RECORDS,
            method="GET",
            path="/threads",
            description="The conversations you have started, newest first.",
            input_schema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "minimum": 1, "maximum": 200},
                    "cursor": {"type": "string"},
                },
                "additionalProperties": False,
            },
        ),
        McpOperation(
            tool_name="get_thread",
            audit_disposition=RECORDS,
            method="GET",
            path="/threads/{thread_id}",
            description="One conversation, with its turns in order.",
            input_schema={
                "type": "object",
                "properties": {"thread_id": {"type": "string", "minLength": 1}},
                "required": ["thread_id"],
                "additionalProperties": False,
            },
        ),
        McpOperation(
            tool_name="delete_thread",
            audit_disposition=RECORDS_ELSEWHERE,
            audit_note="`threads.py` writes `thread_deleted`",
            method="DELETE",
            path="/threads/{thread_id}",
            description=(
                "Remove a conversation's view. The audit trail keeps every message it held."
            ),
            input_schema={
                "type": "object",
                "properties": {"thread_id": {"type": "string", "minLength": 1}},
                "required": ["thread_id"],
                "additionalProperties": False,
            },
        ),
        McpOperation(
            tool_name="send_turn",
            audit_disposition=RECORDS_ELSEWHERE,
            audit_note="`threads.py` writes `turn_recorded` / `turn_refused`",
            method="POST",
            path="/threads/{thread_id}/turns",
            description=(
                "Say something in a conversation. The message is recorded as evidence "
                "before anything acts on it; selecting an agent dispatches a run."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "thread_id": {"type": "string", "minLength": 1},
                    "message": {"type": "string", "minLength": 1, "maxLength": 8192},
                    # Optional: its absence is what a decline means. There is no intent
                    # routing here — that needs a model, which this feature does not have.
                    "agent_definition_id": {"type": "string"},
                    "requested_tools": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["thread_id", "message"],
                "additionalProperties": False,
            },
        ),
    ]


def operation_pairs() -> set[tuple[str, str]]:
    """(method, path) for every exposed operation — the set parity compares."""
    return {(op.method, op.path) for op in operations()}


__all__ = ["OPERATION_BY_TOOL", "McpOperation", "operation_pairs", "operations"]
