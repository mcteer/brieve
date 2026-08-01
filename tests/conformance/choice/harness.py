# SPDX-License-Identifier: Apache-2.0
"""Dispatching a run whose tool a model names, and reading back what it chose.

**Built on `tests.conformance.durability.dispatch_harness` rather than beside it.** That
module already knows how to drive the scheduler, wait for an allocation, and read the trail
through an operator credential; a second copy would be a second answer to "did this run
finish", and the two would disagree exactly when one was wrong. What is added here is the
vocabulary 020 introduced — a recording, a `TOOL_CHOSEN` entry, a choice's outcome.

**Every row reads the trail, never the allocation logs.** A row asserting on stdout would be
asserting what the run *said* it did; the entire claim of this feature is that what a model
chose is recorded.
"""

from __future__ import annotations

from typing import Any

from tests.conformance.durability import dispatch_harness as h
from tests.harness.scripted_chooser import NOTHING, recording

#: The definition whose ceiling can refuse a choice: `echo` and `plan`, never `apply`.
#:
#: A definition permitting everything cannot demonstrate a refusal, and one permitting a
#: single tool cannot demonstrate a choice — so the fixture has to be exactly this shape or
#: the rows below pass against an implementation that never consults anything.
PLANNER = "planner-agent"

#: The wide half of the ceiling pair, bound to the OTHER matrix cell. What SC-004 compares.
APPLIER = "applier-agent"

#: A registered tool that `planner-agent` may not have. **Real, not invented**: the
#: distinction between a tool named and denied and a name that is not a tool at all is
#: FR-004's, and a fictional name would exercise the malformed path instead.
FORBIDDEN = "apply"

#: A name no registry holds. The malformed case, and it must never be a real tool.
NOT_A_TOOL = "definitely-not-a-registered-tool"


def choice_args(run_id: str, *, answers: list[str], definition: str = PLANNER, **overrides: Any):
    """A dispatch whose model is a recording, for a definition that can refuse a choice.

    `steps` is small — these rows watch what a run *chose*, not how it survives disruption,
    and a four-hundred-step run would spend minutes proving the same thing four hundred times.
    """
    args = h.dispatch_args(
        run_id,
        agent_definition_id=definition,
        requested_tools=frozenset({"echo", "plan"}),
        subject_roles=frozenset({"operator"}),
        packs=frozenset(),
        invoke_tools=True,
        steps=len(answers),
        choice_recording=recording(*answers),
    )
    args.update(overrides)
    return args


def run_to_completion(run_id: str, **kwargs: Any) -> str:
    """Dispatch, wait for the allocation to end, and return its exit code's allocation.

    Returns the allocation id so a row can report it in a failure message — a red row whose
    message names `nomad alloc logs <id>` costs a minute to diagnose and one that does not
    costs an afternoon.
    """
    dispatcher = h.dispatcher()
    dispatcher.dispatch(**choice_args(run_id, **kwargs))
    alloc = h.allocation_of(h.job_of(dispatcher, run_id))
    h.wait_dead(alloc)
    h.assert_entrypoint_ran(alloc)
    return alloc


def choices(conn: Any, run_id: str) -> list[dict[str, Any]]:
    """Every `TOOL_CHOSEN` entry for this run, in sequence order."""
    return h.events(conn, run_id, "tool_chosen")


def outcomes(conn: Any, run_id: str) -> list[str]:
    return [str(c.get("outcome") or "") for c in choices(conn, run_id)]


def named(conn: Any, run_id: str) -> list[str]:
    return [str(c.get("named") or "") for c in choices(conn, run_id)]


__all__ = [
    "APPLIER",
    "FORBIDDEN",
    "NOTHING",
    "NOT_A_TOOL",
    "PLANNER",
    "choice_args",
    "choices",
    "named",
    "outcomes",
    "run_to_completion",
]
