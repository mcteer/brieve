# SPDX-License-Identifier: Apache-2.0
"""Component tests for AgentPin parse and load (049, T013). Fixture pack names only."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from core.authoring.progress import PhaseName
from core.packs.agents import load_phase_agents
from core.packs.loader import FilesystemPackLoader, parse_manifest
from core.packs.manifest import ManifestError
from tests.conformance.phase_agents.fixtures import write_authoring_pack


def test_five_pins_load_for_an_authoring_pack(tmp_path: Path) -> None:
    write_authoring_pack(tmp_path, "alpha")
    manifest = FilesystemPackLoader(tmp_path).load("alpha")
    assert {pin.phase for pin in manifest.agents} == {p.value for p in PhaseName}
    loaded = load_phase_agents(
        "alpha", PhaseName.WRITE, loader=FilesystemPackLoader(tmp_path), packs_root=tmp_path
    )
    assert loaded.pack == "alpha"
    assert loaded.phase is PhaseName.WRITE
    assert "Unique steer" in loaded.body
    assert loaded.digest == hashlib.sha256(loaded.body.encode()).hexdigest()


def test_an_authoring_pack_with_four_phases_is_incomplete(tmp_path: Path) -> None:
    write_authoring_pack(tmp_path, "alpha", omit_phase="write")
    with pytest.raises(ManifestError) as caught:
        FilesystemPackLoader(tmp_path).load("alpha")
    assert caught.value.reason_code == "agents_incomplete"


def test_unknown_phase_refuses() -> None:
    with pytest.raises(ManifestError) as caught:
        parse_manifest(
            {
                "pack": {
                    "name": "alpha",
                    "product": "alpha",
                    "version": "0.1.0",
                    "provenance": "authored",
                    "probe": "alpha_probe",
                },
                "agents": [
                    {
                        "phase": "deploy",
                        "path": "agents/deploy/AGENTS.md",
                        "version": "0.1.0",
                        "digest": "0" * 64,
                    }
                ],
            }
        )
    assert caught.value.reason_code == "unknown_phase"


def test_duplicate_phase_refuses() -> None:
    pin = {
        "phase": "research",
        "path": "agents/research/AGENTS.md",
        "version": "0.1.0",
        "digest": "0" * 64,
    }
    with pytest.raises(ManifestError) as caught:
        parse_manifest(
            {
                "pack": {
                    "name": "alpha",
                    "product": "alpha",
                    "version": "0.1.0",
                    "provenance": "authored",
                    "probe": "alpha_probe",
                },
                "agents": [pin, dict(pin)],
            }
        )
    assert caught.value.reason_code == "duplicate_phase"


def test_path_escape_is_malformed() -> None:
    with pytest.raises(ManifestError) as caught:
        parse_manifest(
            {
                "pack": {
                    "name": "alpha",
                    "product": "alpha",
                    "version": "0.1.0",
                    "provenance": "authored",
                    "probe": "alpha_probe",
                },
                "agents": [
                    {
                        "phase": "write",
                        "path": "agents/../write/AGENTS.md",
                        "version": "0.1.0",
                        "digest": "0" * 64,
                    }
                ],
            }
        )
    assert caught.value.reason_code == "malformed_manifest"


def test_digest_mismatch_refuses(tmp_path: Path) -> None:
    write_authoring_pack(tmp_path, "alpha", wrong_digest_phase="write")
    with pytest.raises(ManifestError) as caught:
        FilesystemPackLoader(tmp_path).load("alpha")
    assert caught.value.reason_code == "digest_mismatch"


def test_empty_body_refuses(tmp_path: Path) -> None:
    write_authoring_pack(tmp_path, "alpha", empty_phase="write")
    with pytest.raises(ManifestError) as caught:
        FilesystemPackLoader(tmp_path).load("alpha")
    assert caught.value.reason_code == "agents_empty"


def test_missing_provenance_refuses(tmp_path: Path) -> None:
    write_authoring_pack(tmp_path, "alpha", skip_provenance="write")
    with pytest.raises(ManifestError) as caught:
        FilesystemPackLoader(tmp_path).load("alpha")
    assert caught.value.reason_code == "agents_provenance_missing"
