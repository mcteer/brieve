# SPDX-License-Identifier: Apache-2.0
"""GATE:determinism — FR-012, asserted rather than assumed.

Two checks, because neither alone is sufficient:

(a) **Direct-import scan** over test module *source*. Deliberately not a
    ``sys.modules`` check: ``pydantic-ai-slim`` pulls an HTTP client in
    transitively, so a runtime check would fail on every adapter test while
    proving nothing about what the tests themselves reach for.

(b) **Model resolution.** Adapter tests must build agents with stub models. This
    is what actually prevents a live call; (a) cannot, since a live call needs no
    new import if a client is already reachable.

Known limit: this catches *reaching for* a live client, not a call made through
one already imported. Closing that needs a socket-blocking plugin, which adds a
dependency to a regulated tree — escalate only if a live call ever slips through
(specs/004-primary-adapter/research.md).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from tests.harness.adapter_fixtures import scripted_tool_model

TESTS_ROOT = Path(__file__).resolve().parents[1]

#: Clients that would reach a live model, IdP, Vault, or product API.
DENIED_IMPORTS = frozenset(
    {
        "httpx",
        "httpcore",
        "requests",
        "urllib.request",
        "urllib3",
        "aiohttp",
        "hvac",
        "openai",
        "anthropic",
        "google.generativeai",
        "boto3",
    }
)


def _imported_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module)
    return names


def test_no_test_module_imports_a_live_client() -> None:
    offenders: list[str] = []
    for path in TESTS_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for name in _imported_names(tree):
            root = name.split(".")[0]
            if name in DENIED_IMPORTS or root in DENIED_IMPORTS:
                offenders.append(f"{path.relative_to(TESTS_ROOT)}: {name}")
    assert not offenders, (
        f"test modules reach for live clients: {offenders}. "
        "Tests use stub models and harness fakes only (FR-012)."
    )


def test_scripted_model_is_a_stub_not_a_provider() -> None:
    """The fixture model resolves to a local function, not a provider client."""
    model = scripted_tool_model([("echo", {})])
    assert type(model).__name__ == "FunctionModel"
    assert "function" in type(model).__module__


@pytest.mark.anyio
async def test_scripted_model_needs_no_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """A run completes with every provider credential removed from the environment."""
    for var in (
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "VAULT_TOKEN",
    ):
        monkeypatch.delenv(var, raising=False)

    from tests.harness.adapter_fixtures import CountingHandler, governed_agent_fixture

    handler = CountingHandler()
    agent, deps, handlers, _audit = governed_agent_fixture(
        tool_calls=[("echo", {})],
        registry_tools={"echo": handler},
    )

    await agent.run("go", deps=deps)

    assert handlers["echo"].call_count == 1
