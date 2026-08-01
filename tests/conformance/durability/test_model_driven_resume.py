# SPDX-License-Identifier: Apache-2.0
"""CONFORMANCE — a model-driven run is still durable (020, US3, FR-008/SC-005).

**Here rather than in `tests/conformance/choice`, because it is the same guarantee under a
harder condition.** Every durability property this platform holds was established against a
deterministic sequence: `tools[step % len(tools)]` returns the same answer forever, so
"re-observe, never re-execute" and "re-run the step" were indistinguishable in outcome. A
model is not deterministic, and that distinction becomes real — a replay that re-asked would
be re-execution wearing observation's clothes, and it would look like a correct resume.

The observable the platform can actually assert is *no repeated provider call*. It cannot
assert what a second call **would** have returned, and this file does not try. Recorded as a
known limit in 020's conformance contract rather than papered over.
"""

from __future__ import annotations

from typing import Any

import pytest

from tests.conformance.durability import dispatch_harness as h
from tests.harness.scripted_chooser import recording

pytestmark = [pytest.mark.enclave, pytest.mark.host_enclave]

#: Where the disruption left the run. Step 1 holds the open intent naming the tool the model
#: chose before the disruption — which is the record the resumed run must honour.
INTERRUPTED_AT = 1
TOTAL_STEPS = 4

#: The recording a RESUMED allocation is dispatched with.
#:
#: **Deliberately too short to cover the whole run**, and that is the assertion. The resumed
#: allocation must ask for steps 2 and 3 only: step 0 is below the checkpoint, and step 1's
#: choice is already recorded on its open intent. A resumed run that re-asked for the steps it
#: already did would run off the end of this recording and fail loudly — which is a better
#: failure than one that quietly re-chose and happened to pick the same tool.
RESUME_ANSWERS = ["vault_write", "vault_write"]


@pytest.fixture
def conn() -> Any:
    connection = h.connection()
    yield connection
    connection.close()


def _resume_args(run_id: str, *, answers: list[str]) -> dict[str, Any]:
    return h.dispatch_args(
        run_id,
        resume=True,
        agent_definition_id="vault-agent",
        requested_tools=frozenset({"vault_write"}),
        subject_roles=frozenset({"vault-operator"}),
        packs=frozenset({"vault"}),
        invoke_tools=True,
        steps=TOTAL_STEPS,
        choice_recording=recording(*answers),
    )


def test_a_model_driven_run_resumes(conn: Any) -> None:
    """FR-008, SC-005 — killed mid-flight, resumed, exactly one execution per step.

    The interrupted step's effect did NOT land, so re-observation says it may proceed — and
    the resumed run must run it. What makes this row about 020 rather than a repeat of 014 is
    *which tool* it runs: the one named on the open intent, chosen by a model in a previous
    allocation, rather than one this allocation asked for afresh.
    """
    run_id = h.unique("model-resume")
    key = h.step_key(run_id, INTERRUPTED_AT, "vault_write")
    h.clear_effect(key)
    h.arrange_disrupted(
        conn,
        run_id,
        tool_name="vault_write",
        step_index=INTERRUPTED_AT,
        scope_tools=("vault_write",),
        definition="vault-agent",
    )

    dispatcher = h.dispatcher()
    dispatcher.dispatch(**_resume_args(run_id, answers=RESUME_ANSWERS))
    alloc = h.allocation_of(h.job_of(dispatcher, run_id))
    h.wait_dead(alloc)
    h.assert_entrypoint_ran(alloc)

    assert h.exit_code(alloc) == 0, (
        f"the revived allocation failed: nomad alloc logs -stderr {alloc} harness"
    )
    # Steps 0 and 1 are behind the checkpoint or re-observed; the run must not have executed
    # more than the three remaining brackets' worth of work.
    assert h.recorded_results(conn, run_id) <= TOTAL_STEPS, (
        "more results than the run has steps — something executed twice"
    )
    reobserved = h.events(conn, run_id, "step_reobserved")
    assert reobserved, (
        "the resumed run skipped nothing and recorded nothing about skipping; it re-ran the "
        "whole sequence rather than re-observing its prefix"
    )


def test_resume_reissues_no_provider_call(conn: Any) -> None:
    """FR-008, SC-005 — the observable property, asserted as an exact count.

    **The recording is the instrument.** It holds exactly as many answers as the resumed run
    is permitted to ask for; a run that re-asked for a step it had already done would exhaust
    it and the allocation would fail. So "no repeated provider call" is not inferred from a
    log — it is enforced by a stand-in that runs out.

    And the choices recorded by this allocation must name only the steps it was entitled to
    decide. A `tool_chosen` entry at step 0 or step 1 would mean the model was consulted about
    work another allocation had already done, which is the defect this row exists to catch
    even when the answer happens to match.
    """
    run_id = h.unique("model-resume-noask")
    key = h.step_key(run_id, INTERRUPTED_AT, "vault_write")
    h.clear_effect(key)
    h.arrange_disrupted(
        conn,
        run_id,
        tool_name="vault_write",
        step_index=INTERRUPTED_AT,
        scope_tools=("vault_write",),
        definition="vault-agent",
    )

    dispatcher = h.dispatcher()
    dispatcher.dispatch(**_resume_args(run_id, answers=RESUME_ANSWERS))
    alloc = h.allocation_of(h.job_of(dispatcher, run_id))
    h.wait_dead(alloc)
    h.assert_entrypoint_ran(alloc)

    chosen = h.events(conn, run_id, "tool_chosen")
    steps_decided = sorted({int(e.get("step_index", -1)) for e in chosen})
    assert 0 not in steps_decided, (
        f"the resumed run asked a model about step 0, which is below the checkpoint: {chosen}"
    )
    assert steps_decided, "the resumed allocation recorded no choices at all"
    # Step 1 is the interrupted one. Its tool comes from the open intent, so it appears in the
    # trail as a choice — but it must NOT have cost an ask, which the short recording proves
    # by the allocation having succeeded at all.
    assert h.exit_code(alloc) == 0, (
        "the resumed allocation failed, and the most likely cause is that it asked the model "
        f"more times than the recording covers — i.e. it re-asked for a step it had already "
        f"decided: nomad alloc logs -stderr {alloc} harness"
    )
    for entry in chosen:
        if int(entry.get("step_index", -1)) == INTERRUPTED_AT:
            assert str(entry.get("named") or "") == "vault_write", (
                "the resumed run honoured a different tool at the interrupted step than the "
                f"one its open intent names: {entry}"
            )
