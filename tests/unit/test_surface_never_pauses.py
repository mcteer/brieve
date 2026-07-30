# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — FR-015: nothing in the surface pauses, interrupts, or blocks a run.

A negative requirement, asserted as an absence in `src/surfaces`.

**Comments and docstrings are stripped before matching**, and that is load-bearing rather
than tidy: these modules discuss pausing at length precisely because they must not do it.
A check that matched prose would fail on the documentation explaining the guarantee — the
mistake this repository has now made in 006's boundary checker, 007's run-reference check,
and this feature's own read-path isolation test.

The consent model this enforces: an agent with consent to start a run has consent to
finish it. Humans are in the loop when registering an agent or changing its privileges,
not during a run. A surface that could pause runs would put thousands of people in the
path of an ordinary dependency blip.
"""

from __future__ import annotations

import ast
import pathlib

SURFACES = pathlib.Path(__file__).resolve().parents[2] / "src" / "surfaces"

#: Names that would indicate a run being suspended for human input.
FORBIDDEN = (
    "await_approval",
    "wait_for_approval",
    "pause_run",
    "suspend_run",
    "block_until",
    "interrupt_run",
    "prompt_human",
    "human_in_the_loop",
)

#: Blocking primitives, matched precisely rather than by bare name.
#:
#: A first version flagged any call named ``join`` and tripped on ``",".join(...)`` — a
#: string join, not a thread join. The tempting fix is to drop ``join`` from the list,
#: which quietly narrows the check; the right one is to be exact about what blocking looks
#: like. A check that produces false positives gets muted, and a muted check is worse than
#: no check because the gate still appears to exist.
FORBIDDEN_CALLS = ("sleep", "wait", "acquire")

#: A module may declare itself a supervisory loop, and then blocking is its job.
#:
#: This exists because the rule is "no RUN waits on a human", and the blocking-primitive
#: check approximates that. The approximation is right for a request path — any sleep
#: there is a held request — and wrong for the persistent service, whose whole shape is a
#: loop with an interval.
#:
#: Declared rather than carved out by filename, for the reason 009's own task list gives:
#: narrowing a check to remove a false positive is where coverage gets lost silently. An
#: explicit marker is greppable, is a claim the author makes on the record, and leaves the
#: check covering every module that has not made it.
SERVICE_LOOP_MARKER = "__service_loop__"

#: Importing these into a surface module is itself the signal. Blocking a request path
#: requires one of them, and none has a legitimate use here.
FORBIDDEN_IMPORTS = ("threading", "multiprocessing", "concurrent.futures")


def _code_without_prose(path: pathlib.Path) -> ast.Module:
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
    return tree


def _sources() -> list[pathlib.Path]:
    return sorted(SURFACES.rglob("*.py"))


def name_of(node: ast.expr) -> str:
    """A dotted name for an expression, or empty when it is not one.

    Used to judge a call by its RECEIVER rather than by its method name alone, so the check
    can tell `run.lease.acquire()` from `lock.acquire()` without dropping either from the
    forbidden list.
    """
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = name_of(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def test_the_check_covers_something() -> None:
    assert len(_sources()) >= 5


def test_no_surface_module_names_a_pause() -> None:
    offenders: list[str] = []
    for path in _sources():
        code = ast.unparse(_code_without_prose(path)).lower()
        offenders += [f"{path.name}: {name}" for name in FORBIDDEN if name in code]
    assert offenders == [], f"surface can pause a run: {offenders}"


def test_no_surface_module_calls_a_blocking_primitive() -> None:
    """Pausing by another name.

    `time.sleep` in a request path is a run being held open, whatever it is called.
    """
    offenders: list[str] = []
    for path in _sources():
        tree = _code_without_prose(path)
        if SERVICE_LOOP_MARKER in ast.unparse(tree):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            target = node.func
            if isinstance(target, ast.Attribute):
                # A method on a string literal is never a blocking primitive.
                if isinstance(target.value, ast.Constant):
                    continue
                # NOR IS A RUN LEASE. `RunLease.acquire()` is a single conditional upsert
                # that returns immediately and supersedes whoever held the run — it never
                # waits for anything, which is the whole design (`core.durability.lease`: a
                # comparison "whose answer does not depend on who got there first").
                #
                # Excluded by RECEIVER rather than by dropping `acquire` from the list,
                # because this module's own comment argues the point: narrowing the check to
                # remove a false positive is where coverage gets lost silently, and the right
                # fix is to be exact about what blocking looks like. `threading.Lock.acquire`
                # still trips this; `run.lease.acquire` does not.
                if name_of(target.value).endswith("lease") and target.attr == "acquire":
                    continue
                name = target.attr
            else:
                name = getattr(target, "id", "")
            if name in FORBIDDEN_CALLS:
                offenders.append(f"{path.name}: {name}()")
    assert offenders == [], f"surface blocks: {offenders}"


def test_no_surface_module_imports_a_concurrency_primitive() -> None:
    """The other way a request path gets held open.

    Blocking needs something to block on, and none of these has a legitimate use in a
    transport that only starts work and reads records.
    """
    offenders: list[str] = []
    for path in _sources():
        for node in ast.walk(_code_without_prose(path)):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            offenders += [
                f"{path.name}: {n}"
                for n in names
                if any(n == f or n.startswith(f + ".") for f in FORBIDDEN_IMPORTS)
            ]
    assert offenders == [], f"surface imports a concurrency primitive: {offenders}"


def test_only_declared_service_loops_are_exempt() -> None:
    """The exemption is narrow and visible, and nothing else claims it.

    If this list grows, the check is being worked around rather than satisfied — which is
    the failure mode of every exemption, and the reason this asserts the membership rather
    than merely allowing it.

    **Two members, and the second was added deliberately in 012.** `portal/events.py` holds
    an SSE connection open for a bounded time so a person does not refresh a page. It
    `await`s rather than blocks, so it holds no worker while it waits — but the check
    matches `sleep` by name and cannot see that difference, and teaching it to would be
    narrowing the rule, which this file's own note calls the place coverage gets lost
    silently. Declaring the exemption is the more honest of the two, because it is
    greppable and because this row makes it a decision somebody had to make.
    """
    declared = [
        str(p.relative_to(SURFACES))
        for p in _sources()
        if SERVICE_LOOP_MARKER in ast.unparse(_code_without_prose(p))
    ]
    assert declared == ["mcp/server.py", "portal/events.py"], (
        f"unexpected modules claim the service-loop exemption: {declared}"
    )


def test_the_precision_fix_did_not_gut_the_check() -> None:
    """A real blocking call must still be caught.

    Narrowing a check to remove a false positive is exactly where coverage gets lost
    silently, so the narrowed version gets a positive control.
    """
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as fh:
        fh.write("import time\n\ndef handler():\n    time.sleep(5)\n")
        temp = pathlib.Path(fh.name)
    try:
        found = [
            node
            for node in ast.walk(_code_without_prose(temp))
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and not isinstance(node.func.value, ast.Constant)
            and node.func.attr in FORBIDDEN_CALLS
        ]
        assert found, "the narrowed check no longer catches time.sleep()"
    finally:
        temp.unlink()


def test_run_start_is_not_synchronous() -> None:
    """FR-007a in the same breath.

    A dispatcher that executed the run inline would pause the caller for its duration
    without any of the vocabulary above appearing anywhere.
    """
    import inspect

    from surfaces.dispatch.types import RunDispatcher

    signature = inspect.signature(RunDispatcher.dispatch)
    assert "RunHandle" in str(signature.return_annotation)
