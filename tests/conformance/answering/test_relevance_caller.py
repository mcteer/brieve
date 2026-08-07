# SPDX-License-Identifier: Apache-2.0
"""R6, R8 — facts about the SURFACE, not about the gate function (043, US1).

**Why these are not in `test_relevance_gate.py`.** That file drives `answer_question`, which
knows nothing about bindings and takes its judge as a parameter. Both rows here are properties
of the thing that *supplies* the judge: whether it refuses when nobody bound one, and whether it
supplies one at all.

**R8 is the row that matters most in this feature.** `relevance` is optional on
`answer_question` — it has to be, or every recorded eval scorer would need editing and this
feature promised not to touch those suites. An optional gate is a gate something can stop
calling, which is precisely the defect 041 spent a feature closing: 038 built an authoring tier
whose handlers were correct and whose registration had no caller, and every row stayed green.
So this row drives the production route and fails if the surface stops passing a judge, while
every gate row keeps passing.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from core.authority.ask_binding import AskAuthority
from tests.harness.api_fixtures import (
    available_credential,
    qualified_ask_authority,
    surface_under_test,
)
from tests.harness.fixture_relevance import FixtureRelevanceJudge

QUESTION = "How does an AI agent obtain an identity with Vault?"
MODEL = "anthropic/claude-opus@5"

#: A real path and anchor in the pinned corpus. The claim must SURVIVE citation resolution or
#: the gate is never reached (FR-018) and every count below would be zero for the wrong reason.
REAL_PATH = "/validated-designs/vault-operating-guides-adoption/initial-configuration"
REAL_ANCHOR = "enabling-an-audit-device"


class _SurvivingProvider:
    """Answers with one claim whose citation resolves against the real pin.

    `CountingProvider` in the sibling file returns claims with no citations, which is right for
    what it asserts and useless here: nothing survives, so the gate is never invoked and a
    judge-call count of zero would prove nothing.
    """

    def __init__(self) -> None:
        self.calls = 0

    def answer(self, question: str, material: Any, context: str = "") -> list[dict[str, Any]]:
        self.calls += 1
        return [
            {
                "statement": "Vault's initial configuration covers enabling an audit device.",
                "citations": [{"path": REAL_PATH, "anchor": REAL_ANCHOR}],
            }
        ]


def _provider() -> Any:
    return _SurvivingProvider()


def test_row_r6_an_unbound_relevance_cell_refuses_before_availability() -> None:
    """R6 — 026's rule applied to a second decision (FR-017).

    A binding that names an answering cell and no relevance cell is a real state: an operator
    configured half of it. The refusal must say *that*, not that a judge could not be reached —
    those send a reader to the trust fabric and to a vendor's status page respectively.
    """
    binding = {
        "schema_version": 1,
        "guidance_cell": f"vault:{MODEL}:ask",
        "estate_cell": f"terraform:{MODEL}:ask",
        # relevance_cell deliberately absent
    }
    matrix = {
        "schema_version": 1,
        "cells": [
            {
                "pack": pack,
                "model": MODEL,
                "role": "ask",
                "qualified_by": "fixture",
                "judge": "seed",
            }
            for pack in ("vault", "terraform")
        ],
    }
    surface = surface_under_test(
        ask_provider=_provider(),
        ask_model=MODEL,
        ask_authority=AskAuthority(read_binding=lambda: binding, read_matrix=lambda: matrix),
        credential_source=available_credential(),
    )
    client = TestClient(surface.app)

    response = client.post("/ask", json={"question": QUESTION}, headers=surface.bearer())

    assert response.status_code == 403
    assert "relevance" in response.text.lower(), (
        "the refusal must name the decision nobody made, not a generic denial"
    )
    refusals = [
        entry
        for entry in surface.audit.all_entries()
        if entry.payload.get("disposition") == "relevance_unbound"
    ]
    assert refusals, "someone asked, and a boundary a caller can probe without trace is not one"


def test_row_r6_the_refusal_is_recorded_before_any_provider_call() -> None:
    """Governance precedes availability, and the provider proves it."""
    provider = _provider()
    binding = {"schema_version": 1, "guidance_cell": f"vault:{MODEL}:ask"}
    matrix = {
        "schema_version": 1,
        "cells": [
            {
                "pack": "vault",
                "model": MODEL,
                "role": "ask",
                "qualified_by": "fixture",
                "judge": "seed",
            }
        ],
    }
    surface = surface_under_test(
        ask_provider=provider,
        ask_model=MODEL,
        ask_authority=AskAuthority(read_binding=lambda: binding, read_matrix=lambda: matrix),
        credential_source=available_credential(),
    )

    TestClient(surface.app).post("/ask", json={"question": QUESTION}, headers=surface.bearer())

    assert provider.calls == 0, (
        "an ask refused for want of a relevance judge must not reach the answering model — "
        "governance precedes availability, and a provider call is availability"
    )


def test_row_r8_the_production_surface_supplies_a_judge() -> None:
    """R8 — the row this feature's honesty rests on (`verify-the-production-caller`).

    Counted rather than inferred: the judge the surface builds is asked exactly once per
    answered ask. If `ask.py` stops passing one, this fails while every row in
    `test_relevance_gate.py` stays green — which is the asymmetry that made 038's gap invisible
    for a whole feature.
    """
    judge = FixtureRelevanceJudge()
    surface = surface_under_test(
        ask_provider=_provider(),
        ask_model=MODEL,
        ask_authority=qualified_ask_authority(model=MODEL),
        credential_source=available_credential(),
        relevance_judges=lambda cell: judge,
    )

    response = TestClient(surface.app).post(
        "/ask", json={"question": QUESTION}, headers=surface.bearer()
    )

    assert response.status_code == 200
    assert judge.calls == 1, (
        "the production route must construct and pass a relevance judge; a gate nothing calls "
        "is the shape 041 spent a feature closing"
    )


def test_row_r8_both_transports_supply_a_judge() -> None:
    """Parity is a property of the trail, and the gate is now part of it (ADR-0033).

    Wiring one transport is how this feature first broke parity: the API emitted `model_gate`
    and MCP did not. One row, both surfaces, so a future half-wiring fails here.
    """
    judge = FixtureRelevanceJudge()
    surface = surface_under_test(
        ask_provider=_provider(),
        ask_model=MODEL,
        ask_authority=qualified_ask_authority(model=MODEL),
        credential_source=available_credential(),
        relevance_judges=lambda cell: judge,
    )

    TestClient(surface.app).post("/ask", json={"question": QUESTION}, headers=surface.bearer())
    surface.mcp.call("ask", {"question": QUESTION}, subject=surface.subject())

    assert judge.calls == 2, f"both transports must gate; the judge saw {judge.calls} of 2 asks"
    gates = [
        entry for entry in surface.audit.all_entries() if str(entry.event_type) == "model_gate"
    ]
    assert len(gates) == 2, "one MODEL_GATE per answered ask, on both surfaces"
