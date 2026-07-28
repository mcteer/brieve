# SPDX-License-Identifier: Apache-2.0
"""Every operation is attributable, and unauthenticated callers reach none of them.

Two halves of FR-016/FR-017 that are easy to assume rather than assert. 008's structural
argument — a route without a subject dependency has no subject to thread onward, so it
cannot do anything — is strong and is an *argument*. These rows are the check.

The refusal-vocabulary half matters for a different reason: FR-020 splits what a caller
sees from what the trail records, and the split only works if the trail actually
distinguishes the cases the caller cannot.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from core.runs.refusals import (
    INDISTINGUISHABLE_TO_CALLER,
    OPERATION_REASONS,
    OperationRefused,
)
from tests.harness.api_fixtures import surface_under_test

#: Every operation 011 added, as (method, path, mcp tool).
NEW_OPERATIONS = [
    ("GET", "/runs", "list_runs", {}),
    ("GET", "/runs/r/result", "get_run_result", {"run_id": "r"}),
    ("POST", "/runs/r/stop", "stop_run", {"run_id": "r"}),
    ("GET", "/claim-mappings/a", "collect_mapping_change", {"accessor": "a"}),
    ("GET", "/agent-definitions", "list_agent_definitions", {}),
    (
        "GET",
        "/agent-definitions/planner",
        "get_agent_definition",
        {"agent_definition_id": "planner"},
    ),
]


def test_no_new_operation_serves_an_unauthenticated_caller() -> None:
    """FR-016, asserted rather than argued.

    Every operation this feature added, called with no credential. None may succeed —
    and none may fail with a 404 that would tell an anonymous caller whether something
    exists, which is why the assertion is on the authentication classes specifically.
    """
    client = TestClient(surface_under_test().app)

    for method, path, _tool, _args in NEW_OPERATIONS:
        response = client.request(method, path)
        assert response.status_code in (401, 403), (
            f"{method} {path} answered {response.status_code} to a caller with no "
            "credential — the operation is reachable without an identity"
        )


def test_an_invalid_token_is_refused_everywhere_too() -> None:
    """A garbage bearer is not the same code path as no header at all."""
    client = TestClient(surface_under_test().app)

    for method, path, _tool, _args in NEW_OPERATIONS:
        response = client.request(method, path, headers={"Authorization": "Bearer nonsense"})
        assert response.status_code in (401, 403), f"{method} {path} accepted a forged token"


def test_the_trail_distinguishes_what_the_caller_cannot() -> None:
    """FR-020's split, asserted on the vocabulary rather than on one route.

    The caller sees not-found whether a record was absent or another tenant's. The trail
    records which — because a run of `outside_tenant` entries is someone probing, and a
    trail that had collapsed them would show a user who mistypes a lot.
    """
    assert INDISTINGUISHABLE_TO_CALLER == {"no_such_record", "outside_tenant"}
    assert "not_permitted" not in INDISTINGUISHABLE_TO_CALLER

    absent = OperationRefused("gone", reason_code="no_such_record")
    elsewhere = OperationRefused("elsewhere", reason_code="outside_tenant")
    theirs = OperationRefused("theirs", reason_code="not_permitted")

    # Same answer to the caller...
    assert absent.is_visible_to_caller is elsewhere.is_visible_to_caller is False
    # ...different records in the trail.
    assert absent.reason_code != elsewhere.reason_code
    assert theirs.is_visible_to_caller


def test_every_reason_code_says_what_it_means() -> None:
    """A vocabulary with an undocumented member is one that will grow another."""
    assert all(meaning.strip() for meaning in OPERATION_REASONS.values())
    assert INDISTINGUISHABLE_TO_CALLER <= set(OPERATION_REASONS)


def test_the_operation_list_here_matches_what_shipped() -> None:
    """Guards this file against the feature growing past it.

    Six operations were added. If a seventh lands and is not listed here, the
    authentication rows above silently stop covering it — which is how a coverage check
    becomes decorative.
    """
    from surfaces.mcp.operations import operations

    shipped = {op.tool_name for op in operations()}
    listed = {tool for _m, _p, tool, _a in NEW_OPERATIONS}
    original = {"start_run", "get_run", "read_evidence", "request_mapping_change"}

    assert listed == shipped - original
