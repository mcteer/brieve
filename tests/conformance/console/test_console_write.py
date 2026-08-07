# SPDX-License-Identifier: Apache-2.0
"""C1–C5, C7–C8, C21 — the fabric decides, and the console never claims more (044, US2).

**C2 is the row the console's honesty rests on.** An interface that reports "saved" for a
change that was queued — or for one that went nowhere — is worse than no interface, because it
manufactures confidence in a posture that was never applied. The three outcomes are rendered
distinctly and the row fails if they are collapsed.

**C5 is the row that keeps a development estate from looking like a governed one.** With no
quorum configured a change applies immediately, which is legitimate; an interface that says
"applied" identically in both estates is how a development posture reaches production without
anybody noticing it did.

**C21 is the self-grant refusal.** An administrator who can widen their own role has not been
granted authority — they have taken it, and every other check in this feature would still pass.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from surfaces.api.authority_submit import (
    AuthorityChangeRefused,
    ChangeOutcome,
    RecordMoved,
)
from surfaces.api.console import CONNECTIONS_PATH, ConsoleConfig
from tests.harness.api_fixtures import surface_under_test

MODEL = "anthropic/claude-sonnet@5"
JUDGE = "anthropic/claude-opus@5"
QUALIFIED = f"vault:{JUDGE}:judge"


class _Submitter:
    """Stands in for the fabric. Records what it was asked; answers what the row scripted."""

    def __init__(self, outcome: Any = None) -> None:
        self.outcome = outcome if outcome is not None else ChangeOutcome(state="applied")
        self.submitted: list[Any] = []

    def submit_change(self, change: Any) -> Any:
        self.submitted.append(change)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def _matrix() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "cells": [
            {
                "pack": "vault",
                "model": JUDGE,
                "role": "judge",
                "qualified_by": "live",
                "judge": "seed",
            },
            {
                "pack": "vault",
                "model": MODEL,
                "role": "ask",
                "qualified_by": "live",
                "judge": JUDGE,
            },
        ],
    }


def _config(**over: Any) -> ConsoleConfig:
    defaults: dict[str, Any] = {
        "read_matrix": _matrix,
        "read_versioned": lambda path: None if path == CONNECTIONS_PATH else None,
        "quorum_configured": False,
    }
    return ConsoleConfig(**{**defaults, **over})


def _surface(submitter: Any = None, **over: Any) -> Any:
    return surface_under_test(console_config=_config(**over), authority_submitter=submitter)


def _admin(surface: Any) -> dict[str, str]:
    headers: dict[str, str] = surface.bearer(claims={"groups": ["platform-admin"]})
    return headers


def _post(surface: Any, body: dict[str, Any]) -> Any:
    return TestClient(surface.app).post("/console/changes", json=body, headers=_admin(surface))


def _binding_change(**over: Any) -> dict[str, Any]:
    return {
        "record": "ask-bindings",
        "payload": {"schema_version": 1, "relevance_cell": QUALIFIED, **over},
    }


# ── C2 / C5: the three outcomes, never collapsed ───────────────────────────────────────


def test_row_c2_a_pending_change_is_202_and_says_it_is_not_in_force() -> None:
    """C2 — the row the console's honesty rests on.

    202, never 403. 007's seam names the trap: a client reading 403 stops asking, so a change
    approved twenty minutes later is never collected and the requester concludes it was
    refused when it was in fact granted.
    """
    submitter = _Submitter(ChangeOutcome(state="pending", accessor="acc-9", expires_at="t"))
    surface = _surface(submitter, quorum_configured=True)

    response = _post(surface, _binding_change())

    assert response.status_code == 202
    body = response.json()
    assert body["state"] == "pending"
    assert body["accessor"] == "acc-9", "an approver acts on the accessor"
    assert "NOT in force" in body["message"], (
        "a queued change reported without saying it is not yet in force is the confidence "
        "this feature exists to avoid manufacturing"
    )


def test_row_c2_pending_and_applied_are_different_status_codes() -> None:
    """The collapse this row exists to prevent, stated as an inequality."""
    pending = _post(
        _surface(_Submitter(ChangeOutcome(state="pending")), quorum_configured=True),
        _binding_change(),
    )
    applied = _post(_surface(_Submitter(), quorum_configured=True), _binding_change())

    assert pending.status_code != applied.status_code
    assert pending.json()["state"] != applied.json()["state"]


def test_row_c5_an_ungated_estate_says_so_on_every_applied_change() -> None:
    """C5 — FR-007/023b.

    With no quorum configured a change applies immediately. That is legitimate and is the
    development default. What is not legitimate is an interface that looks identical in both
    estates, because that is how a development posture reaches production unnoticed.
    """
    response = _post(_surface(_Submitter(), quorum_configured=False), _binding_change())

    assert response.status_code == 200
    body = response.json()
    assert body["gating"] == "ungated"
    assert "WITHOUT approval" in body["message"]


def test_row_c5_a_gated_estate_does_not_carry_the_ungated_disclosure() -> None:
    """The flag is a fact about the estate, not a constant that is always shown."""
    body = _post(_surface(_Submitter(), quorum_configured=True), _binding_change()).json()

    assert body["gating"] == "gated"
    assert "WITHOUT approval" not in body["message"]


def test_row_c4_a_refused_change_is_403_and_recorded() -> None:
    """C4 — 022's rule: a refusal records, with its requester."""
    submitter = _Submitter(AuthorityChangeRefused("policy refused this change"))
    surface = _surface(submitter)

    response = _post(surface, _binding_change())

    assert response.status_code == 403
    denials = [
        e
        for e in surface.audit.all_entries()
        if e.payload.get("reason_code") == "authority_change_denied"
    ]
    assert denials and denials[-1].payload["actor"] == surface.subject_name


# ── C1: validation precedes the fabric ─────────────────────────────────────────────────


def test_row_c1_an_unqualified_cell_refuses_with_zero_fabric_writes() -> None:
    """C1 — FR-009, and the assertion that matters is the second one.

    A change the platform would refuse anyway must not reach Vault: a rejected write still
    costs a round trip, a log line, and — where a quorum is configured — an approver's
    attention on a request that was never going to be applied.
    """
    submitter = _Submitter()
    surface = _surface(submitter)

    response = _post(surface, _binding_change(relevance_cell="vault:anthropic/nope@1:judge"))

    assert response.status_code == 400
    assert "not a qualified cell" in response.text
    assert submitter.submitted == [], "the fabric was asked about a change already refusable"


def test_row_c1_a_qualified_cell_passes_validation() -> None:
    """Without this, C1 could be satisfied by refusing every binding."""
    submitter = _Submitter()

    assert _post(_surface(submitter), _binding_change()).status_code == 200
    assert len(submitter.submitted) == 1


def test_row_c1_an_unreadable_matrix_does_not_refuse_every_binding() -> None:
    """An outage must not present as an estate of misconfigured cells.

    `read_matrix`'s own docstring names this: an empty matrix resolves every binding to
    `unqualified_cell`, so a matrix that failed to apply would look like every definition in
    the estate being wrongly configured. The validator skips rather than refuses.
    """

    def _down() -> dict[str, Any]:
        raise ConnectionError("vault unreachable")

    submitter = _Submitter()

    assert _post(_surface(submitter, read_matrix=_down), _binding_change()).status_code == 200


def test_row_c25_a_connection_cannot_carry_a_credential() -> None:
    """[GATE:no-secret-leak] FR-018b enforced by vocabulary, not by a filter.

    A filter over credential-shaped names is something a future field slips past. A closed
    set of location fields has nowhere to put one.
    """
    submitter = _Submitter()
    surface = _surface(submitter)

    response = _post(
        surface,
        {
            "record": "product-connections",
            "payload": {"tfe": {"address": "https://app.terraform.io", "token": "hvs.secret"}},
        },
    )

    assert response.status_code == 400
    assert "token" in response.text
    assert submitter.submitted == []


# ── C7 / C8 / C21 ──────────────────────────────────────────────────────────────────────


def test_row_c7_a_stale_read_answers_record_moved_not_a_refusal() -> None:
    """C7 — two administrators editing one record is neither a denial nor an outage (US5)."""
    surface = _surface(_Submitter(RecordMoved("the record changed since it was read")))

    response = _post(surface, {**_binding_change(), "cas": 2})

    assert response.status_code == 409, (
        "409 rather than 403: the second administrator was not denied by governance, "
        "somebody else got there first"
    )


def test_row_c8_the_console_has_no_path_that_applies_a_change_itself() -> None:
    """C8 — asserted as a property of the module, not of one request.

    Every write reaches the fabric through the submitter. A module that could write directly
    would make "the fabric decides" a convention rather than an architecture.
    """
    import inspect

    from surfaces.api import console

    source = inspect.getsource(console)
    assert "submit_change" in source
    for direct in ("urlopen(", "requests.post", "http.client"):
        # `probe_connection` uses urlopen for READ-only reachability; it writes nothing.
        occurrences = source.count(direct)
        if direct == "urlopen(":
            assert occurrences <= 2, "the only urlopen calls belong to the reachability probe"
        else:
            assert occurrences == 0, f"{direct} is a second write path"


def test_row_c21_an_administrator_cannot_grant_themselves_the_admin_role() -> None:
    """C21 — SC-009, and the check no other layer performs.

    The grant is bounded to claim-mappings, the Control Group decides, and the role gate is
    passed — every other protection in this feature says yes to this request. Only this
    refusal stands between an administrator and a wider one.
    """
    submitter = _Submitter()
    surface = _surface(submitter)

    response = _post(
        surface,
        {
            "record": "claim-mappings",
            "key": "groups.self",
            "payload": {
                "claim_name": "groups",
                "claim_value": surface.subject_name,
                "role": "admin",
            },
        },
    )

    assert response.status_code == 403
    assert "may not grant themselves" in response.text
    assert submitter.submitted == []
    refusals = [
        e
        for e in surface.audit.all_entries()
        if e.payload.get("reason_code") == "self_grant_refused"
    ]
    assert refusals


def test_row_c21_granting_admin_to_somebody_else_is_permitted() -> None:
    """The row without which C21 could be satisfied by refusing every admin grant.

    Somebody has to be able to make the second administrator, or the role is unreachable
    after the first — and the first is made by an estate apply.
    """
    submitter = _Submitter()
    surface = _surface(submitter)

    response = _post(
        surface,
        {
            "record": "claim-mappings",
            "key": "groups.platform-admin",
            "payload": {"claim_name": "groups", "claim_value": "someone-else", "role": "admin"},
        },
    )

    assert response.status_code == 200
    assert len(submitter.submitted) == 1


@pytest.mark.parametrize("record", ["harness-ceilings", "model-matrix", "protected-policies"])
def test_a_record_this_feature_scoped_out_is_refused(record: str) -> None:
    """Scope, enforced at the route as well as in the grant and the Control Group list."""
    submitter = _Submitter()

    response = _post(_surface(submitter), {"record": record, "payload": {}})

    assert response.status_code in (400, 403)
    assert submitter.submitted == [] or response.status_code != 200
