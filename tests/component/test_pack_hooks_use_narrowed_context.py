# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — a pack hook does not read `HookContext.run`.

That field carries its own warning: *"Populated for built-in governance hooks only.
Third-party hooks must not depend on this attribute; the hook context narrows further before
the Hook SDK seam ships."*

Pack hooks are third-party and they arrive **before** that seam. So a pack depending on
`run` today is a pack the seam breaks tomorrow — and it would break at the worst moment,
when a hook that had been silently reading a `GovernedRun` starts receiving something
narrower.

Asserted statically over pack hook handlers, because a runtime check only catches the branch
that runs. A hook reading `ctx.run` inside an `if` nobody triggered in a test still ships.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from pathlib import Path
from typing import Any

from core.hooks.types import HookContext, HookDecision

ROOT = Path(__file__).resolve().parents[2]


def _reads_run(func: Any) -> bool:
    """Whether a handler's source ever reaches `.run` on its context parameter."""
    # `textwrap.dedent`, not `inspect.cleandoc`: cleandoc strips the body's indentation
    # relative to the docstring, which turns a valid function into an IndentationError.
    tree = ast.parse(textwrap.dedent(inspect.getsource(func)))
    fn = next(
        (n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))), None
    )
    if fn is None:
        return False
    if not fn.args.args:
        return False
    ctx_name = fn.args.args[0].arg
    return any(
        isinstance(node, ast.Attribute)
        and node.attr == "run"
        and isinstance(node.value, ast.Name)
        and node.value.id == ctx_name
        for node in ast.walk(fn)
    )


def _pack_hook(ctx: HookContext) -> HookDecision:
    """A well-behaved pack hook: everything it needs is on the narrowed context."""
    if ctx.tool_name.startswith("vault_") and "path" not in ctx.arguments:
        return HookDecision(outcome="deny", reason_code="not_permitted", message="path required")
    return HookDecision(outcome="allow", reason_code="ok")


def _badly_behaved(ctx: HookContext) -> HookDecision:
    """What this row exists to catch — reaching for the run the seam will take away."""
    if ctx.run is not None and ctx.run.state is not None:
        return HookDecision(outcome="allow", reason_code="ok")
    return HookDecision(outcome="deny", reason_code="internal_error")


def test_a_pack_hook_does_not_read_the_run() -> None:
    assert _reads_run(_pack_hook) is False


def test_the_check_fires_on_a_hook_that_does() -> None:
    """The positive control. Without it this file asserts that a function nobody wrote
    badly was not written badly."""
    assert _reads_run(_badly_behaved) is True


def test_the_field_still_carries_its_warning() -> None:
    """The contract this row enforces lives in a comment, so the comment is asserted.

    If someone removes the warning — because the seam shipped, or because it looked like
    stale advice — this fails and the decision surfaces instead of the rule quietly
    evaporating.
    """
    source = (ROOT / "src" / "core" / "hooks" / "types.py").read_text()
    # The clause that fits on one line. The full sentence wraps across a comment
    # continuation, so matching it whole would fail on a reflow that changed nothing.
    assert "Third-party hooks must not depend on" in source
    assert "the hook context narrows further" in source


def test_everything_a_pack_hook_needs_is_on_the_narrowed_context() -> None:
    """The positive half: the rule is followable.

    A prohibition against reading `run` would be unreasonable if the remaining context could
    not answer a hook's questions. Tool name, arguments, phase, and correlation id are what
    a pack hook decides on, and they are all here.
    """
    fields = set(HookContext.__dataclass_fields__)
    assert {"correlation_id", "tool_name", "arguments", "phase"} <= fields
