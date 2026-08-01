# SPDX-License-Identifier: Apache-2.0
"""CONFORMANCE — a dispatched run's tool is one a model named (020, FR-001/FR-002).

**Against a dispatched run, not a constructed agent** (FR-010). The adapter's governance is
already asserted by 004's rows and has been correct since it was written; what was never
asserted — what could not be asserted, because it was not true — is that a real run consults
a model at all. A row that built an agent in-process and watched it choose would prove the
thing that already worked.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest

from tests.conformance.choice import harness as c
from tests.conformance.durability import dispatch_harness as h

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def conn() -> Any:
    connection = h.connection()
    yield connection
    connection.close()


@pytest.mark.enclave
@pytest.mark.host_enclave
def test_a_model_choice_is_executed(conn: Any) -> None:
    """FR-001, SC-001 — the tool invoked is the one a model named, evidenced from the trail.

    **The recording names the tool round-robin would not have picked.** `planner-agent`
    requests `echo` and `plan`; sorted, `_tool_for_step` would have given step 0 `echo` and
    step 1 `plan`. This run chooses `plan` then `echo` — the reverse — so a trail showing that
    order cannot have come from the arithmetic this feature deleted.

    That inversion is what makes the row non-vacuous. Asserting only "a tool ran" would pass
    against the code as it stood before 020.
    """
    run_id = h.unique("choice-executed")
    c.run_to_completion(run_id, answers=["plan", "echo"])

    assert c.named(conn, run_id) == ["plan", "echo"], (
        "the tools recorded as chosen are not the ones the model named, in order — "
        f"got {c.named(conn, run_id)}"
    )
    assert c.outcomes(conn, run_id) == ["chosen", "chosen"], (
        f"a choice did not reach the governed entry cleanly: {c.choices(conn, run_id)}"
    )
    assert h.tool_invocations(conn, run_id) == 2, (
        "the trail records two chosen tools but a different number of invocations — the "
        "choice and the execution have come apart"
    )
    # The join Principle IX requires: a chosen tool and its bracket are the same run's story.
    order = h.event_order(conn, run_id)
    assert order.index("tool_chosen") < order.index("tool_outcome"), (
        "a tool's outcome is recorded before the choice that caused it; an investigator "
        "reading in order would see an effect before its reason"
    )


@pytest.mark.enclave
@pytest.mark.host_enclave
def test_a_toolless_run_is_distinguishable(conn: Any) -> None:
    """FR-002a, FR-002b — the carve-out is asserted rather than trusted.

    A run with `invoke_tools` off runs steps and invokes no tool. It consults no model, which
    is right: a provider call whose answer is discarded is cost and a failure mode for
    nothing. **What it must not be is invisible.** An unasserted carve-out is
    indistinguishable from the defect it resembles — a run that looks governed, executed
    nothing, and consulted nobody.

    So the trail says `not_consulted` per step, and the row checks the *positive* record
    rather than the absence of a `chosen` one. Distinguishing by absence is what left the
    trail short by one step before `STEP_REOBSERVED` existed.
    """
    run_id = h.unique("choice-toolless")
    dispatcher = h.dispatcher()
    dispatcher.dispatch(
        **c.choice_args(run_id, answers=[], invoke_tools=False, steps=2, choice_recording="")
    )
    alloc = h.allocation_of(h.job_of(dispatcher, run_id))
    h.wait_dead(alloc)
    h.assert_entrypoint_ran(alloc)

    assert c.outcomes(conn, run_id) == ["not_consulted", "not_consulted"], (
        "a run that invokes no tools did not say so per step; the carve-out is "
        f"indistinguishable from a model-driven run: {c.choices(conn, run_id)}"
    )
    assert h.tool_invocations(conn, run_id) == 0, "a toolless run invoked a tool"


def test_no_arithmetic_selection_remains() -> None:
    """FR-002, SC-002 — `_tool_for_step` is gone, and nothing replaced it.

    **By source inspection, because a deleted function leaves no runtime trace to assert
    on.** There is no call to make and no event to read; the property is that a shape is
    absent from the tree.

    **Verified non-vacuous before it was written.** `_tool_for_step` at `entrypoint.py:99`
    was the only arithmetic tool selection in `src/`, with exactly one call site — so this
    row has one thing to assert against and would have failed against the tree as it stood.

    Not marked `enclave`: it reads files. It runs in `make check` and in the hermetic lane,
    which is where a regression would be introduced and where it should be caught.

    **Parsed, not grepped, and the first draft of this row proved why.** A text search for
    ``tools[step %`` matched four files — every one of them a *comment* explaining what had
    been deleted, including the comment standing where `_tool_for_step` used to be. The
    repository has paid for this exact mistake before: `test_fake_fabric_is_fault_injection_only`
    says in its own docstring that five checks here have matched prose instead of code. So this
    reads the AST, where a docstring is a string and an expression is an expression.

    It looks for the SHAPE rather than the name — a subscript whose index is a modulo — because
    the defect is the arithmetic and a rename would defeat a name-only check.
    """
    offenders: list[str] = []
    for path in (ROOT / "src").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_tool_for_step":
                offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}: _tool_for_step")
            if isinstance(node, ast.Name) and node.id == "_tool_for_step":
                offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}: call to it")
            # `anything[... % ...]` — selecting an element by a remainder, which is what
            # round-robin over a tool list is and the only reason to write it.
            if isinstance(node, ast.Subscript) and any(
                isinstance(inner, ast.BinOp) and isinstance(inner.op, ast.Mod)
                for inner in ast.walk(node.slice)
            ):
                offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}: subscript by modulo")
    assert not offenders, (
        "arithmetic tool selection is reachable from a production run again: "
        f"{offenders}. A fallback that survives is a fallback that will be taken — exactly "
        "when the provider is down, and every governance row will keep passing"
    )


def test_the_contract_states_what_this_gate_does_not_assert() -> None:
    """FR-009, ADR-0047 — the limits are written down, checked rather than trusted.

    **The limit most likely to be misread is the first one.** A demonstration of a model
    picking the obviously right tool is far more persuasive than what it proves: that the
    choice was *governed*, not that it was *good*. Whether a model chooses well is an eval
    question (Principle VIII).

    Checked because a contract's "what this does not assert" section is the part that rots
    first — it costs nothing to leave behind when the rows change, and nobody notices until
    someone cites the gate for a claim it never made.
    """
    contract = (ROOT / "specs/020-model-in-the-loop/contracts/conformance.md").read_text()
    for required in (
        "Not that the choice is good",
        "Not that the model is safe",
        "Not that two runs agree",
        "Not that the double behaves like any particular model",
    ):
        assert required in contract, (
            f"the conformance contract no longer records the limit {required!r}; a gate "
            "whose stated limits have gone missing will be cited for claims it cannot make"
        )
