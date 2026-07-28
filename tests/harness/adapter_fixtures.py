# SPDX-License-Identifier: Apache-2.0
"""Adapter test fixtures — stub models and governed agent builders.

No live model, IdP, Vault, or product API is reachable from anything here
(FR-012). Model behaviour is scripted with ``FunctionModel``: it emits the tool
calls the test wants and then a final text response, so a run is deterministic
and needs no API key.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from pydantic_ai.messages import (
    ModelMessage,
    ModelResponse,
    TextPart,
    ToolCallPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.toolsets import FunctionToolset

from adapters.pydantic_ai.agent import build_governed_agent, start_adapter_run
from adapters.pydantic_ai.run_context import AdapterRunContext
from core.approvals import ApprovalHook
from core.authority.types import AuthorityScope
from core.durability import DurabilityProvider
from core.registry.memory import ToolRegistry
from tests.harness.capture_audit import capture_audit
from tests.harness.fake_identity_fabric import (
    DEFAULT_AGENT_DEFINITION_ID,
    FakeBrokeredMaterialSource,
    FakeIdentityFabric,
    fake_identity_fabric,
)
from tests.harness.frozen_clock import frozen_clock


class CountingHandler:
    """Registry tool body that records how many times it actually ran.

    Exposes ``call_count`` to match the existing harness convention, so
    ``assert_no_side_effect`` works against it unchanged.
    """

    def __init__(self, result: Any = "ok", *, raise_exc: Exception | None = None) -> None:
        self.call_count = 0
        self._result = result
        self._raise = raise_exc

    def __call__(self, arguments: Mapping[str, Any]) -> Any:
        self.call_count += 1
        if self._raise is not None:
            raise self._raise
        return self._result


def scripted_tool_model(
    calls: Sequence[tuple[str, dict[str, Any]]],
    *,
    final_text: str = "done",
) -> FunctionModel:
    """A model that issues ``calls`` in order, one per step, then stops.

    Deterministic by construction — no sampling, no network, no key.
    """
    remaining = list(calls)

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        if remaining:
            name, args = remaining.pop(0)
            return ModelResponse(parts=[ToolCallPart(tool_name=name, args=args)])
        return ModelResponse(parts=[TextPart(content=final_text)])

    return FunctionModel(respond)


def echo_toolset(tool_names: Iterable[str]) -> FunctionToolset[AdapterRunContext]:
    """Expose ``tool_names`` as framework tools.

    These supply the schema the model sees. The bodies here are never executed —
    ``GovernedToolset`` routes execution to ``invoke_tool``, so the core registry
    holds the real body. A body that *did* run would be an ungoverned call, which
    is what the mapping tests assert against.
    """
    toolset: FunctionToolset[AdapterRunContext] = FunctionToolset()
    for name in tool_names:

        def _never_called(payload: str = "") -> str:
            raise AssertionError(
                "framework tool body executed directly — the governed mapping was bypassed"
            )

        toolset.add_function(_never_called, name=name)
    return toolset


def governed_agent_fixture(
    *,
    tool_calls: Sequence[tuple[str, dict[str, Any]]],
    registry_tools: Mapping[str, CountingHandler] | None = None,
    framework_tools: Iterable[str] | None = None,
    subject_user_id: str = "user-1",
    agent_definition_id: str = DEFAULT_AGENT_DEFINITION_ID,
    correlation_id: str = "corr-adapter",
    scope_tools: Iterable[str] | None = None,
    scope_actions: Iterable[str] | None = None,
    fabric: FakeIdentityFabric | None = None,
    capabilities: Sequence[Any] | None = None,
    approval_hook: ApprovalHook | None = None,
    durability: DurabilityProvider | None = None,
    registry: ToolRegistry | None = None,
) -> tuple[Any, AdapterRunContext, dict[str, CountingHandler], Any]:
    """Build a governed agent, its deps, side-effect counters, and the audit sink."""
    handlers = dict(registry_tools) if registry_tools is not None else {"echo": CountingHandler()}
    reg = registry if registry is not None else ToolRegistry()
    if registry is None:
        for name, handler in handlers.items():
            reg.register(name, handler)

    tools = list(scope_tools) if scope_tools is not None else list(handlers)
    audit = capture_audit()
    identity = (
        fabric
        if fabric is not None
        else fake_identity_fabric(
            subject_user_id=subject_user_id,
            tool_names=set(tools),
            ceiling_tools=set(tools),
        )
    )

    deps = start_adapter_run(
        correlation_id=correlation_id,
        subject_user_id=subject_user_id,
        agent_definition_id=agent_definition_id,
        requested_scope=AuthorityScope(
            tool_names=frozenset(tools),
            product_actions=frozenset(scope_actions) if scope_actions is not None else frozenset(),
        ),
        identity_fabric=identity,
        registry=reg,
        clock=frozen_clock(),
        audit_sink=audit,
        approval_hook=approval_hook,
        durability=durability,
        # Brokering is unimplemented (ADR-0044); rows whose subject is the check in FRONT
        # of it need something here, or they refuse `broker_not_implemented` and stop
        # testing what they were written to test.
        brokered_material_source=FakeBrokeredMaterialSource(),
    )

    exposed = list(framework_tools) if framework_tools is not None else list(handlers)
    agent = build_governed_agent(
        scripted_tool_model(tool_calls),
        toolsets=[echo_toolset(exposed)],
        capabilities=capabilities,
    )
    return agent, deps, handlers, audit


def build_probe_capability(probe_log: list[str], *, label: str = "co-resident") -> Any:
    """A co-resident (non-governance) capability that records when it observed a call.

    It appends its own label *and* a snapshot of the governed run's probe log, so a
    test can assert governance had already admitted the call by the time this ran.
    Imported lazily so this module stays importable without the framework.
    """
    from pydantic_ai.capabilities.abstract import AbstractCapability

    class _ProbeCapability(AbstractCapability[AdapterRunContext]):
        async def wrap_tool_execute(
            self,
            ctx: Any,
            *,
            call: Any,
            tool_def: Any,
            args: Any,
            handler: Any,
        ) -> Any:
            deps = getattr(ctx, "deps", None)
            seen = list(deps.governed_run.probe_log) if deps is not None else []
            probe_log.append(f"{label}:saw={','.join(seen) or 'nothing'}")
            return await handler(args)

    return _ProbeCapability()


def build_failing_capability(*, message: str = "governance dependency unavailable") -> Any:
    """Capability whose tool-execute hook raises — used to prove fail-closed."""
    from pydantic_ai.capabilities.abstract import AbstractCapability

    class _FaultCapability(AbstractCapability[AdapterRunContext]):
        async def wrap_tool_execute(
            self,
            ctx: Any,
            *,
            call: Any,
            tool_def: Any,
            args: Any,
            handler: Any,
        ) -> Any:
            raise RuntimeError(message)

    return _FaultCapability()


__all__ = [
    "CountingHandler",
    "build_failing_capability",
    "build_probe_capability",
    "echo_toolset",
    "governed_agent_fixture",
    "scripted_tool_model",
]
