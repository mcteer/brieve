# SPDX-License-Identifier: Apache-2.0
"""C15–C17 — the judge can be turned off, and the platform says so (044, US3).

**Disclose, never suppress.** Three products were available when an administrator disables the
relevance gate: answer silently (which reintroduces gap 0g by configuration), decline (which
means turning off a check turns off answering), or answer with the absence disclosed. The third
is 033's shape — *a disclosure appearing only past a threshold trains readers that silence
means complete* — and it is settled here as the template for every toggle the console grows.

**C16 asserts an absence.** No `MODEL_GATE` is written when the gate is off, because an event
for a gate that did not run is the vacuous assertion 040 caught in M9: a payload key read
behind an `if` that was never true, green for the wrong reason.

**C17 drives both states in one process against one surface.** A row that restarted between
them would prove the record was read at startup, which is the opposite of FR-013.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from core.answering.answer import RELEVANCE_DISABLED
from core.authority.ask_binding import AskAuthority
from tests.harness.api_fixtures import available_credential, surface_under_test
from tests.harness.fixture_relevance import FixtureRelevanceJudge

MODEL = "anthropic/claude-opus@5"
JUDGE = "fixture/relevance-judge@1"
QUESTION = "How does an AI agent obtain an identity with Vault?"

REAL_PATH = "/validated-designs/vault-operating-guides-adoption/initial-configuration"
REAL_ANCHOR = "enabling-an-audit-device"


class _Provider:
    """One claim whose citation resolves, so the gate is actually reached."""

    def answer(self, question: str, material: Any, context: str = "") -> list[dict[str, Any]]:
        return [
            {
                "statement": "Vault's initial configuration covers enabling an audit device.",
                "citations": [{"path": REAL_PATH, "anchor": REAL_ANCHOR}],
            }
        ]


class _MutableBinding:
    """A binding record an administrator can flip mid-process.

    This is the whole of FR-013's mechanism: the surface reads the binding per ask, so a
    change is in force for the next question with nothing restarted and no new fabric read.
    """

    def __init__(self) -> None:
        self.enabled = True

    def record(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "guidance_cell": f"vault:{MODEL}:ask",
            "estate_cell": f"terraform:{MODEL}:ask",
            "relevance_cell": f"vault:{JUDGE}:judge",
            "relevance_enabled": self.enabled,
        }

    def matrix(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "cells": [
                {
                    "pack": p,
                    "model": MODEL,
                    "role": "ask",
                    "qualified_by": "fixture",
                    "judge": "seed",
                }
                for p in ("vault", "terraform")
            ]
            + [
                {
                    "pack": "vault",
                    "model": JUDGE,
                    "role": "judge",
                    "qualified_by": "fixture",
                    "judge": "seed",
                }
            ],
        }


def _surface(binding: _MutableBinding, judge: FixtureRelevanceJudge) -> Any:
    return surface_under_test(
        ask_provider=_Provider(),
        ask_model=MODEL,
        ask_authority=AskAuthority(read_binding=binding.record, read_matrix=binding.matrix),
        credential_source=available_credential(),
        relevance_judges=lambda cell: judge,
    )


def _ask(surface: Any) -> Any:
    return TestClient(surface.app).post(
        "/ask", json={"question": QUESTION}, headers=surface.bearer()
    )


def test_row_c15_a_disabled_gate_still_answers_and_discloses() -> None:
    """C15 — FR-011, and the disclosure must reach the RESPONSE, not only the record.

    A disclosure that lives only in the audit trail is one the person reading the answer never
    sees, which is the reassurance this whole decision exists to avoid.
    """
    binding = _MutableBinding()
    binding.enabled = False
    judge = FixtureRelevanceJudge()
    surface = _surface(binding, judge)

    response = _ask(surface)

    assert response.status_code == 200
    body = response.json()
    assert body["disposition"] == "answered", "disabling a check must not disable answering"
    assert body["relevance_note"] == RELEVANCE_DISABLED
    assert "administrator" in body["relevance_note"], (
        "the note names WHO decided; 'relevance was not checked' alone reads as a platform "
        "failure rather than as somebody's decision"
    )
    assert judge.calls == 0, "the judge was consulted for a gate that is switched off"


def test_row_c16_the_record_distinguishes_disabled_from_unreachable() -> None:
    """C16 — FR-012. Two causes, two destinations for whoever reads the trail.

    *Disabled by an administrator* sends a reader to a person; *the judge could not be
    reached* sends them to a vendor's status page. A single "no relevance" would send half of
    them to the wrong place.
    """
    binding = _MutableBinding()
    binding.enabled = False
    surface = _surface(binding, FixtureRelevanceJudge())

    _ask(surface)

    ask_records = [e for e in surface.audit.all_entries() if str(e.event_type) == "ask_answered"]
    assert ask_records[-1].payload["relevance_gate"] == "disabled_by_admin"


def test_row_c16_no_model_gate_is_written_for_a_gate_that_did_not_run() -> None:
    """C16's other half — 040's M9 shape avoided.

    A `MODEL_GATE` event for a gate that never ran would be an assertion about a judgement
    nobody made. Worse, a row counting gate events would then pass whether or not the gate
    was running, which is the vacuous-assertion trap in its purest form.
    """
    binding = _MutableBinding()
    binding.enabled = False
    surface = _surface(binding, FixtureRelevanceJudge())

    _ask(surface)

    assert not [e for e in surface.audit.all_entries() if str(e.event_type) == "model_gate"]


def test_row_c17_the_toggle_takes_effect_without_a_restart() -> None:
    """C17 — FR-013/SC-011, driven in ONE process against ONE surface.

    Both states, one client, no reassembly. A row that rebuilt the surface between them would
    prove the record is read at startup — the opposite of what this asserts.
    """
    binding = _MutableBinding()
    judge = FixtureRelevanceJudge()
    surface = _surface(binding, judge)
    client = TestClient(surface.app)

    def _ask_once() -> Any:
        return client.post("/ask", json={"question": QUESTION}, headers=surface.bearer()).json()

    # Enabled: the gate runs.
    first = _ask_once()
    assert first["relevance_note"] != RELEVANCE_DISABLED
    assert judge.calls == 1

    # An administrator flips it. Nothing is restarted.
    binding.enabled = False
    second = _ask_once()
    assert second["relevance_note"] == RELEVANCE_DISABLED
    assert judge.calls == 1, "the judge ran again for a disabled gate"

    # And back.
    binding.enabled = True
    third = _ask_once()
    assert third["relevance_note"] != RELEVANCE_DISABLED
    assert judge.calls == 2


def test_an_enabled_gate_is_unchanged_from_043() -> None:
    """The regression guard. 044 must not alter the answering path when the gate is on."""
    binding = _MutableBinding()
    surface = _surface(binding, FixtureRelevanceJudge())

    _ask(surface)

    gates = [e for e in surface.audit.all_entries() if str(e.event_type) == "model_gate"]
    assert len(gates) == 1, "one MODEL_GATE per answered ask, exactly as 043 wrote it"
    ask_records = [e for e in surface.audit.all_entries() if str(e.event_type) == "ask_answered"]
    assert ask_records[-1].payload["relevance_gate"] == "checked"


def test_both_transports_honour_the_toggle() -> None:
    """ADR-0033 is a statement about a DEPLOYMENT, not about one route.

    A gate switched off on the API and running on MCP would make an administrator's decision
    depend on which door was used — and 043 shipped exactly that asymmetry once, with only
    the parity row catching it.
    """
    binding = _MutableBinding()
    binding.enabled = False
    judge = FixtureRelevanceJudge()
    surface = _surface(binding, judge)

    api = _ask(surface).json()
    mcp = surface.mcp.call("ask", {"question": QUESTION}, subject=surface.subject())

    assert api["relevance_note"] == RELEVANCE_DISABLED
    assert mcp.payload["relevance_note"] == RELEVANCE_DISABLED
    assert judge.calls == 0
