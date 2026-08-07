# SPDX-License-Identifier: Apache-2.0
"""GATE:no-secret-leak — SC-002, asserted as an absence (038, W3a).

SC-002 claims **100%, no unaccounted writes**. W1 asserts the positive: a write is a governed
decision. **A negative requirement cannot be proven by something passing**, so this enumerates
the filesystem-write surface in `core.authoring` and asserts `author_file`'s handler is the only
member — the same shape as `tests/conformance/packs/test_no_bypass_path.py`, which enumerates
the tool surface rather than trusting that no second path was added.

**Comments and docstrings are stripped before matching**, on the precedent this repository has
paid for five times: prose about writing is not a write, and these modules contain a great deal
of prose about writing.
"""

from __future__ import annotations

import ast
import pathlib

from tests.harness.source_reading import code_without_prose

AUTHORING = pathlib.Path(__file__).resolve().parents[2] / "src" / "core" / "authoring"

#: Calls that put bytes on disk. Attribute names rather than qualified paths, because
#: `path.write_text(...)` and `Path(p).write_text(...)` are the same act reached two ways.
#:
#: `rmtree` added by 041: deleting a tree is a write in every sense this check cares about, and
#: its absence meant the enumeration had a hole the day it was written. Nothing in the package
#: used it, so the hole was invisible rather than exploited.
WRITE_CALLS = frozenset(
    {"write_text", "write_bytes", "mkdir", "touch", "unlink", "rmdir", "rmtree"}
)

#: The one function permitted to write, and the one module it lives in. `mkdir` accompanies it
#: because a file cannot be written into a directory that does not exist — and the parent it
#: creates is inside the workspace, which `resolve_in_workspace` has already bounded.
#:
#: **Acquisition writes, and SC-002's claim survives it — but only because of where it runs.**
#: `acquisition.py` produces the subject checkout BEFORE dispatch, in the dispatching context.
#: No agent exists yet, nothing it writes is influenced by a model, and it never touches a
#: workspace or a subject tree the tier hands out — it *creates* the tree the tier will later
#: mount read-only. SC-002 is a claim about writes an agent can cause; this is a claim about
#: the platform preparing an input.
#:
#: That distinction is asserted rather than argued: `test_acquisition.py` drives acquisition
#: and checks every path it creates lies under the directory its caller named. An exemption
#: whose justification lives only in a comment is the shape ADR-0047 refuses.
PERMITTED = {
    ("tool.py", "FileAuthor.__call__"),
    ("acquisition.py", "acquire_subject"),
    ("acquisition.py", "release_subject"),
}


def _qualified_functions(path: pathlib.Path) -> list[tuple[str, ast.AST]]:
    """Every function in the module, named as `Class.method` or `function`."""
    tree = ast.parse(code_without_prose(path.read_text()), filename=str(path))
    out: list[tuple[str, ast.AST]] = []
    # The MODULE BODY, not `ast.walk` — walking yields a method twice, once as its class's child
    # and once on its own, so an exemption naming `FileAuthor.__call__` would miss the bare
    # `__call__` and the check would report its own permitted writer as an offender.
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            out += [
                (f"{node.name}.{child.name}", child)
                for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append((node.name, node))
    return out


def test_author_file_is_the_only_write_surface_in_authoring() -> None:
    """The absence SC-002 needs, enumerated rather than assumed."""
    offenders: list[str] = []
    for module in sorted(AUTHORING.glob("*.py")):
        for name, node in _qualified_functions(module):
            if (module.name, name) in PERMITTED:
                continue
            for inner in ast.walk(node):
                if (
                    isinstance(inner, ast.Call)
                    and isinstance(inner.func, ast.Attribute)
                    and inner.func.attr in WRITE_CALLS
                ):
                    offenders.append(f"{module.name}:{name} calls {inner.func.attr}")

    assert not offenders, (
        f"{offenders} write to the filesystem outside `author_file`'s handler. SC-002 claims "
        f"100% of writes are governed, and a second path would make that claim false while "
        f"every positive row still passed"
    )


def test_the_permitted_writer_still_exists() -> None:
    """An exemption for a function that has moved is an exemption that lies.

    The same discipline `test_every_allowlist_entry_still_needs_its_exemption` applies to the
    product-blindness allowlist: a stale entry silently widens the check it was narrowing.
    """
    for filename, qualified in PERMITTED:
        names = {name for name, _ in _qualified_functions(AUTHORING / filename)}
        assert qualified in names, (
            f"{filename} no longer defines {qualified}; the exemption names something that does "
            f"not exist, which means the check is narrower than it reads"
        )


def test_the_write_surface_is_bounded_before_it_writes() -> None:
    """The permitted writer resolves its path first, and the resolution refuses an escape.

    A write surface of one is only worth having if that one cannot be pointed anywhere.
    """
    source = code_without_prose((AUTHORING / "tool.py").read_text())
    call = source[source.index("class FileAuthor") :]
    assert "resolve_in_workspace" in call, (
        "the writer no longer resolves its path against the workspace; an unbounded single "
        "write surface is not better than several bounded ones"
    )
    assert call.index("resolve_in_workspace") < call.index("write_text"), (
        "the path is resolved after the write; resolution that happens later bounds nothing"
    )
