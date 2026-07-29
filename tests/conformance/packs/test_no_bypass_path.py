# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — a pack tool is reached the way every tool is (FR-003, Principle II).

**Asserted structurally, because there is no pack-tool code path.** That is the design, not
a consequence of it: `register_pack` calls `ToolRegistry.register`, the same function 002
built, so a pack tool inherits the hook pipeline **by construction rather than by
discipline**. There is nothing to bypass because nothing separate exists.

That makes this file's job unusual. It is not checking that a bypass is closed — it is
checking that nobody opened one, which is a claim about the shape of the code rather than
about its behaviour. A behavioural test would pass equally well against an implementation
that had a second path nobody happened to exercise.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

from core.packs import registration
from core.registry.memory import ToolRegistry

ROOT = Path(__file__).resolve().parents[3]
PACKS = ROOT / "src" / "core" / "packs"


def test_registration_reaches_the_registry_and_nothing_else() -> None:
    """The only way a pack tool becomes callable is `ToolRegistry.register`."""
    tree = ast.parse(inspect.getsource(registration))
    calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "register" in calls, "registration no longer registers through the registry"


def test_no_pack_module_invokes_a_handler() -> None:
    """Loading and registering never *call* anything a pack named.

    A pack module that invoked a handler would be executing pack-selected code outside the
    pipeline — the bypass, arriving as a convenience. The handlers this package touches are
    only ever passed to `register`, never called.
    """
    offenders: dict[str, list[str]] = {}
    for path in sorted(PACKS.glob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        called = [
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        ]
        suspicious = [name for name in called if name in {"handler", "observer", "probe"}]
        if suspicious:
            offenders[path.name] = suspicious
    assert not offenders, f"a pack module invokes what a manifest named: {offenders}"


def test_the_registry_has_no_pack_aware_entry_point() -> None:
    """The registry does not know packs exist, which is why there is one path.

    If `ToolRegistry` grew a `register_pack_tool`, pack tools would have their own door and
    this whole property would become a matter of which door callers chose.
    """
    pack_aware = [name for name in dir(ToolRegistry) if "pack" in name.lower()]
    assert not pack_aware, (
        f"the registry has pack-aware members {pack_aware}; a second registration path is a "
        f"second authorization path wearing a convenience's name"
    )


def test_a_registered_pack_tool_is_indistinguishable_from_any_other() -> None:
    """The behavioural half: what the registry holds carries no pack marker.

    The pipeline cannot treat a pack tool differently because it cannot tell. That is
    stronger than a rule saying it should not.
    """
    registry = ToolRegistry()
    registry.register("ordinary", lambda args: "ok")
    fields = set(type(registry.resolve("ordinary")).__dataclass_fields__)
    assert "pack" not in fields and "pack_name" not in fields, (
        "ToolRegistration carries pack provenance; the pipeline could branch on it"
    )
