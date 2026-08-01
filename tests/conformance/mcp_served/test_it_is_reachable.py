# SPDX-License-Identifier: Apache-2.0
"""US4 — reachable from where a person actually works, and independent of the sweeper."""

from __future__ import annotations

import subprocess

import pytest

from tests.conformance.mcp_served import surfaces

pytestmark = [pytest.mark.enclave, pytest.mark.host_enclave]

CONTRACT = surfaces.ROOT / "specs/019-mcp-server/contracts/conformance.md"


def test_it_is_reachable_from_outside_the_platform_network(running_surface: str) -> None:
    """FR-014: a client on the developer's own machine connects.

    **The limit, recorded because the row cannot state it itself**: this proves reachability
    *from where the lane runs*. If the lane ever moves somewhere that shares a network
    namespace with the platform, it keeps passing and stops meaning anything. Whoever moves it
    owes this feature's contract an update — the failure would be silent, and this feature
    exists because of a different silent one.
    """
    status = surfaces.handshake_refused_without_credential()

    assert status == 401, (
        f"the surface answered {status} from this machine. A connection error here means the "
        f"port is not published to the developer's machine at all — which was true of every "
        f"host-mode surface in this platform until 019 was born in bridge mode."
    )


def test_the_published_port_is_on_the_developers_machine(running_surface: str) -> None:
    """The mechanism behind FR-014, asserted rather than assumed.

    Host mode publishes nothing: `docker ps` shows an empty Ports column and the port block
    beside it is inert. Measured on 2026-07-31 against the API and the portal, one of which
    had to be converted at real cost. This surface was born in bridge mode so it never would.
    """
    listed = subprocess.run(  # noqa: S603 - fixed binary
        ["docker", "ps", "--format", "{{.Names}}\t{{.Ports}}"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout

    published = [line for line in listed.splitlines() if "8083" in line]

    assert published, (
        "no container publishes the surface's port. In host network mode the Ports column is "
        "empty and nothing on this machine can reach it, however healthy the process is."
    )


def test_neither_process_takes_the_other_down(running_surface: str) -> None:
    """FR-015a, SC-008: the served transport and the supervisory loop are separate jobs.

    Asserted structurally rather than by stopping things. A row that killed the sweeper to
    watch the surface survive would leave suspended runs unresumed if it died between the two
    halves — and the property it would prove is one two jobs give by construction.

    A future change merging them re-creates the failure this forbids: a protocol crash that
    silently stops suspended runs from resuming, which presents as a hang and quietly ends
    ADR-0049's guarantee that consent to start a run is consent to finish it.
    """
    jobs = subprocess.run(  # noqa: S603 - fixed binary
        ["nomad", "job", "status", "-short", "-address=http://127.0.0.1:4646"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout

    assert "mcp-surface" in jobs, "the served surface is not a job of its own"
    assert "\nmcp " in jobs or jobs.startswith("mcp "), (
        "the supervisory loop is not running as a separate job — if these ever became one "
        "process, a protocol crash would stop suspended runs resuming"
    )


def test_the_contract_states_what_this_gate_does_not_assert() -> None:
    """FR-018: the honest limit is checked, not trusted.

    A later edit could remove the statement and let a green lane imply that a model chose
    something. It did not: the tool selection behind a dispatched run is still a scripted
    sequence, and this surface serves the transport rather than putting a model in the loop.
    """
    contract = CONTRACT.read_text()

    required = {
        "no model is choosing anything": "model",
        "the reachability limit": "from where the lane runs",
    }
    missing = [why for why, phrase in required.items() if phrase not in contract]

    assert not missing, (
        "the conformance contract no longer records a limit these rows depend on: "
        + ", ".join(missing)
    )
