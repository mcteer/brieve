# SPDX-License-Identifier: Apache-2.0
"""CONFORMANCE — an unqualified model is unreachable, counted at the provider.

**This file exists because 024's contract asserted this and nothing performed it.** That contract
states *"An unqualified cell refuses before any provider call"*, backed by FR-009 and SC-006, and
between 024's merge and 026's it was true of nothing: no module on the answering path referenced
the Qualified Model Matrix, and the matrix record held no `ask` cell for any pack.

**Counted at the provider, not read off the response.** A refusal that returns the right status
while having already called the model would satisfy any response-level check and violate the
requirement. "Unreachable, not merely unused" is only visible in the provider's own call count —
so that is what these rows assert.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from core.answering.corpus import Corpus
from core.authority.ask_binding import AskAuthority
from tests.harness.api_fixtures import (
    available_credential,
    qualified_ask_authority,
    surface_under_test,
)

GUIDANCE_QUESTION = "How does an AI agent obtain an identity with Vault?"
ESTATE_QUESTION = "Which runs were denied last night?"


class CountingProvider:
    """Answers whatever it is asked, and remembers that it was asked.

    The count is the assertion. Everything else about this double is incidental — it answers
    plausibly only so that a failure to refuse produces a *passing-looking* answer, which is
    exactly the shape the gap took.
    """

    def __init__(self) -> None:
        self.calls = 0

    def answer(self, question: str, material: Any) -> list[dict[str, Any]]:
        self.calls += 1
        if isinstance(material, Corpus):
            return [{"statement": "From the corpus.", "citations": []}]
        return [
            {
                "statement": "From the records.",
                "references": [{"entry_hash": r.entry_hash} for r in material[:1]],
            }
        ]


def test_a_provider_with_no_qualified_cell_is_never_called() -> None:
    """SC-001, and the row 024's contract asserted for two features without having.

    **This row was a strict xfail until the wiring landed** (T001 → T015): it failed because the
    provider WAS called, which is what made the gap a measurement rather than a claim. The marker
    came off; the row stays, and it is now SC-009's tripwire — remove the resolution step and it
    counts a call again.

    No authority is arranged: no binding record, no matrix cells. Under FR-001 the platform must
    refuse before the provider is contacted, so the call count must be zero — on both surfaces,
    for both sources.
    """
    provider = CountingProvider()
    surface = surface_under_test(ask_provider=provider, ask_model="anthropic/claude-opus@5")
    client = TestClient(surface.app)

    for question in (GUIDANCE_QUESTION, ESTATE_QUESTION):
        client.post("/ask", json={"question": question}, headers=surface.bearer())
        surface.mcp.call("ask", {"question": question}, subject=surface.subject())

    assert provider.calls == 0, (
        f"the provider was called {provider.calls} times with no qualified cell — an unqualified "
        f"model must be UNREACHABLE, not merely unused (FR-001, SC-001)"
    )


MODEL = "anthropic/claude-opus@5"


#: A judge for these rows to bind, so the 043 gate is satisfied and these rows keep asserting
#: what they are about. **A different model from `MODEL`**, per ADR-0067 — a self-judging
#: binding would pass here and be exactly the shape that record forbids.
RELEVANCE_MODEL = "anthropic/claude-sonnet@5"


def _authority(binding: dict[str, Any], matrix: dict[str, Any]) -> AskAuthority:
    """Bind the sources these rows are about, plus a relevance judge they are not.

    043 made a relevance judge a precondition of answering, so a binding record without one
    refuses `relevance_unbound` and every row here would 403 for a reason none of them is
    testing. The judge is added to the record and the matrix rather than to each row.
    """
    binding = {**binding}
    binding.setdefault("relevance_cell", f"vault:{RELEVANCE_MODEL}:judge")
    matrix = {
        **matrix,
        "cells": [
            *matrix.get("cells", []),
            {
                "pack": "vault",
                "model": RELEVANCE_MODEL,
                "role": "judge",
                "qualified_by": "fixture",
                "judge": "seed",
                "withdrawn": False,
            },
        ],
    }
    return AskAuthority(read_binding=lambda: binding, read_matrix=lambda: matrix)


def _cells(*refs: str, **kw: Any) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "cells": [
            {
                "pack": r.split(":")[0],
                "model": r.split(":")[1],
                "role": kw.get("role", "ask"),
                "qualified_by": "fixture",
                "judge": "seed",
                "withdrawn": kw.get("withdrawn", False),
            }
            for r in refs
        ],
    }


def _asks(surface: Any) -> list[Any]:
    return [e for e in surface.audit.all_entries() if str(e.event_type) == "ask_answered"]


def test_the_fixture_default_is_refusal_not_qualification() -> None:
    """SC-003b, and it is the tripwire for the trap this feature exists to avoid.

    A harness that auto-qualified whatever provider a test injected would rebuild
    "configured = qualified" *inside the test suite*, and every refusal row would then be
    testing an override rather than the behaviour. The default must be refusal.
    """
    provider = CountingProvider()
    surface = surface_under_test(ask_provider=provider, ask_model=MODEL)

    response = TestClient(surface.app).post(
        "/ask", json={"question": GUIDANCE_QUESTION}, headers=surface.bearer()
    )

    assert response.status_code == 403
    assert provider.calls == 0
    assert [a.payload["disposition"] for a in _asks(surface)] == ["unbound"]


def test_a_withdrawn_cell_refuses_and_calls_nothing() -> None:
    """SC-002 through the wired surface. A withdrawn cell is not a qualified one."""
    provider = CountingProvider()
    surface = surface_under_test(
        ask_provider=provider,
        ask_model=MODEL,
        ask_authority=_authority(
            {"schema_version": 1, "guidance_cell": f"vault:{MODEL}:ask"},
            _cells(f"vault:{MODEL}:ask", withdrawn=True),
        ),
    )

    response = TestClient(surface.app).post(
        "/ask", json={"question": GUIDANCE_QUESTION}, headers=surface.bearer()
    )

    assert response.status_code == 403
    assert provider.calls == 0
    assert _asks(surface)[0].payload["disposition"] == "unqualified_cell"


def test_a_cell_qualified_for_another_role_authorises_nothing() -> None:
    """SC-003. Roles exist so one green cell does not license everything.

    The binding names `...:ask` — it must, or parse refuses — while the matrix qualifies that
    pack and model only for `plan`. Nothing in the reference string shows it; only resolution does.
    """
    provider = CountingProvider()
    surface = surface_under_test(
        ask_provider=provider,
        ask_model=MODEL,
        ask_authority=_authority(
            {"schema_version": 1, "guidance_cell": f"vault:{MODEL}:ask"},
            _cells(f"vault:{MODEL}:ask", role="plan"),
        ),
    )

    TestClient(surface.app).post(
        "/ask", json={"question": GUIDANCE_QUESTION}, headers=surface.bearer()
    )

    assert provider.calls == 0
    assert _asks(surface)[0].payload["disposition"] == "unqualified_cell"


def test_an_unreadable_fabric_refuses_distinguishably_from_an_unbound_one() -> None:
    """SC-004. An outage is not a governance state, and the trail must not conflate them.

    Both refuse and both call nothing; what differs is where they send an operator — one to
    author a binding, the other to the outage.
    """

    def _down() -> dict[str, Any]:
        raise ConnectionError("vault is unreachable")

    broken = surface_under_test(
        ask_provider=CountingProvider(),
        ask_model=MODEL,
        ask_authority=AskAuthority(read_binding=_down, read_matrix=lambda: _cells()),
    )
    unbound = surface_under_test(
        ask_provider=CountingProvider(),
        ask_model=MODEL,
        ask_authority=_authority({"schema_version": 1}, _cells()),
    )

    for surface in (broken, unbound):
        TestClient(surface.app).post(
            "/ask", json={"question": GUIDANCE_QUESTION}, headers=surface.bearer()
        )

    assert _asks(broken)[0].payload["disposition"] == "matrix_unreadable"
    assert _asks(unbound)[0].payload["disposition"] == "unbound"


def test_a_binding_for_one_source_does_not_license_the_other() -> None:
    """SC-003a. Qualifying a model to summarise records has not qualified it to cite docs."""
    provider = CountingProvider()
    surface = surface_under_test(
        ask_provider=provider,
        ask_model=MODEL,
        ask_authority=_authority(
            {"schema_version": 1, "guidance_cell": f"vault:{MODEL}:ask"},
            _cells(f"vault:{MODEL}:ask"),
        ),
        # Guidance is bound and must ANSWER here, so it needs the credential too — governance
        # passing is not authority to call a vendor (027).
        credential_source=available_credential(),
    )
    client = TestClient(surface.app)

    guidance = client.post("/ask", json={"question": GUIDANCE_QUESTION}, headers=surface.bearer())
    estate = client.post("/ask", json={"question": ESTATE_QUESTION}, headers=surface.bearer())

    assert guidance.status_code == 200, "the bound source must still answer"
    assert estate.status_code == 403
    assert [a.payload["disposition"] for a in _asks(surface)][-1] == "unbound"


def test_an_answered_ask_records_the_cell_that_authorised_it() -> None:
    """SC-005. The `model` field says which model answered; only this says it was permitted."""
    surface = surface_under_test(
        ask_provider=CountingProvider(),
        ask_model=MODEL,
        ask_authority=qualified_ask_authority(model=MODEL),
    )

    TestClient(surface.app).post(
        "/ask", json={"question": GUIDANCE_QUESTION}, headers=surface.bearer()
    )

    payload = _asks(surface)[0].payload
    assert payload["cell"] == f"vault:{MODEL}:ask"
    assert payload["bound_cell"] == payload["cell"]
    assert payload["cell_disposition"] == "pinned"


def test_governance_refuses_before_availability_when_both_are_absent() -> None:
    """The precedence rule, where it is observable.

    No authority AND no provider: the ask refuses `unbound`, not `provider_unavailable`. "Nobody
    decided which model may answer" is the answer an operator needs before "nothing is wired" —
    the reverse order sends them to configure a provider they are not yet permitted to use.
    """
    surface = surface_under_test()

    response = TestClient(surface.app).post(
        "/ask", json={"question": GUIDANCE_QUESTION}, headers=surface.bearer()
    )

    assert response.status_code == 403
    assert _asks(surface)[0].payload["disposition"] == "unbound"


# --------------------------------------------------------------- US2: substitution


ALTERNATE = "anthropic/claude-sonnet@5"


def test_an_unavailable_pinned_cell_falls_back_and_the_record_says_so() -> None:
    """SC-006, FR-006 — one record carries the pinned cell, the used cell, and the reason.

    No second event and no fabricated run id: `MATRIX_FALLBACK`'s payload assumes a run, and an
    ask has none. An ask consults exactly one model, so which cell authorised it is an attribute
    of the ask.
    """
    surface = surface_under_test(
        # The provider is constructed for the ALTERNATE model — so that is what `available` holds.
        ask_provider=CountingProvider(),
        ask_model=ALTERNATE,
        ask_authority=_authority(
            {"schema_version": 1, "guidance_cell": f"vault:{MODEL}:ask"},
            _cells(f"vault:{MODEL}:ask", f"vault:{ALTERNATE}:ask"),
        ),
        # The fallback must ANSWER for this row to observe the fallback record, so the credential
        # is arranged too — governance passing is not authority to call a vendor (027).
        credential_source=available_credential(),
    )

    response = TestClient(surface.app).post(
        "/ask", json={"question": GUIDANCE_QUESTION}, headers=surface.bearer()
    )

    assert response.status_code == 200
    payload = _asks(surface)[0].payload
    assert payload["bound_cell"] == f"vault:{MODEL}:ask"
    assert payload["cell"] == f"vault:{ALTERNATE}:ask"
    assert payload["cell_disposition"].startswith("fallback:")


def test_no_qualified_alternative_refuses_rather_than_reaching_further() -> None:
    """FR-007. There is no path from unavailability to an unqualified model."""
    provider = CountingProvider()
    surface = surface_under_test(
        ask_provider=provider,
        ask_model=ALTERNATE,
        ask_authority=_authority(
            # Only the pinned cell is qualified, and its model is not the one configured.
            {"schema_version": 1, "guidance_cell": f"vault:{MODEL}:ask"},
            _cells(f"vault:{MODEL}:ask"),
        ),
    )

    response = TestClient(surface.app).post(
        "/ask", json={"question": GUIDANCE_QUESTION}, headers=surface.bearer()
    )

    assert response.status_code == 403
    assert provider.calls == 0


def test_fallback_never_selects_a_withdrawn_cell() -> None:
    """The no-third-branch property, exercised for asks.

    An available alternative that has been withdrawn is not a candidate — otherwise "withdrawn"
    would mean "unpinnable" rather than "not qualified".
    """
    surface = surface_under_test(
        ask_provider=CountingProvider(),
        ask_model=ALTERNATE,
        ask_authority=_authority(
            {"schema_version": 1, "guidance_cell": f"vault:{MODEL}:ask"},
            _cells(f"vault:{MODEL}:ask", f"vault:{ALTERNATE}:ask", withdrawn=True),
        ),
    )

    response = TestClient(surface.app).post(
        "/ask", json={"question": GUIDANCE_QUESTION}, headers=surface.bearer()
    )
    assert response.status_code == 403


def test_the_used_cells_model_is_the_model_the_provider_was_built_for() -> None:
    """Analysis U2 — record/actual agreement, asserted rather than assumed.

    `available` is exactly the injected provider's model. Anything wider would let fallback select
    a cell for a model this provider cannot call, and the record would then name an authorisation
    for a model that never ran — on an attestation-relevant record, the worst available outcome.
    """
    surface = surface_under_test(
        ask_provider=CountingProvider(),
        ask_model=ALTERNATE,
        ask_authority=_authority(
            {"schema_version": 1, "guidance_cell": f"vault:{MODEL}:ask"},
            _cells(f"vault:{MODEL}:ask", f"vault:{ALTERNATE}:ask"),
        ),
    )

    TestClient(surface.app).post(
        "/ask", json={"question": GUIDANCE_QUESTION}, headers=surface.bearer()
    )

    payload = _asks(surface)[0].payload
    # The cell's model component, compared against what the surface was configured with.
    assert payload["cell"].split(":")[1] == ALTERNATE


def test_a_substitution_needs_no_second_event_and_names_no_run() -> None:
    """T019 — the investigator walk, in one record.

    The whole provenance of a substituted answer is on the ask record: what was asked for, what
    was used, and why. No `matrix_fallback` entry, and no `run_id` anywhere in the payload.
    """
    surface = surface_under_test(
        ask_provider=CountingProvider(),
        ask_model=ALTERNATE,
        ask_authority=_authority(
            {"schema_version": 1, "guidance_cell": f"vault:{MODEL}:ask"},
            _cells(f"vault:{MODEL}:ask", f"vault:{ALTERNATE}:ask"),
        ),
    )

    TestClient(surface.app).post(
        "/ask", json={"question": GUIDANCE_QUESTION}, headers=surface.bearer()
    )

    kinds = {str(e.event_type) for e in surface.audit.all_entries()}
    assert "matrix_fallback" not in kinds
    payload = _asks(surface)[0].payload
    assert "run_id" not in payload
    assert {"cell", "bound_cell", "cell_disposition"} <= set(payload)
