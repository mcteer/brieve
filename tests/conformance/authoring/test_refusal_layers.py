# SPDX-License-Identifier: Apache-2.0
"""A2 — three refusal layers, three distinguishable reasons (041, FR-019, SC-008).

FAKE_FABRIC_IS_FAULT_INJECTION = (
    "Each row here injects exactly one authority-resolution failure — a user scope, a ceiling, "
    "or a task scope that omits the tool — because the property under test IS which of those "
    "three said no. The production fabric resolves all three from live records, so a row using "
    "it could not vary one term while holding the others fixed."
)

**Why this row needed a mechanism, not just an assertion.** Until 041 `intersect_scopes`
computed one effective set and kept no memory of which term dropped a name, so every refusal
downstream read `authority_insufficient`. That is true and useless: "your ceiling does not
carry this tool" sends an operator to a governance record, and "this run did not ask for it"
sends them to the dispatch. One code for both is a signpost pointing at the whole town.
"""

from __future__ import annotations

import pytest

from core.audit.sink import InMemoryAuditSink
from core.authority.intersection import (
    OUTSIDE_CEILING,
    OUTSIDE_POLICY,
    OUTSIDE_TASK_SCOPE,
    OUTSIDE_USER_SCOPE,
    excluded_by,
    exclusions,
)
from core.authority.types import AuthorityScope
from core.registry.memory import ToolRegistry
from core.run import GovernedRun, start_governed_run
from core.tools.invoke import invoke_tool
from tests.harness.capture_audit import capture_audit
from tests.harness.fake_identity_fabric import fake_identity_fabric
from tests.harness.frozen_clock import frozen_clock

FAKE_FABRIC_IS_FAULT_INJECTION = (
    "Each row injects one authority-resolution failure, because which term refused IS the "
    "property under test."
)

TOOL = "author_file"
DEFINITION = "authoring-agent"


def _scope(*tools: str) -> AuthorityScope:
    return AuthorityScope(tool_names=frozenset(tools), product_actions=frozenset())


def _run(
    *,
    user: set[str],
    ceiling: set[str],
    requested: set[str],
    registry: ToolRegistry,
    audit: InMemoryAuditSink,
) -> GovernedRun:
    fabric = fake_identity_fabric(
        tool_names=user,
        product_actions=set(),
        ceiling_tools=ceiling,
        ceiling_actions=set(),
    )
    return start_governed_run(
        agent_definition_id=DEFINITION,
        correlation_id="corr-041-layers",
        subject_user_id="user-1",
        requested_scope=_scope(*requested),
        identity_fabric=fabric,
        clock=frozen_clock(),
        registry=registry,
        audit_sink=audit,
    )


def _registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(TOOL, lambda arguments: {"ok": True}, risk_class="write")
    return registry


# --------------------------------------------------------------------------------------
# The pure algebra. These need no run at all, which is the point: the answer is a property
# of the terms, computed once where all four are in scope.
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("user", "ceiling", "requested", "expected"),
    [
        (set(), {TOOL}, {TOOL}, OUTSIDE_USER_SCOPE),
        ({TOOL}, set(), {TOOL}, OUTSIDE_CEILING),
        ({TOOL}, {TOOL}, set(), OUTSIDE_TASK_SCOPE),
        ({TOOL}, {TOOL}, {TOOL}, None),
    ],
)
def test_the_algebra_names_the_term_that_dropped_the_tool(
    user: set[str], ceiling: set[str], requested: set[str], expected: str | None
) -> None:
    assert (
        excluded_by(
            TOOL, user=_scope(*user), ceiling=_scope(*ceiling), requested=_scope(*requested)
        )
        == expected
    )


def test_policy_narrowing_is_its_own_answer() -> None:
    """Distinct from the other three because it can become true mid-run."""
    assert (
        excluded_by(
            TOOL,
            user=_scope(TOOL),
            ceiling=_scope(TOOL),
            requested=_scope(TOOL),
            policy=_scope(),
        )
        == OUTSIDE_POLICY
    )


def test_precedence_reports_the_bound_a_reader_must_satisfy_first() -> None:
    """When two terms exclude, the reported one is the outer bound.

    Telling somebody to widen a task scope for a tool their ceiling never carried is worse
    than saying nothing — they would do the work and be refused again.
    """
    both = excluded_by(TOOL, user=_scope(), ceiling=_scope(), requested=_scope())
    assert both == OUTSIDE_USER_SCOPE

    ceiling_and_scope = excluded_by(TOOL, user=_scope(TOOL), ceiling=_scope(), requested=_scope())
    assert ceiling_and_scope == OUTSIDE_CEILING


def test_exclusions_covers_names_no_single_term_mentions() -> None:
    """The domain is the UNION of the terms, which is where the interesting cases live.

    A run requesting a tool no ceiling mentions must still get an answer naming the ceiling.
    Restricting the map to the ceiling's own names would leave exactly that case unexplained.
    """
    found = exclusions(user=_scope("a", "b"), ceiling=_scope("a"), requested=_scope("a", "b", "c"))
    assert found["b"] == OUTSIDE_CEILING
    assert found["c"] == OUTSIDE_USER_SCOPE
    assert "a" not in found, "a tool every term carries is not excluded by anything"


# --------------------------------------------------------------------------------------
# A2 proper: the same three layers, observed through a governed run's refusal.
#
# **Where the discriminator actually lives, corrected during implementation.** The plan put
# it on the authority hook. Measured, the hook's check fires only when live policy narrows
# authority AFTER issuance — every ceiling and task-scope refusal is caught earlier, by the
# pipeline's scope gate against `run.scope`. So both of those layers arrived as one
# `out_of_scope` record and the hook's new codes were unreachable for them.
#
# The reason CODE stays `out_of_scope`, because it is a stable vocabulary that surfaces and
# recorded runs depend on. The discriminator rides in the payload, which is what SC-008 asks
# for: distinguishable by an operator reading only the record.
# --------------------------------------------------------------------------------------


def test_row_a2_layer_one_an_unknown_tool_is_its_own_answer() -> None:
    """The vocabulary layer refuses before authority is consulted at all.

    A tool nothing registered cannot be denied by a ceiling, because there is nothing for a
    ceiling to have named. This sends a reader to the registry; the other two send them to
    governance records.
    """
    audit = capture_audit()
    run = _run(user={TOOL}, ceiling={TOOL}, requested={TOOL}, registry=ToolRegistry(), audit=audit)

    result = invoke_tool(run, TOOL, {"path": "m.tf", "content": "x"})

    assert not result.allowed
    assert result.reason_code == "unregistered"


def test_row_a2_layer_two_outside_the_ceiling_names_the_ceiling() -> None:
    """The ceiling record decides, and the record says so.

    A run may not request more than its ceiling — `manufacture_authority` refuses the run
    outright — so a tool outside the ceiling is necessarily outside the request too. The
    useful answer for such a tool is the OUTER bound: widening a task scope to reach
    something the ceiling never carried is wasted work.
    """
    audit = capture_audit()
    run = _run(
        user={TOOL, "echo"}, ceiling={"echo"}, requested={"echo"}, registry=_registry(), audit=audit
    )

    result = invoke_tool(run, TOOL, {"path": "m.tf", "content": "x"})

    assert not result.allowed
    assert result.reason_code == "out_of_scope"
    denials = [e for e in audit.all_entries() if e.payload.get("excluded_by")]
    assert denials, "the trail must carry which bound refused, not only that one did"
    assert denials[-1].payload["excluded_by"] == OUTSIDE_CEILING


def test_row_a2_layer_three_outside_task_scope_names_the_task_scope() -> None:
    """The ceiling permits it and this run did not ask — a dispatch fact, not a governance one."""
    audit = capture_audit()
    run = _run(
        user={TOOL, "echo"},
        ceiling={TOOL, "echo"},
        requested={"echo"},
        registry=_registry(),
        audit=audit,
    )

    result = invoke_tool(run, TOOL, {"path": "m.tf", "content": "x"})

    assert not result.allowed
    denials = [e for e in audit.all_entries() if e.payload.get("excluded_by")]
    assert denials[-1].payload["excluded_by"] == OUTSIDE_TASK_SCOPE


def test_row_a2_the_three_layers_are_mutually_distinguishable() -> None:
    """The assertion the feature owes: an operator tells them apart from the record alone."""
    unknown_audit, ceiling_audit, scope_audit = (
        capture_audit(),
        capture_audit(),
        capture_audit(),
    )
    invoke_tool(
        _run(
            user={TOOL},
            ceiling={TOOL},
            requested={TOOL},
            registry=ToolRegistry(),
            audit=unknown_audit,
        ),
        TOOL,
        {},
    )
    invoke_tool(
        _run(
            user={TOOL, "echo"},
            ceiling={"echo"},
            requested={"echo"},
            registry=_registry(),
            audit=ceiling_audit,
        ),
        TOOL,
        {},
    )
    invoke_tool(
        _run(
            user={TOOL, "echo"},
            ceiling={TOOL, "echo"},
            requested={"echo"},
            registry=_registry(),
            audit=scope_audit,
        ),
        TOOL,
        {},
    )

    def _signature(audit: InMemoryAuditSink) -> tuple[str, str]:
        denials = [e for e in audit.all_entries() if e.payload.get("outcome") == "deny"]
        last = denials[-1].payload
        return last.get("reason_code", ""), last.get("excluded_by", "")

    signatures = {_signature(unknown_audit), _signature(ceiling_audit), _signature(scope_audit)}
    assert len(signatures) == 3, (
        f"the three refusal layers must be distinguishable from the record alone; got "
        f"{sorted(signatures)}"
    )


def test_an_unexplained_exclusion_degrades_rather_than_guesses() -> None:
    """Fail-closed on the explanation, not only on the decision.

    A run whose authority was supplied rather than manufactured has no terms to have compared.
    The record then carries no `excluded_by` at all — a confident wrong signpost is worse than
    the honest absence of one.
    """
    audit = capture_audit()
    run = _run(
        user={TOOL, "echo"}, ceiling={"echo"}, requested={"echo"}, registry=_registry(), audit=audit
    )
    run.authority_exclusions = {}

    result = invoke_tool(run, TOOL, {"path": "m.tf", "content": "x"})

    assert not result.allowed
    assert result.reason_code == "out_of_scope"
    assert all("excluded_by" not in e.payload for e in audit.all_entries())
