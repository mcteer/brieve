# SPDX-License-Identifier: Apache-2.0
"""Row: no registered route reaches a tool body (FR-007, SC-005).

The API exposes no direct tool invocation. A caller reaching a tool through the API would
be acting *beside* the agent rather than through it — a second path to the governed core,
which is the shape Principle II exists to prevent.

**This walks the application's registered routes and follows what each one calls.** It is
not a text search, and the difference is the whole value: a grep passes a module that
mentions ``invoke_tool`` in a docstring and misses a route that reaches a tool through an
alias or a helper. This repository has had a check match prose three times; here the
mistake would be worse, because the check would report the platform's central containment
property as holding while a bypass route sat in the app.
"""

from __future__ import annotations

import ast
import inspect
from types import FunctionType
from typing import Any

from fastapi import FastAPI

from surfaces.api.app import registered_routes
from tests.harness.api_fixtures import surface_under_test

#: Anything that executes a tool. Reached directly or via any alias.
TOOL_ENTRYPOINTS = {"invoke_tool"}

#: Depth is bounded but generous. A bypass hidden four calls deep is still a bypass; a
#: bound stops the walk cycling through the framework's own machinery.
MAX_DEPTH = 6


def _called_names(func: Any) -> set[str]:
    try:
        source = inspect.getsource(func)
    except (OSError, TypeError):
        return set()
    try:
        tree = ast.parse(inspect.cleandoc(source))
    except SyntaxError:
        try:
            tree = ast.parse(_dedent(source))
        except SyntaxError:
            return set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            target = node.func
            if isinstance(target, ast.Name):
                names.add(target.id)
            elif isinstance(target, ast.Attribute):
                names.add(target.attr)
    return names


def _dedent(source: str) -> str:
    import textwrap

    return textwrap.dedent(source)


def _reachable_calls(func: Any, depth: int = 0, seen: set[int] | None = None) -> set[str]:
    """Every function name reachable from ``func``, following resolvable globals.

    Following globals is what catches the alias case: a route calling ``_helper()`` where
    ``_helper`` calls ``invoke_tool`` names neither entrypoint in its own body.
    """
    seen = seen if seen is not None else set()
    if depth > MAX_DEPTH or id(func) in seen:
        return set()
    seen.add(id(func))

    names = _called_names(func)
    reachable = set(names)

    # Globals AND closure cells. A helper defined alongside the route is a freevar, not a
    # global — and that is precisely how a bypass would be written, so resolving only
    # globals would miss the realistic case while passing the contrived one.
    namespace: dict[str, Any] = dict(getattr(func, "__globals__", {}))
    code = getattr(func, "__code__", None)
    closure = getattr(func, "__closure__", None)
    if code is not None and closure:
        for name, cell in zip(code.co_freevars, closure, strict=False):
            try:
                namespace[name] = cell.cell_contents
            except ValueError:  # pragma: no cover - cell not yet bound
                continue

    for name in names:
        target = namespace.get(name)
        if isinstance(target, FunctionType):
            reachable |= _reachable_calls(target, depth + 1, seen)
    return reachable


def _tool_reaching_routes(app: FastAPI) -> list[str]:
    offenders = []
    for route in registered_routes(app):
        endpoint = route["endpoint"]
        if endpoint is None:
            continue
        if _reachable_calls(endpoint) & TOOL_ENTRYPOINTS:
            offenders.append(f"{route['methods']} {route['path']}")
    return offenders


def test_no_route_reaches_a_tool() -> None:
    app = surface_under_test().app
    assert _tool_reaching_routes(app) == []


def test_the_walk_actually_visits_routes() -> None:
    """Without this, an empty route list would make the assertion above vacuous."""
    app = surface_under_test().app
    paths = {r["path"] for r in registered_routes(app)}
    assert "/runs" in paths


def test_break_fixture_catches_a_tool_reached_through_an_alias() -> None:
    """Self-verifying break fixture (FR-014's discipline, 004's pattern).

    The bypass deliberately does **not** name ``invoke_tool`` in the route body. A checker
    satisfied by the literal name in the endpoint's own source would pass this, which is
    the failure mode the walk exists to close.
    """
    from fastapi import APIRouter

    def invoke_tool(*args: Any, **kwargs: Any) -> str:  # noqa: ARG001
        return "executed"

    def _run_the_thing() -> str:
        # One level of indirection, and a name that says nothing.
        return invoke_tool("echo", {})

    surface = surface_under_test()
    smuggled = APIRouter()

    @smuggled.post("/tools/echo")
    def call_echo() -> str:
        return _run_the_thing()

    surface.app.include_router(smuggled)

    offenders = _tool_reaching_routes(surface.app)
    assert offenders, "the walk failed to notice a tool reached through an alias"
    assert any("/tools/echo" in o for o in offenders)
