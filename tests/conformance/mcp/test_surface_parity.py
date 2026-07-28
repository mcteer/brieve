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
        json={"agent_definition_id": "definition-a", "requested_tools": ["echo"]},
        headers=surface.bearer(),
    )
    mcp = surface.mcp.call(
        "start_run",
        {"agent_definition_id": "definition-a", "requested_tools": ["echo"]},
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

    api_body = {"agent_definition_id": "definition-a", "requested_tools": ["echo"]}
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
        {"agent_definition_id": "definition-a", "requested_tools": ["echo"]},
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
        {"agent_definition_id": "definition-a", "requested_tools": ["echo"]},
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
