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
from typing import Any

#: MCP tool name → the API operation it corresponds to.
#:
#: Explicit rather than derived, because the correspondence is the claim being tested. A
#: mapping computed from the API would make the parity row compare the API against itself.
OPERATION_BY_TOOL: dict[str, tuple[str, str]] = {
    "start_run": ("POST", "/runs"),
    "get_run": ("GET", "/runs/{run_id}"),
    "read_evidence": ("GET", "/evidence"),
    "request_mapping_change": ("POST", "/claim-mappings"),
    "collect_mapping_change": ("GET", "/claim-mappings/{accessor}"),
    "list_runs": ("GET", "/runs"),
    "get_run_result": ("GET", "/runs/{run_id}/result"),
}


@dataclass(frozen=True)
class McpOperation:
    """One operation this surface exposes."""

    tool_name: str
    method: str
    path: str
    description: str
    input_schema: dict[str, Any]


def operations() -> list[McpOperation]:
    """Every operation, in the order a client would see them listed."""
    return [
        McpOperation(
            tool_name="start_run",
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
            tool_name="request_mapping_change",
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
            tool_name="collect_mapping_change",
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
    ]


def operation_pairs() -> set[tuple[str, str]]:
    """(method, path) for every exposed operation — the set parity compares."""
    return {(op.method, op.path) for op in operations()}


__all__ = ["OPERATION_BY_TOOL", "McpOperation", "operation_pairs", "operations"]
