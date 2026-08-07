# SPDX-License-Identifier: Apache-2.0
"""C19, C20, C22 — an agent cannot reach the console (044, US4).

**These land in the same phase as the write route, not after it.** A console that can change
governance records while the dispatched-run exclusion is "next" is the platform being
configurable by the thing it governs for the length of that gap. 042 made the same argument
about policy authoring; this is that argument one surface over.

**C20 is the row that makes the other two mean something.** It builds the same registry with
the exclusion removed and requires the call to succeed. If it ever stops passing, the
protection is coming from somewhere this feature does not control — and removing the exclusion
would silently remove nothing, which is a gate that cannot fail.

**C22 turns an absence into a checked fact.** 043 shipped a gate the API emitted and MCP did
not, and only the parity row caught it. The console is portal-only by decision (clarify Q1), so
MCP carrying no configuration verb is a property somebody must assert rather than notice.
"""

from __future__ import annotations

from typing import Any

from core.audit.sink import InMemoryAuditSink
from core.authority.types import AuthorityScope
from core.registry.memory import ToolRegistry
from core.run import start_governed_run
from core.tools.invoke import invoke_tool
from surfaces.api.console import ADMIN_ROLE
from surfaces.toolset import build_registry, known_tools
from tests.harness.fake_identity_fabric import fake_identity_fabric
from tests.harness.frozen_clock import frozen_clock

#: Declared because the repo requires it: authority is resolved through the fake so the ceiling
#: is the only variable. C20 compares a registry with the exclusion and one without, and a
#: production fabric would vary authority alongside it — leaving "which one refused" unanswerable.
FAKE_FABRIC_IS_FAULT_INJECTION = (
    "The registry's contents are the injected variable. Everything else — ceiling, scope, call "
    "— is held identical, so a refusal can only be the exclusion's doing."
)

#: What a run would have to resolve to reach configuration. None of these is a registered tool,
#: and that is the exclusion: there is no name a ceiling could carry.
CONSOLE_TOOL_NAMES = (
    "console_configuration",
    "console_change",
    "read_configuration",
    "request_change",
)


def _run(registry: ToolRegistry, ceiling: set[str]) -> Any:
    return start_governed_run(
        agent_definition_id="authoring-agent",
        correlation_id="corr-044-exclusion",
        subject_user_id="user-1",
        requested_scope=AuthorityScope(tool_names=frozenset(ceiling), product_actions=frozenset()),
        identity_fabric=fake_identity_fabric(
            tool_names=set(ceiling),
            product_actions=set(),
            ceiling_tools=set(ceiling),
            ceiling_actions=set(),
        ),
        clock=frozen_clock(),
        registry=registry,
        audit_sink=InMemoryAuditSink(),
    )


def test_row_c19_no_console_operation_is_a_tool_a_run_can_resolve() -> None:
    """C19 — the exclusion is structural: there is no name for a ceiling to carry.

    Not a refusal a handler performs, and not a rule a model is asked to follow. The
    vocabulary a ceiling may name is derived from what registered, and nothing registers
    these — so a dispatched run cannot express the request, let alone make it.
    """
    registry, _ = build_registry(packs=["vault", "terraform"])
    vocabulary = known_tools(registry)

    for name in CONSOLE_TOOL_NAMES:
        assert name not in vocabulary, (
            f"{name!r} is a name a ceiling could carry. The console is a person's surface; a "
            f"dispatched run reaching it is the platform being configurable by the thing it "
            f"governs (Principle IV)."
        )


def test_row_c19_a_run_naming_a_console_tool_is_refused() -> None:
    """The same property from the other end: asking produces a refusal, not an action."""
    registry, _ = build_registry(packs=["vault"])
    run = _run(registry, {"vault_read"})

    result = invoke_tool(run, "console_change", {"record": "ask-bindings"})

    assert not result.allowed


def test_row_c20_the_exclusion_can_lose() -> None:
    """C20 — **the row that makes every other row in this file mean something**.

    The exclusion is that nothing registers a console tool. So the rigged-on construction is a
    registry where something does: if C19's scenario then succeeds, the refusal above was the
    absence of a registration and not an accident of naming. If this ever fails, the
    protection has moved somewhere this feature does not control.
    """
    registry, _ = build_registry(packs=["vault"])
    registry.register(
        name="console_change",
        handler=lambda arguments: {"applied": True},
        repeatable=True,
    )

    run = _run(registry, {"console_change"})
    result = invoke_tool(run, "console_change", {"record": "ask-bindings"})

    assert result.allowed, (
        "with a console tool registered, the call MUST succeed. If it refuses anyway, the "
        "exclusion asserted above is being produced by something else — and removing the "
        "real protection would silently remove nothing."
    )


def test_row_c22_mcp_carries_no_configuration_verb() -> None:
    """C22 — the absence as a checked fact (clarify Q1).

    043 shipped a gate the API emitted and MCP did not, and only the parity row caught it.
    Here the asymmetry is deliberate — the console is portal-only, so no parity is owed — but
    a deliberate absence and an overlooked one look identical in a diff. This is what
    distinguishes them.
    """
    import inspect

    from surfaces.mcp import transport

    source = inspect.getsource(transport)

    for verb in ("console", "configuration", "/console"):
        assert f'"{verb}"' not in source, (
            f"MCP's operation table names {verb!r}. The console is a person's surface reached "
            f"from the portal; an agent-facing transport with a governance-write path would "
            f"be US4's exclusion and its violation in the same feature."
        )


def test_the_console_role_is_not_something_a_run_can_hold() -> None:
    """A dispatched run authenticates as a workload, and `admin` is a person's role.

    Belt and braces with the registry exclusion: even if a console operation somehow became
    reachable, the role gate is a second refusal — and the two fail independently.
    """
    registry, _ = build_registry(packs=["vault"])
    run = _run(registry, {"vault_read"})

    granted: frozenset[str] = getattr(run, "roles", frozenset()) or frozenset()
    assert ADMIN_ROLE not in granted
