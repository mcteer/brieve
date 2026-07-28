# SPDX-License-Identifier: Apache-2.0
"""A mid-run trust-fabric outage suspends the run; a run-start outage refuses it.

**The asymmetry is not a special case.** A run that cannot resolve identity before it
begins has no grant, no checkpoint, and nothing to come back to — so refusing is the only
available answer. A run that loses the fabric mid-flight has all three, and ADR-0049 is
explicit that a run may wait on a machine condition: the condition clears itself, and
ending hours of work on a transient blip is the outcome suspension exists to avoid.

What falls out of that: the disposition depends on whether the run exists yet, which is a
property of the run rather than a rule someone has to remember.
"""

from __future__ import annotations

from typing import Any

import pytest

from core.authority.errors import ResolutionRefused
from core.authority.types import AuthorityScope
from core.hooks.suspension import TRUST_FABRIC_DEPENDENCY
from core.registry.memory import ToolRegistry
from core.run import RunState, start_governed_run
from core.tools.invoke import invoke_tool
from tests.harness import capture_audit, fake_identity_fabric, frozen_clock
from tests.harness.fake_identity_fabric import DEFAULT_AGENT_DEFINITION_ID


class FabricThatFailsOnPolicy:
    """Resolves everything a run start needs, then loses the fabric.

    Models the real sequence: a run starts fine, works for a while, and the trust fabric
    becomes unreachable at some later step. A fabric that failed from the beginning would
    exercise the run-start path instead, which is a different requirement.
    """

    def __init__(self, inner: Any, *, reason: str = "fabric_unreachable") -> None:
        self._inner = inner
        self._reason = reason
        self.fail = False

    def resolve_user_scope(self, subject_user_id: str) -> AuthorityScope:
        return self._inner.resolve_user_scope(subject_user_id)  # type: ignore[no-any-return]

    def resolve_ceiling(self, agent_definition_id: str) -> AuthorityScope:
        return self._inner.resolve_ceiling(agent_definition_id)  # type: ignore[no-any-return]

    def resolve_policy(self, agent_definition_id: str) -> AuthorityScope | None:
        if self.fail:
            raise ResolutionRefused("trust fabric unreachable", reason_code=self._reason)
        return self._inner.resolve_policy(agent_definition_id)  # type: ignore[no-any-return]

    def resolve_product_entitlements(self, subject_user_id: str, product: str) -> frozenset[str]:
        return self._inner.resolve_product_entitlements(subject_user_id, product)  # type: ignore[no-any-return]


def _run(fabric: Any) -> Any:
    registry = ToolRegistry()
    registry.register("echo", lambda _arguments: {"ok": "ran"})
    return start_governed_run(
        correlation_id="corr-outage",
        subject_user_id="user-1",
        agent_definition_id=DEFAULT_AGENT_DEFINITION_ID,
        requested_scope=AuthorityScope(tool_names=frozenset({"echo"})),
        identity_fabric=fabric,
        registry=registry,
        clock=frozen_clock(),
        audit_sink=capture_audit(),
    )


@pytest.mark.parametrize("reason", ["fabric_unreachable", "fabric_timeout"])
def test_a_mid_run_outage_suspends_naming_the_fabric(reason: str) -> None:
    """Both failure modes suspend. A timeout is an outage that answered slowly."""
    fabric = FabricThatFailsOnPolicy(
        fake_identity_fabric(tool_names={"echo"}, ceiling_tools={"echo"}), reason=reason
    )
    run = _run(fabric)
    assert invoke_tool(run, "echo", {}).allowed

    fabric.fail = True
    result = invoke_tool(run, "echo", {})

    assert not result.allowed
    assert run.state is RunState.SUSPENDED
    assert run.stop_reason == f"awaiting:{TRUST_FABRIC_DEPENDENCY}"


def test_the_suspended_run_is_not_terminal() -> None:
    """The one-line property the whole mechanism rests on.

    A terminal state would make the sweeper refuse to resume it, and the run would sit
    suspended forever — the hang ADR-0049 exists to prevent, produced by the mechanism
    meant to prevent it.
    """
    fabric = FabricThatFailsOnPolicy(
        fake_identity_fabric(tool_names={"echo"}, ceiling_tools={"echo"})
    )
    run = _run(fabric)
    fabric.fail = True
    invoke_tool(run, "echo", {})

    assert not run.state.is_terminal()


def test_a_run_start_outage_refuses_rather_than_suspending() -> None:
    """The other side of the asymmetry: no grant, no checkpoint, nothing to resume.

    This is what makes the mid-run behaviour a consequence rather than a rule — the run
    does not exist yet, so suspension is not an option that was rejected. It is not
    available.
    """

    class DeadFabric:
        def resolve_user_scope(self, subject_user_id: str) -> AuthorityScope:
            raise ResolutionRefused("down", reason_code="fabric_unreachable")

        def resolve_ceiling(self, agent_definition_id: str) -> AuthorityScope:
            raise ResolutionRefused("down", reason_code="fabric_unreachable")

        def resolve_policy(self, agent_definition_id: str) -> AuthorityScope | None:
            raise ResolutionRefused("down", reason_code="fabric_unreachable")

        def resolve_product_entitlements(
            self, subject_user_id: str, product: str
        ) -> frozenset[str]:
            raise ResolutionRefused("down", reason_code="fabric_unreachable")

    from core.authority.errors import AuthorityRefuseError

    with pytest.raises(AuthorityRefuseError):
        _run(DeadFabric())


def test_an_ordinary_policy_failure_does_not_suspend() -> None:
    """Only an unreachable FABRIC suspends. Everything else denies the step.

    Without this, any resolution problem would suspend runs — turning a misconfigured
    policy record into an estate-wide pause, and making suspension mean 'something went
    wrong' rather than 'something we are waiting on'.
    """
    fabric = FabricThatFailsOnPolicy(
        fake_identity_fabric(tool_names={"echo"}, ceiling_tools={"echo"}),
        reason="unsupported_schema_version",
    )
    run = _run(fabric)
    fabric.fail = True

    result = invoke_tool(run, "echo", {})

    assert not result.allowed
    assert run.state is not RunState.SUSPENDED
