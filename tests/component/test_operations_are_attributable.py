# SPDX-License-Identifier: Apache-2.0
"""Every operation is ATTRIBUTABLE, and unauthenticated callers reach none of them.

**This file does not check that any operation writes an audit entry, and its name once implied
that it did.** 022 renamed it for that reason: eight operations shipped unrecorded across
thirteen additions while this file sat beside them looking like the guard against exactly that.
A test named for a check it does not perform is worse than no test, because the next reader
concludes the question is covered.

What *does* check recording is `test_the_claim_matches_behaviour.py`. This file checks
authentication, and always did.

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

#: Every operation added after 008, as (method, path, mcp tool, args).
#:
#: Grown by 012 with the five thread operations. The guard at the bottom of this file is
#: what forced that — and it is worth noticing that it worked: without it, five new
#: operations would have shipped uncovered by the authentication rows above, which is
#: precisely how a coverage check becomes decorative.
NEW_OPERATIONS = [
    # 035's three. Enrolled because the guard below caught their absence, which is the check
    # working exactly as the 021 note beneath describes: an operation that skipped these rows
    # would ship without the authentication coverage every other one has.
    ("GET", "/ask-conversations", "ask_conversations", {}),
    ("GET", "/ask-conversations/c1", "ask_conversation", {"conversation_id": "c1"}),
    ("DELETE", "/ask-conversations/c1", "delete_ask_conversation", {"conversation_id": "c1"}),
    ("GET", "/runs", "list_runs", {}),
    ("GET", "/runs/r/result", "get_run_result", {"run_id": "r"}),
    # 021's report. Added here because the guard below caught its absence — which is the
    # check working: an operation that skipped these rows would ship without the
    # authentication coverage every other one has, and nothing would have said so.
    ("GET", "/runs/r/report", "get_run_report", {"run_id": "r"}),
    # 024. Answering is an API operation (ADR-0034), so it answers to these rows like any other.
    ("POST", "/ask", "ask", {"question": "anything"}),
    # 047. Propose intake — same authentication bar as every other northbound act.
    ("POST", "/propose", "propose", {"repository": "acme/app", "task": "add terraform"}),
    ("POST", "/runs/r/stop", "stop_run", {"run_id": "r"}),
    ("GET", "/claim-mappings/a", "collect_mapping_change", {"accessor": "a"}),
    ("GET", "/agent-definitions", "list_agent_definitions", {}),
    (
        "GET",
        "/agent-definitions/planner",
        "get_agent_definition",
        {"agent_definition_id": "planner"},
    ),
    # 012's five.
    ("POST", "/threads", "create_thread", {}),
    ("GET", "/threads", "list_threads", {}),
    ("GET", "/threads/t", "get_thread", {"thread_id": "t"}),
    ("DELETE", "/threads/t", "delete_thread", {"thread_id": "t"}),
    (
        "POST",
        "/threads/t/turns",
        "send_turn",
        {"thread_id": "t", "message": "hello"},
    ),
    # 015. Reconciliation reads both copies of a stream in full, so it is exactly the
    # kind of operation that must not be reachable without an identity.
    (
        "GET",
        "/evidence/reconciliation?correlation_id=c",
        "reconcile_evidence",
        {"correlation_id": "c"},
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

    If an operation lands and is not listed here, the authentication rows above silently stop
    covering it — which is how a coverage check becomes decorative. It has already caught this
    once: 012's five thread operations were added to the catalogue before they were added here,
    and this row is what noticed.

    **The count is derived, not restated.** This docstring used to say *"eleven operations have
    been added since 008"* and *"if a twelfth lands"*; by 022 the real number was thirteen. The
    LIST below is enforced by the assertion at the bottom and stayed correct the whole time,
    while the PROSE COUNT beside it drifted two behind — a second copy of a fact, maintained by
    hand, going stale exactly as this repository keeps finding they do.
    """
    from surfaces.mcp.operations import operations

    shipped = {op.tool_name for op in operations()}
    listed = {tool for _m, _p, tool, _a in NEW_OPERATIONS}
    original = {"start_run", "get_run", "read_evidence", "request_mapping_change"}

    assert listed == shipped - original, (
        f"{len(NEW_OPERATIONS)} listed here, {len(shipped - original)} shipped since 008"
    )
