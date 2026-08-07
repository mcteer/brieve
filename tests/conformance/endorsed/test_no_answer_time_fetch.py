# SPDX-License-Identifier: Apache-2.0
"""E23 — the answering path makes zero outbound requests (045, T021, SC-003, ADR-0070).

**Asserted by instrumentation, not by the absence of code.** "We do not call out here" is a
claim about today's implementation; a socket that fails the test is a claim about every commit
after it. This is ADR-0070's central bound — the record permits egress during detection,
review-sync and endorsement-sync, and *never* during answering — so the bound is enforced by
making the operation impossible rather than by nobody having written it.

**With an endorsed source configured**, which is the whole point. A row that ran with nothing
endorsed would assert that a path nobody exercised makes no requests, which is true of any path
that does not run. So the corpus here holds customer material and the answer cites it.
"""

from __future__ import annotations

import socket
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from core.answering.endorsed.corpus import build_endorsed_corpus
from core.answering.endorsed.records import (
    ADOPTED,
    EndorsedDocument,
    SyncedVersion,
    digest_of_document,
)
from tests.harness.api_fixtures import (
    available_credential,
    qualified_ask_authority,
    surface_under_test,
)

ENDORSED_PATH = "/endorsed/acme-standards/logging.md"


class OutboundRequestDuringAnswering(AssertionError):
    """Raised the instant anything tries to open a socket while an answer is being composed.

    Its own type so the failure names what happened rather than surfacing as a connection
    error somewhere three frames down, which is how this kind of violation usually gets
    misread as a flaky network.
    """


@pytest.fixture
def no_egress(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    """Make every outbound attempt fail loudly, and record what was attempted.

    **`socket.socket.connect` and not just `urllib`**, because the bound is about reaching a
    third party at all — a future implementation using `httpx`, `requests`, or a `git`
    subprocess talking over a socket must fail this too. Patching one library would assert
    something about that library rather than about the path.
    """
    attempts: list[str] = []
    original = socket.socket.connect

    def refuse(self: Any, address: Any) -> None:
        attempts.append(str(address))
        raise OutboundRequestDuringAnswering(
            f"the answering path tried to reach {address}. ADR-0070 permits endorsed-content "
            f"egress during detection, review-sync and endorsement-sync only — never while "
            f"answering, because a corpus that fetched at answer time would make every answer "
            f"depend on a third party being reachable and would make 'pinned' untrue."
        )

    monkeypatch.setattr(socket.socket, "connect", refuse)
    yield attempts
    monkeypatch.setattr(socket.socket, "connect", original)


def _endorsed() -> Any:
    sections = {"retention": "Logs are retained for 400 days."}
    return build_endorsed_corpus(
        [
            SyncedVersion(
                version_id="v-one",
                tenant_id="acme",
                source="acme-standards",
                upstream_tip="abc123",
                synced_at=datetime(2026, 8, 1, tzinfo=UTC),
                synced_by="dan@acme.example",
                state=ADOPTED,
                documents={
                    ENDORSED_PATH: EndorsedDocument(
                        path=ENDORSED_PATH,
                        url="https://git.example.com/acme/standards/logging.md",
                        digest=digest_of_document(sections),
                        anchors=frozenset(sections),
                        sections=dict(sections),
                    )
                },
            )
        ]
    )


class _Cites:
    def answer(self, question: str, corpus: Any, context: str = "") -> list[dict[str, Any]]:
        return [
            {
                "statement": "Logs are retained for 400 days.",
                "citations": [{"path": ENDORSED_PATH, "anchor": "retention"}],
            }
        ]


def _surface() -> Any:
    return surface_under_test(
        ask_provider=_Cites(),
        ask_model="anthropic/claude-opus@5",
        ask_authority=qualified_ask_authority(),
        credential_source=available_credential(),
        endorsed_reader=_endorsed,
    )


def test_row_e23_answering_from_endorsed_material_opens_no_socket(no_egress: list[str]) -> None:
    """The row this task exists for.

    The answer is composed, the citation into customer material resolves, and nothing was
    fetched — because the content was synced earlier and read from the store, exactly as the
    pinned corpus is read from its manifest.
    """
    surface = _surface()

    response = TestClient(surface.app).post(
        "/ask", json={"question": "How long are logs retained?"}, headers=surface.bearer()
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["disposition"] == "answered"
    assert body["claims"][0]["citations"][0]["provenance"] == "customer-endorsed"
    assert attempts_are_empty(no_egress)


def test_row_e23_the_mcp_surface_fetches_nothing_either(no_egress: list[str]) -> None:
    """ADR-0033 parity, and 043 shipped that asymmetry once.

    A bound that held on one transport and not the other would be a bound the platform does
    not have — a caller choosing MCP would get the behaviour nobody asserted.
    """
    surface = _surface()

    result = surface.mcp.call(
        "ask", {"question": "How long are logs retained?"}, subject=surface.subject()
    )

    assert result.ok, result.payload
    # Not merely `ok`: the row must exercise the answering path it claims to instrument, and
    # an MCP result that declined would satisfy `ok` while fetching nothing for the same
    # reason a path that does not run fetches nothing.
    assert result.payload["disposition"] == "answered"
    assert result.payload["claims"][0]["citations"][0]["provenance"] == "customer-endorsed"
    assert result.payload["endorsed_version"] == "v-one"
    assert attempts_are_empty(no_egress)


def test_the_instrumentation_can_actually_fail(no_egress: list[str]) -> None:
    """**A checker that has never rejected anything is indistinguishable from `pass`.**

    The repository has shipped several checks that passed by measuring nothing. This one is
    exercised directly: a deliberate outbound attempt must raise, or the two rows above are
    green about a socket patch that never took effect.
    """
    # **`socket.connect` directly, not `urllib`**, and that is not a workaround. 005's egress
    # inventory refuses an HTTP client import outside the enclave paths, and it is right to:
    # this file does not talk to the enclave, so adding it to that list to satisfy a control
    # would put a false statement in an inventory whose whole value is being exhaustive.
    # Connecting a socket is also the more honest control — it exercises the thing the fixture
    # actually patches, one layer below whichever HTTP library a future implementation picks.
    with pytest.raises(OutboundRequestDuringAnswering):
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("127.0.0.1", 9))

    assert no_egress, "the instrumentation recorded nothing for an attempt that was made"
    no_egress.clear()


def attempts_are_empty(attempts: list[str]) -> bool:
    """Named so the assertion reads as the claim it makes, and reports what it found."""
    assert not attempts, f"the answering path reached out to {attempts}"
    return True
