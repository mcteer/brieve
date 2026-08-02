# SPDX-License-Identifier: Apache-2.0
"""CONFORMANCE — the platform obtains its authority to call a model, per task, or it refuses.

**This file exists because the answering capability was complete, gated, and unusable.** 024 built
it, 025 extended it, 026 governed it — and every ask through the served surface refused before
reaching a model, because putting a vendor credential inside a service was a constitutional
question nobody had answered. Three features recorded the deferral rather than resolving it.

**The three refusals are the design, and they are three different people's problems.** A cell the
matrix has not qualified sends someone to the matrix; a credential the store does not hold sends
them to whoever governs credentials; a vendor that will not answer sends them to the vendor. The
rows here assert that a reader of the trail can tell which, because collapsing any two of them
would send somebody to the wrong system during an incident.

**Counted at the provider and at the credential source, never read off the response.** A refusal
that returns the right status while having already called the vendor satisfies any response-level
check and violates the requirement. And a surface that fetched once and reused the key across asks
would satisfy every single-ask row while holding a credential for the life of the process — so the
credential source counts its reads too.
"""

from __future__ import annotations

import os
from typing import Any

import pytest
from fastapi.testclient import TestClient

from core.answering.answer import ProviderUnavailable
from core.answering.corpus import Corpus
from core.evals.scoring import EVAL_PROVIDER_KEY
from tests.harness.api_fixtures import (
    available_credential,
    qualified_ask_authority,
    surface_under_test,
)

GUIDANCE_QUESTION = "How does an AI agent obtain an identity with Vault?"
ESTATE_QUESTION = "Which runs were denied last night?"
MODEL = "anthropic/claude-opus@5"


class CountingProvider:
    """Answers plausibly, and remembers that it was asked.

    Plausibly on purpose: a failure to refuse then produces a *passing-looking* answer, which is
    the shape every gap in this area has taken.
    """

    def __init__(self) -> None:
        self.calls = 0
        self.secrets: list[str] = []

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


class RefusingProvider:
    """A vendor that will not answer — the third rung of the ladder."""

    def answer(self, question: str, material: Any) -> list[dict[str, Any]]:
        raise ProviderUnavailable("the vendor did not answer")


def _asks(surface: Any) -> list[Any]:
    return [e for e in surface.audit.all_entries() if str(e.event_type) == "ask_answered"]


def _qualified(**kwargs: Any) -> Any:
    """A surface whose governance PASSES, so what follows is about the credential alone."""
    kwargs.setdefault("ask_model", MODEL)
    kwargs.setdefault("ask_authority", qualified_ask_authority(model=MODEL))
    return surface_under_test(**kwargs)


# ------------------------------------------------------------------ T013: the headline


def test_a_qualified_cell_with_no_credential_refuses_and_calls_nothing() -> None:
    """SC-001's inverse, counted at the provider.

    Governance has passed — the matrix qualifies this cell and the binding names it — and the ask
    still refuses, because a qualified cell is not authority to call a vendor. Those are two
    different permissions held in two different places, and this row is what keeps them from
    collapsing into one.
    """
    provider = CountingProvider()
    surface = _qualified(ask_provider=provider, credential_source=None)

    response = TestClient(surface.app).post(
        "/ask", json={"question": GUIDANCE_QUESTION}, headers=surface.bearer()
    )

    assert response.status_code == 503
    assert provider.calls == 0, "the vendor was called without the platform holding authority to"
    record = _asks(surface)[0].payload
    assert record["disposition"] == "credential_unavailable"
    # Governance PASSED, and the record keeps saying so. Overwriting the resolution outcome with
    # the later failure would erase the fact that the cell was qualified — and an investigator
    # would then be unable to tell this from an unqualified ask.
    assert record["cell"] == f"vault:{MODEL}:ask"
    assert record["cell_disposition"] == "pinned"
    assert record["model_authority"] == ""


def test_a_credential_present_answers_and_the_record_carries_the_reference() -> None:
    provider = CountingProvider()
    surface = _qualified(ask_provider=provider, credential_source=available_credential())

    response = TestClient(surface.app).post(
        "/ask", json={"question": GUIDANCE_QUESTION}, headers=surface.bearer()
    )

    assert response.status_code == 200
    assert provider.calls == 1
    assert _asks(surface)[0].payload["model_authority"] == "vault:model-credentials/anthropic@v1"


def test_two_asks_are_two_fetches_and_no_surface_holds_a_key_between_them() -> None:
    """The property no single-ask row can see, and the whole posture in one assertion.

    A surface that fetched once at construction and reused the key would pass every other row in
    this file and hold a vendor credential for the life of the process — the standing credential
    Principle IV forbids, moved one layer up from the reader that refuses to cache.

    Asserted on **both surfaces**, because they build providers independently and a cache added to
    one would be invisible in the other's rows (ADR-0033).
    """
    credential = available_credential()
    surface = _qualified(ask_provider=CountingProvider(), credential_source=credential)
    client = TestClient(surface.app)

    client.post("/ask", json={"question": GUIDANCE_QUESTION}, headers=surface.bearer())
    client.post("/ask", json={"question": GUIDANCE_QUESTION}, headers=surface.bearer())
    surface.mcp.call("ask", {"question": GUIDANCE_QUESTION}, subject=surface.subject())

    assert len(credential.reads) == 3, (
        f"three asks produced {len(credential.reads)} credential reads; a surface is holding a "
        f"key across asks"
    )


# ------------------------------------------------------------------ T014: no env fallback


def test_the_production_path_never_falls_back_to_the_eval_lane_credential(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GATE:fail-closed — the row three features' silence would have needed.

    **The environment variable is deliberately SET.** A production path that fell back to
    `EVAL_PROVIDER_API_KEY` would work on the operator's laptop, work in every hermetic row that
    happens to have it set, and fail only in the enclave where no such variable exists — the most
    expensive place to discover it. Every other row in this file passes whether or not the fallback
    exists; this one is the only thing standing between the platform and that fix.

    If this row is ever seen passing with the variable *unset*, it is testing nothing.
    """
    monkeypatch.setenv(EVAL_PROVIDER_KEY, "not-a-real-key-and-must-never-be-reached")
    assert os.environ.get(EVAL_PROVIDER_KEY), "this row is vacuous without the variable set"

    provider = CountingProvider()
    surface = _qualified(ask_provider=provider, credential_source=None)

    response = TestClient(surface.app).post(
        "/ask", json={"question": GUIDANCE_QUESTION}, headers=surface.bearer()
    )

    assert response.status_code == 503
    assert provider.calls == 0
    assert _asks(surface)[0].payload["disposition"] == "credential_unavailable"


# ------------------------------------------------------------------ T015: three refusals


def test_the_three_failures_stay_distinguishable_in_the_trail() -> None:
    """SC-006. Three failures, three people, and the trail says which without guessing.

    The order is the design: the cell is checked before the credential, and the credential before
    the vendor. Reversing any pair sends an operator to configure something they are not yet
    permitted to use, or to chase a vendor outage that is really a missing credential.
    """
    unqualified = surface_under_test(
        ask_provider=CountingProvider(),
        ask_model=MODEL,
        credential_source=available_credential(),
    )
    no_credential = _qualified(ask_provider=CountingProvider(), credential_source=None)
    vendor_down = _qualified(
        ask_provider=RefusingProvider(), credential_source=available_credential()
    )

    for surface in (unqualified, no_credential, vendor_down):
        TestClient(surface.app).post(
            "/ask", json={"question": GUIDANCE_QUESTION}, headers=surface.bearer()
        )

    assert _asks(unqualified)[0].payload["disposition"] == "unbound"
    assert _asks(no_credential)[0].payload["disposition"] == "credential_unavailable"
    # The vendor rung records nothing new of its own — `answer_question` raises and the surface
    # answers 503 — and that asymmetry is worth naming rather than papering over: the first two
    # are the platform's own decisions and the third is somebody else's outage.
    assert _asks(vendor_down) == []


def test_governance_is_checked_before_the_credential_is_sought() -> None:
    """The order, where it is observable: an unqualified ask never touches the store.

    A platform that fetched first would go looking for authority to make a call it was never
    permitted to make — and an operator watching credential reads would see traffic for asks that
    governance had already decided against.
    """
    credential = available_credential()
    surface = surface_under_test(
        ask_provider=CountingProvider(), ask_model=MODEL, credential_source=credential
    )

    TestClient(surface.app).post(
        "/ask", json={"question": GUIDANCE_QUESTION}, headers=surface.bearer()
    )

    assert credential.reads == [], "the store was read for an ask governance had already refused"


# ------------------------------------------------------------------ T016: never persisted


def test_the_key_appears_in_no_record_and_in_no_response_body() -> None:
    """GATE:no-secret-leak — FR-008, at both places a value could escape.

    The trail carries a **reference**: where the credential lives and which rotation generation was
    in force. Not the key, and not a hash of it — a hash of a low-entropy-format secret is an
    oracle, and the platform's rule everywhere else is references only.

    The asker is present beside it (SC-004a): the platform calls the vendor as itself, and *for
    whom* has to remain answerable or an audit of model use answers nothing about people.
    """
    secret = "brokered-and-must-never-be-written-anywhere"
    credential = available_credential(secret=secret)
    surface = _qualified(ask_provider=CountingProvider(), credential_source=credential)

    response = TestClient(surface.app).post(
        "/ask", json={"question": GUIDANCE_QUESTION}, headers=surface.bearer()
    )

    assert secret not in response.text
    for entry in surface.audit.all_entries():
        assert secret not in str(entry.payload), f"the key reached {entry.event_type}'s payload"

    record = _asks(surface)[0].payload
    assert record["model_authority"].startswith("vault:model-credentials/")
    assert secret not in record["model_authority"]
    assert record["subject_user_id"] == "alice"


# ------------------------------------------------------------------ T017: one reader


def test_both_paths_reach_one_credential_reader_and_no_other() -> None:
    """SC-002 / FR-003, scoped to what a hermetic row can honestly check.

    **The providers differ by path and always have** — `LiveAnswerProvider` on the answering path,
    `ModelChooser` on the run path — and unifying those is not the design. What must be one is the
    **credential mechanism**: two ways to obtain authority to call a vendor is the fragmentation
    Principle VII forbids, and it is the failure mode where one path gets a fix and the other does
    not.

    Asserted by parsing rather than by running, because the run path only executes under an
    attested workload identity (`@pytest.mark.enclave`) and a single hermetic row cannot exercise
    both halves. The *behavioural* run-path half is owed in the enclave lane; this row is the
    structural claim, and it is the one that fails when somebody adds a second reader.
    """
    import ast
    import pathlib

    src = pathlib.Path(__file__).resolve().parents[3] / "src"
    assembly = [
        src / "surfaces" / "mcp" / "served.py",
        src / "surfaces" / "dispatch" / "entrypoint.py",
    ]

    #: Anything that would constitute a second way to obtain a vendor credential.
    RIVALS = ("EVAL_PROVIDER_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY")

    for path in assembly:
        source = path.read_text(encoding="utf-8")
        names = {node.id for node in ast.walk(ast.parse(source)) if isinstance(node, ast.Name)} | {
            alias.asname or alias.name
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.ImportFrom)
            for alias in node.names
        }
        assert "BrokeredModelCredential" in names, (
            f"{path.name} does not reach the one credential reader; if this path no longer needs "
            f"a model credential, remove it from this row and say why"
        )
        for rival in RIVALS:
            assert rival not in source, f"{path.name} names a second credential source: {rival}"
