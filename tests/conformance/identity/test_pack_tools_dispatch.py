# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — a pack tool reaches a real product through the real pipeline.

**This is the row the Vault pack exists for.** Terraform proves *adoption* — a real upstream,
a pinned commit, genuine provenance. Vault proves *invocation*: its tools reach a product
that actually runs here, so Principle II's claim gets exercised end to end rather than
against a fixture that would agree with anything.

Every other pack row in this feature is hermetic and would pass against a platform where no
tool had ever been called. This one needs the enclave, and it fails if the pack's product is
unreachable, if the probe is missing, if the ceiling does not know the tool's name, or if the
dependency gate denies the call — the set of failures that were invisible until a pack
declared a product that could genuinely be down.
"""

from __future__ import annotations

import pytest

from core.authority.types import AuthorityScope
from core.registry.memory import ToolRegistry
from core.run import start_governed_run
from core.tools.invoke import invoke_tool
from surfaces.probes import vault_probe
from surfaces.toolset import build_registry, known_actions, known_tools
from tests.conformance.identity.conftest import production_fabric

pytestmark = pytest.mark.host_enclave


def test_vault_is_reachable_from_the_probe_the_pack_names() -> None:
    """The precondition every row below depends on.

    Separated so a Vault outage reports as a Vault outage rather than as a pack defect. The
    two look identical from a denied tool call, which is the confusion the probe exists to
    remove.
    """
    reachable, detail = vault_probe("vault")
    assert reachable, f"vault is not reachable ({detail}); the rows below cannot mean anything"


def test_the_vault_pack_registers_its_tools_with_risk_classes_intact() -> None:
    registry, loaded = build_registry(packs=["vault"])
    assert "vault_read" in known_tools(registry)
    assert "vault.read" in known_actions(registry)
    assert registry.resolve("vault_read").risk_class == "secret_touching"
    assert loaded["vault"].product == "vault"
    assert loaded["vault"].probe is not None, (
        "the Vault pack registered without a resolved probe; its product would record "
        "UNHEALTHY and every one of its tools would be denied while Vault is up"
    )


def test_a_pack_tool_passes_the_same_hooks_as_any_other_tool() -> None:
    """FR-003, exercised rather than inspected.

    The hermetic row asserts there is no bypass *path*; this asserts a real call goes through
    the pipeline it is supposed to. A structural check and a live call are different evidence,
    and the structural one holds even if nothing had ever been invoked.
    """
    registry, _ = build_registry(packs=["vault"])
    run = start_governed_run(
        correlation_id="corr-pack-dispatch-001",
        subject_user_id="conformance",
        agent_definition_id="planner",
        requested_scope=_scope_of(registry, "vault_read"),
        identity_fabric=production_fabric(),
        registry=registry,
    )

    outcome = invoke_tool(run, "vault_read", {"path": "conformance/probe"})

    assert outcome.allowed, f"the pack tool was refused: {outcome.reason_code}"
    events = [e.event_type for e in run.audit_sink.list_by_correlation_id(run.correlation_id)]
    assert "pre_decision" in events, f"no pre-hook decision recorded; got {events}"
    assert "tool_outcome" in events, f"no tool outcome recorded; got {events}"


def test_a_read_against_real_vault_returns_keys_and_never_values() -> None:
    """Against the real product, not a double.

    `vault_read` returning keys and presence is a property of the handler; this asserts it
    holds when the handler is talking to an actual Vault rather than to a stub that returns
    nothing interesting either way.

    A value returned here reaches tool output, then the trail, then model context — and the
    trail is append-only and hash-chained, so what lands there is permanent (ADR-0051).
    """
    from surfaces.handlers import vault_read

    result = vault_read({"path": "conformance/probe"})

    assert set(result) == {"path", "present", "keys"}, (
        f"vault_read returned {sorted(result)}; anything beyond path/present/keys risks "
        f"carrying secret material into a permanent record"
    )
    assert isinstance(result["keys"], list)
    assert all(isinstance(k, str) for k in result["keys"])


def _scope_of(registry: ToolRegistry, *tools: str) -> AuthorityScope:
    """The scope a run requests, derived from what the tools actually declare.

    Derived rather than written out, for the reason the vocabulary is: a literal here would
    have to agree with the manifest, and the two would drift the first time a pack changed
    a product action.
    """
    actions = {registry.resolve(t).product_action for t in tools}
    return AuthorityScope(
        tool_names=frozenset(tools),
        product_actions=frozenset(str(a) for a in actions if a),
    )
