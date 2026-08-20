# SPDX-License-Identifier: Apache-2.0
"""Hermetic AuthoringRequest walk of Vault five-phase pins (049, T030)."""

from __future__ import annotations

from pathlib import Path

from core.authoring.progress import PHASE_ORDER
from core.authoring.request import AuthoringRequest
from surfaces.dispatch.phase_agents import bind_phase_agents
from tests.conformance.phase_agents.fixtures import fake_run

PACKS = Path(__file__).resolve().parents[3] / "packs"
AUTHORING_PACKS = frozenset({"vault", "terraform"})


def test_vault_authoring_request_walks_five_phase_pins() -> None:
    request = AuthoringRequest(
        correlation_id="corr-049-vault-walk",
        tenant_id="tenant-acme",
        requester="dana",
        target_repository="acme/app",
        task="Add an AppRole policy for ci-deploy",
        pack="vault",
    )
    request.validate(
        run_tenant_id="tenant-acme",
        owned_repositories=frozenset({"acme/app"}),
        packs_declaring_authoring=AUTHORING_PACKS,
    )
    run = fake_run((request.pack,), PACKS)
    digests: list[str] = []
    for phase in PHASE_ORDER:
        loaded = bind_phase_agents(run, phase)
        assert loaded.pack == "vault"
        key = f"vault/agents/{phase.value}@{loaded.version}"
        assert run.agent_content_pins[key] == loaded.digest
        digests.append(loaded.digest)
    assert len(set(digests)) == 5
    assert not any(k.startswith("terraform/agents/") for k in run.agent_content_pins)
