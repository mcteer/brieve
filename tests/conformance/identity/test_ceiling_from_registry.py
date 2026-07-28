# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — an agent's ceiling comes from what an operator configured.

Every row asserting "authority cannot exceed the ceiling" has passed since 002 against a
dictionary in `FakeIdentityFabric`. They were not wrong; they were narrower than they read.
This is the first time the number comes from the thing an operator actually edits.

**Nothing here is faked.** Ceiling, user scope, and policy all resolve from the live trust
fabric. These rows ran through a hybrid harness during implementation, because
`manufacture_authority` takes all three from one object and no story could be proven until
every story had landed; T046a migrated them and deleted the hybrid.

**Two definitions, not one.** "The ceiling bounds authority" is only demonstrable against a
ceiling that excludes something a run would otherwise get. With one definition, every
assertion here would hold under a fabric that ignored ceilings entirely.
"""

from __future__ import annotations

import pytest

from core.authority.errors import AuthorityRefuseError, ResolutionRefused
from core.authority.types import AuthorityScope
from core.run import start_governed_run
from tests.conformance.identity.conftest import (
    production_fabric,
    registry_of_known_tools,
    subject_fabric,
)
from tests.harness import capture_audit, frozen_clock

pytestmark = pytest.mark.enclave


def test_row_the_same_request_refuses_under_the_narrow_ceiling() -> None:
    """`planner-agent`'s registered ceiling excludes `apply`, so the run does not start.

    **The platform refuses rather than narrowing**, and that is worth stating because the
    spec's acceptance scenario said otherwise — it described authority being manufactured
    for the permitted subset. 002's `manufacture_authority` refuses outright when a
    requested scope exceeds the ceiling, which is stricter and fail-closed, and the
    scenario was written without checking it. The code is right; the sentence was wrong.
    """
    with pytest.raises(AuthorityRefuseError):
        start_governed_run(
            correlation_id="corr-ceiling-planner",
            subject_user_id="user-1",
            agent_definition_id="planner-agent",
            requested_scope=AuthorityScope(tool_names=frozenset({"echo", "plan", "apply"})),
            identity_fabric=subject_fabric("operator"),
            registry=registry_of_known_tools(),
            clock=frozen_clock(),
            audit_sink=capture_audit(),
        )


def test_row_the_same_request_succeeds_under_the_wide_ceiling() -> None:
    """The pair, and the only thing that makes the row above mean anything.

    Identical request, identical user, identical everything except which definition the run
    is started under — so the difference in outcome can only be the ceiling. A fabric that
    refused everything, or that returned an empty ceiling for all definitions, would
    satisfy the previous row perfectly and fail this one.
    """
    run = start_governed_run(
        correlation_id="corr-ceiling-applier",
        subject_user_id="user-1",
        agent_definition_id="applier-agent",
        requested_scope=AuthorityScope(tool_names=frozenset({"echo", "plan", "apply"})),
        identity_fabric=subject_fabric("operator"),
        registry=registry_of_known_tools(),
        clock=frozen_clock(),
        audit_sink=capture_audit(),
    )

    assert {"echo", "plan", "apply"} <= run.authority.effective.tool_names


def test_row_a_request_within_the_narrow_ceiling_is_granted() -> None:
    """`planner-agent` is not simply broken — it grants what its ceiling allows.

    Without this, "the narrow definition refuses" would be satisfied by a definition whose
    ceiling failed to resolve at all.
    """
    run = start_governed_run(
        correlation_id="corr-ceiling-planner-ok",
        subject_user_id="user-1",
        agent_definition_id="planner-agent",
        requested_scope=AuthorityScope(tool_names=frozenset({"echo", "plan"})),
        identity_fabric=subject_fabric("operator"),
        registry=registry_of_known_tools(),
        clock=frozen_clock(),
        audit_sink=capture_audit(),
    )

    assert {"echo", "plan"} <= run.authority.effective.tool_names
    assert "apply" not in run.authority.effective.tool_names


def test_row_the_two_ceilings_actually_differ() -> None:
    """States the comparison the two rows above depend on, so it cannot silently stop holding.

    If both definitions ever resolved to the same ceiling, both rows would still pass and
    neither would be testing anything.
    """
    fabric = production_fabric()

    planner = fabric.resolve_ceiling("planner-agent")
    applier = fabric.resolve_ceiling("applier-agent")

    assert planner.tool_names != applier.tool_names
    assert planner.tool_names < applier.tool_names, (
        "the fixture pair is no longer nested, so 'narrower ceiling grants less' is not "
        "what these rows are measuring"
    )


def test_row_an_unregistered_definition_refuses() -> None:
    """Never a default ceiling, never an open one (FR-003)."""
    with pytest.raises(ResolutionRefused) as caught:
        production_fabric().resolve_ceiling("no-such-agent-definition")

    assert caught.value.reason_code == "unknown_agent_definition"
