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

import pytest
from fastapi.testclient import TestClient

from core.answering.corpus import Corpus
from tests.harness.api_fixtures import surface_under_test

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


@pytest.mark.xfail(
    strict=True,
    reason="FR-001 / 024's SC-006 (026): nothing on the answering path consults the Qualified "
    "Model Matrix, so a provider with no qualified cell is called anyway. The wiring lands in "
    "T010; T015 removes THIS MARKER and the row then guards the fix — it is not deleted.",
)
def test_a_provider_with_no_qualified_cell_is_never_called() -> None:
    """SC-001, and the row 024's contract has been asserting without having.

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
