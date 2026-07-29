# SPDX-License-Identifier: Apache-2.0
"""Row: the same operation on either transport yields the same verdict and equivalent audit.

**The row ADR-0033 has been owed since 008**, claimable now that two transports exist.

008 refused it for a good reason — parity is a property *between* transports and there was
one. What this feature does is not simply claim it: the constitutional row read "across all
four transports", which two cannot satisfy, so 009 amended it to bind across every pair of
implemented transports and then satisfies it for the API/MCP pair. Claiming the row as
worded would have been the stub ADR-0047 forbids, in the feature whose spec makes a point
of refusing stubs.

Driven from `specs/008-northbound-api/contracts/operations.snapshot.json`, which is why
008 committed it. That prerequisite is also a check: if the snapshot has drifted from the
API, parity is measuring the wrong thing, and the drift surfaces here as the first failure
rather than as a mystery three commits later.
"""

from __future__ import annotations

import json
import pathlib

from fastapi.testclient import TestClient

from surfaces.mcp.operations import operation_pairs
from tests.harness.api_fixtures import surface_under_test
from tests.harness.parity import project

SNAPSHOT = (
    pathlib.Path(__file__).resolve().parents[3]
    / "specs"
    / "008-northbound-api"
    / "contracts"
    / "operations.snapshot.json"
)


def _api_pairs() -> set[tuple[str, str]]:
    return {(op["method"], op["path"]) for op in json.loads(SNAPSHOT.read_text())}


# --------------------------------------------------------------------- coverage


def test_row_both_transports_expose_the_same_operations() -> None:
    """Asymmetry in **either** direction fails.

    Including MCP exposing something the API does not, which is the direction a
    transport-specific convenience actually grows — someone adds "just this one helper"
    where it is easiest, and the surfaces diverge from the side nobody is watching.
    """
    assert operation_pairs() == _api_pairs()


def test_the_comparison_has_something_to_compare() -> None:
    """Without this, two empty sets would satisfy the row above."""
    assert len(_api_pairs()) >= 4


def test_break_fixture_an_operation_on_one_transport_only_is_detected() -> None:
    """Self-verifying: constructs the divergence and asserts it is caught."""
    smuggled = operation_pairs() | {("POST", "/mcp-only-convenience")}
    assert smuggled != _api_pairs()


# --------------------------------------------------------------------- verdicts


def test_row_start_run_yields_the_same_verdict() -> None:
    surface = surface_under_test()
    client = TestClient(surface.app)

    api = client.post(
        "/runs",
        json={"agent_definition_id": "planner", "requested_tools": ["echo"]},
        headers=surface.bearer(),
    )
    mcp = surface.mcp.call(
        "start_run",
        {"agent_definition_id": "planner", "requested_tools": ["echo"]},
        subject=surface.subject(),
    )

    assert api.status_code == mcp.status == 202


def test_row_unknown_run_yields_the_same_verdict() -> None:
    surface = surface_under_test()
    client = TestClient(surface.app)

    api = client.get("/runs/no-such-run", headers=surface.bearer())
    mcp = surface.mcp.call("get_run", {"run_id": "no-such-run"}, subject=surface.subject())

    assert api.status_code == mcp.status == 404


def test_row_evidence_read_yields_the_same_verdict() -> None:
    surface = surface_under_test()
    client = TestClient(surface.app)

    api = client.get("/evidence", headers=surface.bearer())
    mcp = surface.mcp.call("read_evidence", {}, subject=surface.subject())

    assert api.status_code == mcp.status == 200


def test_row_mapping_change_is_pending_on_both() -> None:
    """202 on both, and the reason this matters is the same on both.

    A client that reads 403 stops asking, so a change approved twenty minutes later is
    never collected. A transport that got this wrong would produce a verdict difference
    here rather than a subtle behavioural one in production.
    """
    surface = surface_under_test()
    client = TestClient(surface.app)
    body = {
        "mapping": {"claim_name": "groups", "claim_value": "sre", "role": "operator"},
        "reason": "onboarding",
    }

    api = client.post("/claim-mappings", json=body, headers=surface.bearer())
    mcp = surface.mcp.call("request_mapping_change", body, subject=surface.subject())

    assert api.status_code == mcp.status == 202


# --------------------------------------------------------------------- audit


def test_row_audit_events_are_equivalent() -> None:
    """Same types, same order, same subject, same decision fields.

    Not "both produced some audit", which two surfaces agreeing about nothing would also
    satisfy — and which is what this row would assert if the projection were left unnamed.
    """
    api_surface = surface_under_test()
    mcp_surface = surface_under_test()

    api_body = {"agent_definition_id": "planner", "requested_tools": ["echo"]}
    api_response = TestClient(api_surface.app).post(
        "/runs", json=api_body, headers=api_surface.bearer()
    )
    mcp_result = mcp_surface.mcp.call("start_run", api_body, subject=mcp_surface.subject())

    api_trail = project(
        api_surface.audit.list_by_correlation_id(api_response.json()["correlation_id"])
    )
    mcp_trail = project(
        mcp_surface.audit.list_by_correlation_id(mcp_result.payload["correlation_id"])
    )

    assert api_trail == mcp_trail
    assert api_trail, "an empty projection would make this row vacuous"


def test_row_the_subject_is_the_caller_on_both() -> None:
    """MCP acts as the calling user, never as itself (FR-002a).

    A service account would collapse every caller into one subject and destroy the
    non-repudiation the delegation chain exists for — invisibly, because everything else
    would still work.
    """
    surface = surface_under_test()
    result = surface.mcp.call(
        "start_run",
        {"agent_definition_id": "planner", "requested_tools": ["echo"]},
        subject=surface.subject(),
    )

    entries = surface.audit.list_by_correlation_id(result.payload["correlation_id"])
    issued = [e for e in entries if str(e.event_type) == "authority_issued"]
    assert issued, "starting a run through MCP wrote no authority record"
    assert issued[0].payload["subject_user_id"] == "alice"
    assert "mcp" not in str(issued[0].payload["subject_user_id"]).lower()


def test_break_fixture_an_extra_audit_event_is_detected() -> None:
    """The fixture that proves the audit comparison is doing work.

    Breaking a *verdict* would be caught by the verdict rows above, so it would prove
    nothing about this one. This adds an event to one side only.
    """
    surface = surface_under_test()
    result = surface.mcp.call(
        "start_run",
        {"agent_definition_id": "planner", "requested_tools": ["echo"]},
        subject=surface.subject(),
    )
    correlation_id = result.payload["correlation_id"]
    baseline = project(surface.audit.list_by_correlation_id(correlation_id))

    from core.audit.schema import AuditEventType

    surface.audit.append_event(
        correlation_id=correlation_id,
        tenant_id="tenant-test",
        event_type=AuditEventType.PRE_DECISION,
        payload={"outcome": "allow"},
    )
    divergent = project(surface.audit.list_by_correlation_id(correlation_id))

    assert divergent != baseline, "an extra event slipped past the projection"


# ------------------------------------------------------- verdicts, 011's operations
#
# The coverage half of parity grows by construction — the snapshot IS the compared set, so
# adding an operation to one transport fails immediately. The VERDICT half does not: two
# surfaces can expose the same ten operations and disagree about what each returns, and
# nothing would notice unless someone wrote these.


def test_row_listing_runs_yields_the_same_verdict() -> None:
    surface = surface_under_test()
    client = TestClient(surface.app)

    api = client.get("/runs", headers=surface.bearer())
    mcp = surface.mcp.call("list_runs", {}, subject=surface.subject())

    assert api.status_code == mcp.status == 200
    assert api.json()["runs"] == mcp.payload["runs"]


def test_row_an_unknown_runs_result_yields_the_same_verdict() -> None:
    """Both answer not-found, and both for the same reason — a run nobody started.

    The tenant collapse means this is also the answer for another tenant's run, which is
    why the two transports agreeing here is worth asserting rather than assuming.
    """
    surface = surface_under_test()
    client = TestClient(surface.app)

    api = client.get("/runs/no-such-run/result", headers=surface.bearer())
    mcp = surface.mcp.call("get_run_result", {"run_id": "no-such-run"}, subject=surface.subject())

    assert api.status_code == mcp.status == 404


def test_row_stopping_an_unknown_run_yields_the_same_verdict() -> None:
    surface = surface_under_test()
    client = TestClient(surface.app)

    api = client.post("/runs/no-such-run/stop", headers=surface.bearer())
    mcp = surface.mcp.call("stop_run", {"run_id": "no-such-run"}, subject=surface.subject())

    assert api.status_code == mcp.status == 404


def test_row_collecting_an_unknown_change_yields_the_same_verdict() -> None:
    surface = surface_under_test()
    client = TestClient(surface.app)

    api = client.get("/claim-mappings/no-such-accessor", headers=surface.bearer())
    mcp = surface.mcp.call(
        "collect_mapping_change", {"accessor": "no-such-accessor"}, subject=surface.subject()
    )

    assert api.status_code == mcp.status == 404


def test_row_enumerating_definitions_yields_the_same_verdict_and_marking() -> None:
    """Same list, same `may_start` on every entry.

    The marking is the part worth comparing: two surfaces could both return two
    definitions and disagree about which the caller may start, which is a difference a
    person would act on.
    """
    surface = surface_under_test()
    client = TestClient(surface.app)

    api = client.get("/agent-definitions", headers=surface.bearer())
    mcp = surface.mcp.call("list_agent_definitions", {}, subject=surface.subject())

    assert api.status_code == mcp.status == 200
    assert api.json()["definitions"] == mcp.payload["definitions"]
    assert api.json()["definitions"], "an empty comparison would make this row vacuous"


# --------------------------------------------------------- 012: thread verdicts
#
# The catalogue half of parity now compares fifteen operations instead of ten, and it
# passed the moment both surfaces listed them. These rows are the other half: two surfaces
# can expose the same operation and disagree about what it *answers*, and a conversational
# surface that declined on one transport while dispatching on the other would be two
# authorization paths wearing one name.


def _thread_on_both(surface: object) -> str:
    """A thread both transports can see, created through the API.

    Created once and used from both sides deliberately — the surfaces share a store, so a
    thread made here is a thread MCP must be able to reach. If they held separate stores
    this would fail, which is the divergence worth catching.
    """
    client = TestClient(surface.app)  # type: ignore[attr-defined]
    created = client.post("/threads", headers=surface.bearer())  # type: ignore[attr-defined]
    assert created.status_code == 201
    return str(created.json()["thread_id"])


def test_row_thread_creation_yields_the_same_verdict() -> None:
    surface = surface_under_test()
    client = TestClient(surface.app)

    api = client.post("/threads", headers=surface.bearer())
    mcp = surface.mcp.call("create_thread", {}, subject=surface.subject())

    assert api.status_code == mcp.status == 201


def test_row_an_unknown_thread_yields_the_same_verdict() -> None:
    surface = surface_under_test()
    client = TestClient(surface.app)

    api = client.get("/threads/th-nonexistent", headers=surface.bearer())
    mcp = surface.mcp.call("get_thread", {"thread_id": "th-nonexistent"}, subject=surface.subject())

    assert api.status_code == mcp.status == 404


def test_row_a_declined_turn_yields_the_same_verdict_and_disposition() -> None:
    """A decline is a 200 with a disposition on both, not an error on one of them."""
    surface = surface_under_test()
    client = TestClient(surface.app)
    thread_id = _thread_on_both(surface)

    api = client.post(
        f"/threads/{thread_id}/turns",
        json={"message": "what can you do?"},
        headers=surface.bearer(),
    )
    mcp = surface.mcp.call(
        "send_turn",
        {"thread_id": thread_id, "message": "what can you do?"},
        subject=surface.subject(),
    )

    assert api.status_code == mcp.status == 200
    assert api.json()["disposition"] == mcp.payload["disposition"] == "declined"
    assert api.json()["reason"] == mcp.payload["reason"] == "nothing_to_dispatch"


def test_row_a_dispatched_turn_yields_the_same_verdict_on_both() -> None:
    surface = surface_under_test()
    client = TestClient(surface.app)
    thread_id = _thread_on_both(surface)

    api = client.post(
        f"/threads/{thread_id}/turns",
        json={"message": "plan it", "agent_definition_id": "planner"},
        headers=surface.bearer(),
    )
    mcp = surface.mcp.call(
        "send_turn",
        {"thread_id": thread_id, "message": "plan it", "agent_definition_id": "planner"},
        subject=surface.subject(),
    )

    assert api.status_code == mcp.status == 200
    assert api.json()["disposition"] == mcp.payload["disposition"] == "dispatched"
    assert api.json()["run_id"] and mcp.payload["run_id"]


def test_row_an_oversized_message_is_refused_identically() -> None:
    """The pre-acceptance refusal, which is the one most likely to live on one surface.

    The API bounds it in its request model; MCP bounds it in core. Both must answer the
    same way, or the size limit is a suggestion on whichever surface forgot.
    """
    surface = surface_under_test()
    client = TestClient(surface.app)
    thread_id = _thread_on_both(surface)
    oversized = "x" * 9000

    api = client.post(
        f"/threads/{thread_id}/turns",
        json={"message": oversized},
        headers=surface.bearer(),
    )
    mcp = surface.mcp.call(
        "send_turn",
        {"thread_id": thread_id, "message": oversized},
        subject=surface.subject(),
    )

    assert api.status_code == mcp.status, (
        f"transports disagree on an oversized message: API {api.status_code}, MCP {mcp.status}"
    )
    assert api.status_code >= 400, "an oversized message was accepted"


def test_row_deleting_a_thread_yields_the_same_verdict() -> None:
    surface = surface_under_test()
    client = TestClient(surface.app)

    api_thread = _thread_on_both(surface)
    api = client.delete(f"/threads/{api_thread}", headers=surface.bearer())

    mcp_thread = _thread_on_both(surface)
    mcp = surface.mcp.call("delete_thread", {"thread_id": mcp_thread}, subject=surface.subject())

    assert api.status_code == mcp.status == 204


def test_row_listing_threads_agrees_across_transports() -> None:
    """Same store, same subject: the two listings must name the same threads."""
    surface = surface_under_test()
    client = TestClient(surface.app)
    for _ in range(3):
        _thread_on_both(surface)

    api = client.get("/threads", headers=surface.bearer())
    mcp = surface.mcp.call("list_threads", {}, subject=surface.subject())

    assert api.status_code == mcp.status == 200
    assert [t["thread_id"] for t in api.json()["threads"]] == [
        t["thread_id"] for t in mcp.payload["threads"]
    ]
