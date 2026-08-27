# SPDX-License-Identifier: Apache-2.0
"""V2, V3, V4 — the refusal in the pipeline, and the proof it can lose (042, US2).

**V3 is the row this file exists for.** Every other row here asserts that a protected policy
refuses; V3 asserts that the refusal is doing the work. It builds the same run **without** the
hook registered and requires the call to succeed — so if a future edit unregisters the hook,
detaches it from `GOVERNANCE`, or narrows it into irrelevance, this row fails while the rest
stay green. A safety case that cannot lose has not been tested; it has been asserted.

**Why the hook and not only the request check.** `test_policy_protected.py` refuses on the
policy a request NAMES. This refuses on what a call actually CARRIES, which is the difference
between a run that asked wrongly and a run that changed its mind — the second being the one a
planted instruction produces.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.audit.sink import InMemoryAuditSink
from core.authority.types import AuthorityScope
from core.hooks.types import CapabilityKind, HookDecision, HookPhase, HookRegistration
from core.registry.memory import ToolRegistry
from core.run import GovernedRun, start_governed_run
from core.tools.invoke import invoke_tool
from surfaces.dispatch.policy_authoring import (
    POLICY_WRITING_TOOLS,
    ProtectedSet,
    protected_policy_hook,
)
from tests.harness.fake_identity_fabric import fake_identity_fabric
from tests.harness.frozen_clock import frozen_clock

#: Declared because the repo requires it, and the declaration is the honest one: authority is
#: resolved through the fake so these rows can hold EVERY term fixed but the hook registration
#: — same ceiling, same scope, same call. V3's whole claim is that one registration is the
#: difference between refused and written, and a production fabric would vary the ceiling
#: alongside it, leaving "which one refused" unanswerable.
FAKE_FABRIC_IS_FAULT_INJECTION = (
    "The ceiling is held constant so the ONLY variable is whether the 042 governance hook is "
    "registered. V3 asserts the call succeeds without it; that comparison is meaningless if "
    "authority resolution can differ between the two runs."
)

DEFINITION = "authoring-agent"
TOOL = "author_file"
PROTECTED = ProtectedSet(names=frozenset({"agent-ceiling", "authoring-publisher"}))


def _registry() -> tuple[ToolRegistry, list[dict[str, Any]]]:
    """A registry whose handler RECORDS rather than acts.

    The calls list is what makes "refused before it happened" assertable: a row that only
    checked the decision could not tell a refusal from a refusal that arrived too late.
    """
    calls: list[dict[str, Any]] = []
    registry = ToolRegistry()

    def _handler(arguments: Mapping[str, Any]) -> dict[str, Any]:
        calls.append(dict(arguments))
        return {"written": True}

    for name in sorted(POLICY_WRITING_TOOLS):
        registry.register(name=name, handler=_handler, repeatable=True)
    return registry, calls


def _run(registry: ToolRegistry, audit: InMemoryAuditSink, *, hooked: bool) -> GovernedRun:
    """The run, with the 042 hook registered or deliberately absent.

    `hooked=False` is the rigged-off construction V3 drives — everything identical but the
    one registration, in one process, because there is no pre-042 tree to check out (040's
    M3 recorded that trap and 041's harness took the same shape).
    """
    tools = set(POLICY_WRITING_TOOLS)
    hooks: list[HookRegistration] = [protected_policy_hook(PROTECTED)] if hooked else []
    return start_governed_run(
        agent_definition_id=DEFINITION,
        correlation_id="corr-042-hook",
        subject_user_id="user-1",
        requested_scope=AuthorityScope(tool_names=frozenset(tools), product_actions=frozenset()),
        identity_fabric=fake_identity_fabric(
            tool_names=tools, product_actions=set(), ceiling_tools=tools, ceiling_actions=set()
        ),
        clock=frozen_clock(),
        registry=registry,
        audit_sink=audit,
        hooks=hooks,
    )


def test_row_v2_a_call_naming_a_trust_fabric_policy_is_refused_in_the_pipeline() -> None:
    """V2 — the model tried anyway, and the act refused (FR-004, US2-3).

    The guarantee must not rest on the model not trying, which is why this drives the call
    rather than the request.
    """
    registry, calls = _registry()
    audit = InMemoryAuditSink()

    result = invoke_tool(_run(registry, audit, hooked=True), TOOL, {"policy_name": "agent-ceiling"})

    assert not result.allowed
    assert result.reason_code == "policy_protected"
    assert not calls, "refused BEFORE the handler ran; a later refusal has already written"


def test_row_v2_the_attempt_is_recorded_by_the_pipeline() -> None:
    """FR-005's recording, and it is the ENGINE's rather than the handler's.

    Every PRE decision is appended with its hook name, outcome and reason code before the
    deny propagates. A handler writing its own event would file the same refusal twice and
    invite a reader to think they were two attempts.
    """
    registry, _ = _registry()
    audit = InMemoryAuditSink()

    invoke_tool(_run(registry, audit, hooked=True), TOOL, {"policy_name": "agent-ceiling"})

    decisions = [
        entry.payload
        for entry in audit.all_entries()
        if entry.payload.get("hook_name") == "policy_protected"
    ]
    assert decisions, "a boundary a caller can probe without trace is not a boundary"
    assert decisions[-1]["outcome"] == "deny"
    assert decisions[-1]["reason_code"] == "policy_protected"
    assert decisions[-1]["capability_kind"] == str(CapabilityKind.GOVERNANCE), (
        "GOVERNANCE runs first among co-resident capabilities — Principle III's ordering, "
        "and the reason this is a registration rather than a function somebody calls"
    )


def test_row_v3_the_safety_case_can_lose() -> None:
    """V3 — **the row that makes every other row in this file mean something** (SC-003).

    Identical run, identical call, hook not registered: the write goes through. If this ever
    stops passing, the refusal above is being produced by something other than the hook —
    and the thing V3 is protecting has quietly moved somewhere nobody is watching.
    """
    registry, calls = _registry()
    audit = InMemoryAuditSink()

    result = invoke_tool(
        _run(registry, audit, hooked=False), TOOL, {"policy_name": "agent-ceiling"}
    )

    assert result.allowed, (
        "with the 042 hook unregistered this call MUST succeed. If it refuses anyway, the "
        "protection is coming from somewhere this feature does not control, and removing "
        "the hook would silently remove nothing — which is a gate that cannot fail"
    )
    assert calls == [{"policy_name": "agent-ceiling"}]


def test_row_v2_the_measurement_namespace_cannot_be_named_by_a_caller() -> None:
    """FR-020 at the call site: scratch names are derived from the run, never supplied."""
    registry, calls = _registry()
    audit = InMemoryAuditSink()

    result = invoke_tool(
        _run(registry, audit, hooked=True),
        "vault_policy_impact",
        {"target_policy": "scratch-agent-corr-042-hook-proposed"},
    )

    assert not result.allowed
    assert result.reason_code == "scratch_name_forged"
    assert not calls


def test_row_v2_every_argument_a_policy_name_can_arrive_in_is_checked() -> None:
    """One spelling checked and another not is a hook with a documented bypass."""
    for argument in ("policy_name", "target_policy", "name"):
        registry, calls = _registry()
        result = invoke_tool(
            _run(registry, InMemoryAuditSink(), hooked=True),
            TOOL,
            {argument: "authoring-publisher"},
        )
        assert not result.allowed, f"a policy name in {argument!r} passed the hook"
        assert not calls


def test_row_v2_an_unprotected_policy_passes_the_hook() -> None:
    """The hook narrows; it does not forbid. Without this row it could refuse everything."""
    registry, calls = _registry()

    result = invoke_tool(
        _run(registry, InMemoryAuditSink(), hooked=True),
        TOOL,
        {"policy_name": "payments-app-read"},
    )

    assert result.allowed
    assert calls == [{"policy_name": "payments-app-read"}]


def test_row_v2_a_tool_outside_the_policy_set_is_not_inspected() -> None:
    """`read_subject` analysing a repository that MENTIONS `agent-ceiling` is not an attempt.

    A hook that scanned every tool's arguments for protected names would refuse a run for
    reading a comment — over-refusal that reads as vigilance and makes the feature unusable
    on exactly the repositories it exists for.
    """
    registry, calls = _registry()
    registry.register(name="read_subject", handler=lambda a: {"content": str(a)}, repeatable=True)
    tools = {*POLICY_WRITING_TOOLS, "read_subject"}
    run = start_governed_run(
        agent_definition_id=DEFINITION,
        correlation_id="corr-042-hook",
        subject_user_id="user-1",
        requested_scope=AuthorityScope(tool_names=frozenset(tools), product_actions=frozenset()),
        identity_fabric=fake_identity_fabric(
            tool_names=tools, product_actions=set(), ceiling_tools=tools, ceiling_actions=set()
        ),
        clock=frozen_clock(),
        registry=registry,
        audit_sink=InMemoryAuditSink(),
        hooks=[protected_policy_hook(PROTECTED)],
    )

    result = invoke_tool(run, "read_subject", {"path": "policies/agent-ceiling.hcl"})

    assert result.allowed


def test_row_v2_a_hook_that_raises_denies_rather_than_allowing() -> None:
    """[GATE:fail-closed] Principle III's core demand, asserted rather than assumed.

    The shipped hook raises nothing, so this drives a deliberately broken variant registered
    the same way. The property belongs to the engine — a handler that raises is caught and
    turned into a deny — and this row is what stops that being a docstring claim about code
    042 depends on and does not own.
    """

    def _explodes(ctx: Any) -> HookDecision:
        raise RuntimeError("the protected set went away mid-call")

    registry, calls = _registry()
    tools = set(POLICY_WRITING_TOOLS)
    run = start_governed_run(
        agent_definition_id=DEFINITION,
        correlation_id="corr-042-hook",
        subject_user_id="user-1",
        requested_scope=AuthorityScope(tool_names=frozenset(tools), product_actions=frozenset()),
        identity_fabric=fake_identity_fabric(
            tool_names=tools, product_actions=set(), ceiling_tools=tools, ceiling_actions=set()
        ),
        clock=frozen_clock(),
        registry=registry,
        audit_sink=InMemoryAuditSink(),
        hooks=[
            HookRegistration(
                name="policy_protected",
                phase=HookPhase.PRE,
                capability_kind=CapabilityKind.GOVERNANCE,
                handler=_explodes,
            )
        ],
    )

    result = invoke_tool(run, TOOL, {"policy_name": "payments-app-read"})

    assert not result.allowed, (
        "a governance hook that fails must deny. An allow-on-exception path would mean the "
        "protected set becoming unreadable mid-run silently unprotects the platform"
    )
    assert not calls


# --------------------------------------------------------- #226: a run id is not a claim

#: The run every row below actually is. `_run` builds it with this correlation id, and
#: `GovernedRun.run_id` defaults to the correlation id.
OWN_RUN = "corr-042-hook"

#: Another run's id. Nothing about it is special — that is the point.
FOREIGN_RUN = "corr-some-other-build"


def test_a_call_claiming_another_runs_id_is_refused() -> None:
    """ISSUE #226 — the route around 042's own refusal.

    `handlers.py` deliberately refuses a `scratch_name` argument as "a caller choosing what to
    overwrite", and then derives that name from `run_id` — which IS an argument. Naming another
    run's id reaches that run's measurement workspace, and the wildcard grant in `scratch.tf`
    permits acting on it. Demonstrated against the live enclave before this guard existed:
    read 200, overwrite 200, delete 204.
    """
    registry, calls = _registry()
    audit = InMemoryAuditSink()

    result = invoke_tool(
        _run(registry, audit, hooked=True), TOOL, {"run_id": FOREIGN_RUN, "path": "main.tf"}
    )

    assert not result.allowed
    assert result.reason_code == "run_id_forged"
    assert not calls, "refused BEFORE the handler ran; a later refusal has already written"


def test_a_call_using_its_own_run_id_is_allowed() -> None:
    """THE CONTROL, and the row that stops the guard being a blanket refusal.

    Without this, denying every `run_id` would satisfy the row above and break the feature
    the argument exists for.
    """
    registry, calls = _registry()
    audit = InMemoryAuditSink()

    result = invoke_tool(
        _run(registry, audit, hooked=True), TOOL, {"run_id": OWN_RUN, "path": "main.tf"}
    )

    assert result.allowed, result.reason_code
    assert calls, "the handler must still run for a call acting as itself"


def test_a_call_carrying_no_run_id_is_untouched() -> None:
    """The guard binds on a claim, not on its absence. Most calls carry no run id at all."""
    registry, calls = _registry()
    audit = InMemoryAuditSink()

    result = invoke_tool(_run(registry, audit, hooked=True), TOOL, {"path": "main.tf"})

    assert result.allowed, result.reason_code
    assert calls


def test_the_identity_guard_can_lose() -> None:
    """V3's shape for #226. Identical run, identical call, hook not registered.

    If this ever stops passing, the refusal above is coming from somewhere this fix does not
    control — and removing the hook would silently stop protecting anything.
    """
    registry, calls = _registry()
    audit = InMemoryAuditSink()

    result = invoke_tool(
        _run(registry, audit, hooked=False), TOOL, {"run_id": FOREIGN_RUN, "path": "main.tf"}
    )

    assert result.allowed, (
        "with the hook unregistered this call MUST succeed — that is what makes the refusal "
        "above attributable to the hook rather than to something else in the pipeline"
    )
    assert calls


def test_the_guard_covers_a_tool_outside_the_policy_writing_set() -> None:
    """A run id is an IDENTITY claim, not a policy name, so the check runs on every tool.

    `_POLICY_ARGUMENTS` is deliberately scoped to `POLICY_WRITING_TOOLS`, because a hook
    reading `read_subject`'s file contents for policy names would refuse a run for analysing a
    repository that mentions `agent-ceiling` in a comment. That reasoning does not transfer:
    no tool has a legitimate reason to act as a run other than the one calling it, and a
    future tool deriving anything from `run_id` inherits this guard rather than needing to be
    added to a set somebody must remember.
    """
    calls: list[dict[str, Any]] = []
    registry = ToolRegistry()

    def _record(arguments: Mapping[str, Any]) -> dict[str, Any]:
        calls.append(dict(arguments))
        return {"ok": True}

    registry.register(name="unrelated_tool", handler=_record, repeatable=True)
    tools = {"unrelated_tool"}
    run = start_governed_run(
        agent_definition_id=DEFINITION,
        correlation_id=OWN_RUN,
        subject_user_id="user-1",
        requested_scope=AuthorityScope(tool_names=frozenset(tools), product_actions=frozenset()),
        identity_fabric=fake_identity_fabric(
            tool_names=tools, product_actions=set(), ceiling_tools=tools, ceiling_actions=set()
        ),
        clock=frozen_clock(),
        registry=registry,
        audit_sink=InMemoryAuditSink(),
        hooks=[protected_policy_hook(PROTECTED)],
    )

    result = invoke_tool(run, "unrelated_tool", {"run_id": FOREIGN_RUN})

    assert not result.allowed
    assert result.reason_code == "run_id_forged"
    assert not calls


def test_an_unestablishable_identity_refuses_rather_than_allows() -> None:
    """FAIL-CLOSED. A guard that allowed on absence would be removable by arranging for the
    run to be missing, rather than by deleting the check — which is the failure mode
    Principle III exists to refuse.
    """
    from core.hooks.types import HookContext
    from core.hooks.types import HookPhase as _Phase
    from surfaces.dispatch.policy_authoring import _refuse_a_foreign_run

    decision = _refuse_a_foreign_run(
        HookContext(
            correlation_id="",
            tool_name=TOOL,
            arguments={"run_id": FOREIGN_RUN},
            phase=_Phase.PRE,
            run=None,
        )
    )
    assert decision is not None
    assert decision.outcome == "deny"
    assert decision.reason_code == "run_identity_unavailable"
