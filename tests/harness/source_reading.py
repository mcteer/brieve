# SPDX-License-Identifier: Apache-2.0
"""Reading Python source for what it *does*, not for what it *says about what it does*.

**Five checks in this repository have now matched prose instead of code**: 006's boundary checker,
007's run-reference check, 024's read-path isolation test, 010-era's no-static-credentials row
(which grew its own stripper), and 020's conformance-marker check (which matched
``pytest.mark.enclave`` inside a docstring explaining where a row belongs).

The fifth is where the sentence stops being the thing to rewrite. Every one of these checks reads
source and asks *does this module do X*, and every one of them is defeated by a module that
documents X carefully — which the modules in this tree do, at length, on purpose. A check whose
reliability depends on nobody explaining the rule is a check that punishes the documentation it
depends on.

So the stripping lives here, once, and the checks import it. Principle VII, at the scale of a test
helper: two copies would mean fixing the sixth occurrence twice.

**A false alarm in a hygiene check is not a small cost.** It gets "fixed" by weakening the check or
by contorting a comment, and both leave the gate less able to catch the real thing.
"""

from __future__ import annotations

import ast
from pathlib import Path


def code_without_prose(source: str | Path) -> str:
    """The module's code with docstrings and comments removed.

    ``ast.unparse`` of a parsed module drops comments entirely; docstring expressions are stripped
    explicitly. What remains is code and the string literals that actually participate in
    behaviour — which is deliberately kept, because a literal IS behaviour and a check for a
    hardcoded path or key name must still see one.
    """
    text = Path(source).read_text() if isinstance(source, Path) else source
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = getattr(node, "body", [])
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            node.body = body[1:] or [ast.Pass()]
    return ast.unparse(tree)


__all__ = ["code_without_prose"]
