# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — nothing in this feature waits on a human (FR-014, SC-008).

ADR-0049's whole subject. Once it is established what an agent and a person may reach,
enforcement is continuous and automatic: the harness denies what exceeds authority,
records what happened, and *alerts* when something warrants attention. A human reads an
alert and decides what to do next; they are never a step a run is blocked on.

**Docstrings and comments are stripped before matching**, and that is load-bearing rather
than tidy: these modules discuss waiting on humans at length precisely because they must
not do it. This repository has now had five checks match prose instead of substance — two
of them in this feature, one of them the file that warned about it.
"""

from __future__ import annotations

import ast
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
WATCHED = (REPO / "src" / "surfaces" / "mcp", REPO / "src" / "core" / "dependencies")

#: Vocabulary that would indicate a run suspended for a person to resolve.
FORBIDDEN = (
    "await_approval",
    "wait_for_approval",
    "pending_human",
    "prompt_human",
    "human_in_the_loop",
    "ask_operator",
    "escalate_to",
    "notify_and_wait",
)


def _code_without_prose(path: pathlib.Path) -> str:
    tree = ast.parse(path.read_text())
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


def _sources() -> list[pathlib.Path]:
    return sorted(p for root in WATCHED for p in root.rglob("*.py"))


def test_the_check_covers_something() -> None:
    """Without this, renaming a directory would make every assertion below pass."""
    assert len(_sources()) >= 5


def test_no_module_waits_on_a_person() -> None:
    offenders: list[str] = []
    for path in _sources():
        code = _code_without_prose(path).lower()
        offenders += [f"{path.name}: {name}" for name in FORBIDDEN if name in code]
    assert offenders == [], f"a run can be blocked on a human: {offenders}"


def test_the_stripper_removes_prose_but_not_code() -> None:
    """Both halves, because a stripper that removed everything would make this vacuous."""
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as fh:
        fh.write('"""Docstring about prompt_human."""\n# comment about prompt_human\nx = 1\n')
        prose = pathlib.Path(fh.name)
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as fh:
        fh.write('"""Docstring."""\nprompt_human = True\n')
        code = pathlib.Path(fh.name)
    try:
        assert "prompt_human" not in _code_without_prose(prose)
        assert "prompt_human" in _code_without_prose(code)
    finally:
        prose.unlink()
        code.unlink()


def test_suspension_waits_on_a_named_dependency_not_a_person() -> None:
    """The positive statement of the same rule.

    A suspended run names a machine condition, and machine conditions clear themselves.
    That is the entire difference ADR-0049 draws.
    """
    from core.durability.sweeper import SuspendedRunRecord

    fields = set(SuspendedRunRecord.__dataclass_fields__)
    assert "awaiting" in fields, "a suspension must name what it waits on"
    for human_shaped in ("approver", "assignee", "owner_email", "requires_approval"):
        assert human_shaped not in fields
