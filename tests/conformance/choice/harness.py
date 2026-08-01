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

#: The definition the choice rows drive: the vault pack's two tools, and nothing else.
#:
#: **`vault-agent` rather than the ceiling pair, and the first dispatched run of this feature
#: is what decided it.** `planner-agent` looked ideal — two permitted tools and a third it may
#: not have — and its `plan` tool carries a product action, so the entitlement-mirroring hook
#: refuses every invocation with `identity_unavailable`. That is the platform working: mirroring
#: resolves the requester's product entitlements before a shared-grain credential is wielded,
#: and this enclave federates no user into a product. But it leaves `planner-agent` with one
#: usable tool, and one tool cannot demonstrate a *choice*.
#:
#: The vault pack's tools declare `product_mode` none — they run on the allocation's own
#: platform identity — so mirroring passes and both are genuinely invocable. Two of them, which
#: is the minimum for "the model picked the one an index would not have" to mean anything.
VAULT = "vault-agent"

#: The two tools a choice is made between. Sorted, `_tool_for_step` would have given step 0
#: `vault_read` and step 1 `vault_write`; a recording that inverts that is how these rows
#: prove the answer did not come from arithmetic.
PERMITTED = ("vault_read", "vault_write")

#: A registered tool `vault-agent` may not have. **Real, not invented**: the distinction
#: between a tool named and denied and a name that is not a tool at all is FR-004's, and a
#: fictional name would exercise the malformed path instead. `plan` is a fixture tool the
#: registry always holds, and it is outside both this definition's ceiling and its run scope,
#: so the authority hook refuses it before mirroring is ever consulted.
FORBIDDEN = "plan"

#: A name no registry holds. The malformed case, and it must never be a real tool.
NOT_A_TOOL = "definitely-not-a-registered-tool"

#: The narrow and wide halves of the ceiling pair, bound to DIFFERENT matrix cells. Used only
#: by SC-004, which compares which model two definitions used rather than what they chose —
#: so `echo`, the one tool both can actually invoke, is all either needs.
PLANNER = "planner-agent"
APPLIER = "applier-agent"


def choice_args(
    run_id: str,
    *,
    answers: list[str],
    definition: str = VAULT,
    permitted: tuple[str, ...] = PERMITTED,
    roles: str = "vault-operator",
    packs: frozenset[str] = frozenset({"vault"}),
    **overrides: Any,
) -> dict[str, Any]:
    """A dispatch whose model is a recording, for a definition that can refuse a choice.

    `steps` defaults to the number of answers — these rows watch what a run *chose*, not how
    it survives disruption, and a four-hundred-step run would spend minutes proving the same
    thing four hundred times.

    **The count is answers, not steps, and the two differ whenever a choice is refused.** The
    recording is consumed per *ask*, which is what lets it exercise the re-choice loop at all:
    a refusal at step 0 spends an answer and asks again at the same step. A row that wants two
    steps after a refusal passes `steps=` explicitly.
    """
    args = h.dispatch_args(
        run_id,
        agent_definition_id=definition,
        requested_tools=frozenset(permitted),
        subject_roles=frozenset({roles}),
        packs=packs,
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
    "PERMITTED",
    "PLANNER",
    "VAULT",
    "choice_args",
    "choices",
    "named",
    "outcomes",
    "run_to_completion",
]
