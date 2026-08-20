# SPDX-License-Identifier: Apache-2.0
"""Assert bind/load never fetches the public web for instruction text (049, T032)."""

from __future__ import annotations

import socket
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from core.authoring.progress import PhaseName
from surfaces.dispatch.phase_agents import bind_phase_agents
from tests.conformance.phase_agents.fixtures import fake_run

PACKS = Path(__file__).resolve().parents[3] / "packs"


class OutboundRequestDuringBind(AssertionError):
    """Raised if phase bind tries to open a socket."""


@pytest.fixture
def no_egress(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    attempts: list[str] = []
    original = socket.socket.connect

    def refuse(self: Any, address: Any) -> None:
        attempts.append(str(address))
        raise OutboundRequestDuringBind(f"phase bind tried to reach {address}")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    yield attempts
    monkeypatch.setattr(socket.socket, "connect", original)


def test_binding_a_phase_does_not_open_a_socket(no_egress: list[str]) -> None:
    run = fake_run(("terraform",), PACKS)
    loaded = bind_phase_agents(run, PhaseName.WRITE)
    assert loaded.body.strip()
    assert no_egress == []
