# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — pack isolation of phase instructions (049, T027, A2/A3, SC-002)."""

from __future__ import annotations

from pathlib import Path

from core.authoring.progress import PhaseName
from surfaces.dispatch.phase_agents import bind_phase_agents
from tests.conformance.phase_agents.fixtures import fake_run

PACKS = Path(__file__).resolve().parents[3] / "packs"


def test_terraform_research_is_not_vault_research() -> None:
    tf = bind_phase_agents(fake_run(("terraform",), PACKS), PhaseName.RESEARCH)
    vt = bind_phase_agents(fake_run(("vault",), PACKS), PhaseName.RESEARCH)
    assert tf.body != vt.body
    assert tf.digest != vt.digest
    assert "Terraform" in tf.body
    assert "Vault" in vt.body


def test_a_vault_bound_run_never_records_terraform_agent_pins() -> None:
    run = fake_run(("vault",), PACKS)
    bind_phase_agents(run, PhaseName.RESEARCH)
    assert all(k.startswith("vault/agents/") for k in run.agent_content_pins)
    assert not any(k.startswith("terraform/agents/") for k in run.agent_content_pins)


def test_a_terraform_bound_run_never_records_vault_agent_pins() -> None:
    run = fake_run(("terraform",), PACKS)
    bind_phase_agents(run, PhaseName.RESEARCH)
    assert all(k.startswith("terraform/agents/") for k in run.agent_content_pins)
    assert not any(k.startswith("vault/agents/") for k in run.agent_content_pins)
