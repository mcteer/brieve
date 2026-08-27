# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — row E1, made hermetic (051).

The contract states E1 as a named-runner row: *connected, restricted and air-gapped profiles
deliver the identical assembled instruction, because nothing is fetched at phase start.*

A person running that three times in three profiles is evidence about three runs. The
property underneath it is stronger and can be asserted here: **assembly performs no network
I/O at all**, so there is no profile in which its result could differ. Executable beats
attested where the executable version is available (ADR-0047's spirit), and this removes
E1 from the set of rows whose only enforcement is somebody remembering.

The named-runner row stays in the contract for what this cannot cover — that a real
allocation without outbound access starts Research at all.
"""

from __future__ import annotations

import socket
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from core.authoring.progress import PhaseName
from core.packs.agents import load_phase_agents
from core.packs.loader import FilesystemPackLoader
from surfaces.toolset import PACKS_ROOT


class NetworkReached(AssertionError):
    """Raised the moment assembly touches a socket. Loud, not skipped."""


@contextmanager
def _no_network() -> Iterator[None]:
    """Every outbound path a fetch could take, closed for the duration.

    Patching `socket.socket` alone would leave `create_connection` and name resolution open,
    and a fetch that resolved a host before failing has still reached the network.
    """

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise NetworkReached(
            "assembling a phase instruction touched the network. Skills are pinned executed "
            "content (ADR-0030) and are read from disk; a fetch here would make the "
            "air-gapped profile behave differently from the connected one."
        )

    patch = pytest.MonkeyPatch()
    for name in ("socket", "create_connection", "getaddrinfo"):
        patch.setattr(socket, name, refuse)
    try:
        yield
    finally:
        patch.undo()


@pytest.mark.parametrize("pack", ["terraform", "vault"])
def test_assembly_reaches_no_network(pack: str) -> None:
    """Every phase of every shipped pack, assembled with the network unavailable."""
    loader = FilesystemPackLoader(PACKS_ROOT)
    with _no_network():
        for phase in PhaseName:
            loaded = load_phase_agents(pack, phase, loader=loader, packs_root=PACKS_ROOT)
            assert loaded.body


def test_the_guard_itself_can_fire() -> None:
    """A network guard that never fires would green every row above it."""
    with pytest.raises(NetworkReached), _no_network():
        socket.create_connection(("example.invalid", 443))


def test_the_instruction_is_identical_with_and_without_the_network() -> None:
    """Byte-for-byte, which is the property the three profiles are a proxy for."""
    loader = FilesystemPackLoader(PACKS_ROOT)
    connected = load_phase_agents(
        "terraform", PhaseName.WRITE, loader=loader, packs_root=PACKS_ROOT
    ).body
    with _no_network():
        isolated = load_phase_agents(
            "terraform", PhaseName.WRITE, loader=loader, packs_root=PACKS_ROOT
        ).body
    assert connected == isolated
    assert "BEGIN PINNED SKILL" in isolated, "no skill was delivered; this row proves nothing"


def test_no_skill_path_escapes_the_pack_directory() -> None:
    """What is read is bounded by the pack, so 'from disk' cannot mean 'from anywhere'."""
    for pack in ("terraform", "vault"):
        manifest = FilesystemPackLoader(PACKS_ROOT).load(pack)
        pack_dir = (PACKS_ROOT / pack).resolve()
        for skill in manifest.skills:
            resolved = (PACKS_ROOT / pack / skill.path).resolve()
            assert resolved.is_relative_to(pack_dir), (pack, skill.name)
            assert Path(skill.path).parts[0] != "..", (pack, skill.name)
