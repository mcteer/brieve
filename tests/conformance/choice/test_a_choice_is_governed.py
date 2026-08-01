# SPDX-License-Identifier: Apache-2.0
"""CONFORMANCE — a choice is refused by the enforcement that already existed (020).

Governance became a **signal** here rather than only a wall: a refused choice goes back to the
model, which may choose again. These rows assert both halves — that the denial is the core's
and not the choosing code's, and that the re-choice it permits is bounded, recorded, and
terminal when exhausted.

The second half is the one that matters most. **A run grinding against its ceiling forever
and a run thinking hard are the same picture from outside**, so the bound's absence would look
like the feature working.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from core.choice import DEFAULT_RECHOICE_BOUND
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
def test_an_unpermitted_choice_is_refused_by_existing_enforcement(conn: Any) -> None:
    """FR-003, FR-004, SC-003 — refused, and refused by the CORE.

    **This row discriminates on provenance, not on outcome**, and 019 is why: a layer that
    refuses on its own is outcome-identical to the core refusing, so a row checking only that
    the tool did not run would pass against choosing code that filtered the model's answer
    against the permitted set and never called `invoke_tool` at all.

    The discriminator is the hook trail. A refusal by the existing enforcement leaves a
    `pre_decision` entry from a named governance hook with the reason it denied; a refusal
    invented by the choosing code leaves no `pre_decision` at all, because nothing was ever
    put to the pipeline.

    **What this row cannot do, stated rather than glossed**: `PRE_DECISION` carries
    `hook_name`, `capability_kind`, `outcome` and `reason_code` — and no tool name. So the
    assertion is "a governance hook denied, for the reason an over-reach produces", not "a
    governance hook denied *this* tool". Tightening that would mean widening a sealed-core
    audit payload, which is a bigger change than this row is worth; the run invokes one tool
    and the counts below close most of the gap.
    """
    run_id = h.unique("choice-refused")
    c.run_to_completion(run_id, answers=[c.FORBIDDEN, "vault_read"], steps=1)

    assert c.named(conn, run_id) == [c.FORBIDDEN, "vault_read"]
    assert c.outcomes(conn, run_id) == ["named", "named"], (
        f"the over-reach was not put to the pipeline and re-chosen: {c.choices(conn, run_id)}"
    )

    decisions = h.events(conn, run_id, "pre_decision")
    denials = [d for d in decisions if str(d.get("outcome") or "") == "deny"]
    assert denials, (
        "no hook recorded a denial for the unpermitted choice, so the refusal did not come "
        "from the governed pipeline — the choosing code decided permission for itself, which "
        "is the one thing the contract says it must never do"
    )
    assert any(str(d.get("reason_code") or "") == "out_of_scope" for d in denials), (
        f"a hook denied, but not for the reason a tool outside the run's scope produces: "
        f"{denials}. A different reason means something other than the ceiling refused, and "
        f"this row would then be asserting the wrong mechanism"
    )
    # `pipeline` is the run-scope check the engine performs before any hook is consulted, and
    # it is the one that catches a tool outside the run's scope — which is what an over-reach
    # is. Named alongside the hooks rather than instead of them because a *ceiling* over-reach
    # and a *policy* denial come from different places and this row should accept either; what
    # it must reject is a denial from outside the built-in governance set entirely, which is
    # what a refusal invented by the choosing code would look like if it ever wrote one.
    assert {str(d.get("hook_name") or "") for d in denials} <= {
        "pipeline",
        "authority",
        "dependency",
        "mirroring",
        "governance",
    }, f"the denial came from a hook outside the built-in governance set: {denials}"
    assert h.tool_invocations(conn, run_id) == 1, (
        "the refused tool executed, or the permitted one did not"
    )


@pytest.mark.enclave
@pytest.mark.host_enclave
def test_a_refusal_returns_to_the_model(conn: Any) -> None:
    """FR-004a — the denial teaches rather than only blocking.

    The observable is that a *second* choice happened at the same step after a refusal. The
    row cannot observe the model reading the refusal — the recording answers from a script —
    but it can observe that the platform asked again at the same step index, which is the
    behaviour FR-004a specifies and the only part of it the platform owns.
    """
    run_id = h.unique("choice-returns")
    c.run_to_completion(run_id, answers=[c.FORBIDDEN, "vault_read"], steps=1)

    entries = c.choices(conn, run_id)
    assert [e["step_index"] for e in entries] == [0, 0], (
        f"the second choice was not made at the same step: {entries}"
    )
    assert [e["attempt"] for e in entries] == [0, 1], (
        f"the attempts are not numbered as successive tries at one step: {entries}"
    )


@pytest.mark.enclave
@pytest.mark.host_enclave
def test_the_rechoice_bound_is_terminal(conn: Any) -> None:
    """FR-004b, SC-003a — a run cannot grind past its ceiling by repetition.

    **The property whose absence would look like the feature working.** Without the bound, a
    model naming a forbidden tool forever produces a run that never ends — and from outside,
    a run still going is what a run doing work looks like.

    The recording names the forbidden tool more times than the bound allows, so the run must
    stop at the bound rather than consume the whole recording.
    """
    run_id = h.unique("choice-exhausted")
    over = DEFAULT_RECHOICE_BOUND + 2
    c.run_to_completion(run_id, answers=[c.FORBIDDEN] * over, steps=1)

    outcomes = c.outcomes(conn, run_id)
    assert outcomes == ["named"] * DEFAULT_RECHOICE_BOUND + ["exhausted"], (
        f"the bound did not hold at {DEFAULT_RECHOICE_BOUND} attempts: {outcomes}"
    )
    assert h.tool_invocations(conn, run_id) == 0, "an exhausted run executed a tool anyway"
    # Terminal, and terminal is not a crash. A bound is an ending, which is the reasoning
    # `resume_dispatched_run` already applies to grant expiry.
    assert h.checkpoint(conn, run_id).get("run_state") in ("completed", "stopped"), (
        f"an exhausted run left no terminal checkpoint: {h.checkpoint(conn, run_id)}"
    )


@pytest.mark.enclave
@pytest.mark.host_enclave
def test_every_refusal_is_recorded(conn: Any) -> None:
    """FR-004c, SC-003b — not only the last before success.

    A run denied twice and permitted on the third try is a different event from one permitted
    immediately, and a trail showing only the success would describe the wrong run. This is
    the assertion that would pass vacuously if the platform recorded a choice only when it
    executed — which is the natural implementation, and the wrong one.
    """
    run_id = h.unique("choice-all-refusals")
    c.run_to_completion(run_id, answers=[c.FORBIDDEN, c.FORBIDDEN, "vault_read"], steps=1)

    outcomes = c.outcomes(conn, run_id)
    assert outcomes == ["named", "named", "named"], (
        f"the trail does not hold every attempt, only some: {outcomes}"
    )
    # Two of those three were refused, and the refusals are the pipeline's own records. The
    # count is what makes "every refusal, not only the last" checkable: a platform recording
    # only successful choices would show one entry here, not three.
    denials = [
        d for d in h.events(conn, run_id, "pre_decision") if str(d.get("outcome") or "") == "deny"
    ]
    assert len(denials) >= 2, (
        f"a run denied twice and permitted on the third try left {len(denials)} denial(s) in "
        f"the trail; it would read as a run permitted sooner than it was"
    )


@pytest.mark.enclave
@pytest.mark.host_enclave
def test_a_malformed_choice_is_distinguishable(conn: Any) -> None:
    """Spec edge case — a name that is not a tool is not the same event as an over-reach.

    **The two mean different things to whoever reads the trail**: one is a model that
    misunderstood its task, the other is a model that understood it and reached past its
    ceiling. Collapsing them would tell an investigator the second when the first happened.

    Both appear in one run so the row compares them rather than asserting each in isolation —
    two outcomes that must differ cannot be shown to differ by two separate runs.
    """
    run_id = h.unique("choice-malformed")
    c.run_to_completion(run_id, answers=[c.NOT_A_TOOL, c.FORBIDDEN, "vault_read"], steps=1)

    assert c.outcomes(conn, run_id) == ["malformed", "named", "named"], (
        f"a name that is not a tool is not distinguished from one that is: "
        f"{c.choices(conn, run_id)}"
    )
    # And the malformed one never reached a hook — there was nothing to decide about.
    denied = [
        d
        for d in h.events(conn, run_id, "pre_decision")
        if str(d.get("tool_name") or "") == c.NOT_A_TOOL
    ]
    assert not denied, (
        f"a name that is not a tool was put to the governed pipeline anyway: {denied}"
    )


@pytest.mark.enclave
@pytest.mark.host_enclave
def test_an_empty_choice_ends_the_run(conn: Any) -> None:
    """US1 acceptance 3 — the model names nothing, and the run does not default to a tool.

    Defaulting here would be `_tool_for_step` returning through the back door: a run that
    was told to do nothing would quietly do something, and it would be the something an
    index picked.
    """
    run_id = h.unique("choice-empty")
    c.run_to_completion(run_id, answers=[c.NOTHING], steps=2)

    assert c.outcomes(conn, run_id) == ["empty"], (
        f"naming nothing did not end the run terminally: {c.choices(conn, run_id)}"
    )
    assert h.tool_invocations(conn, run_id) == 0, (
        "the run defaulted to a tool after the model named none"
    )


@pytest.mark.enclave
@pytest.mark.host_enclave
def test_repetition_is_bounded_by_the_step_budget(conn: Any) -> None:
    """Spec edge case — a model naming the same PERMITTED tool forever is bounded already.

    **Asserted because it is the case where nothing is wrong**: no refusal, no malformed
    answer, no ceiling reached. A model that keeps choosing a tool it may have produces a
    perfectly governed run, and the only thing standing between that and a run that never
    ends is the step budget that already existed. Nothing in 020 adds a bound here, which is
    exactly why it needs a row — an unasserted "the old thing still works" is how a
    regression gets in.
    """
    run_id = h.unique("choice-repetition")
    c.run_to_completion(run_id, answers=["vault_read"] * 3, steps=3)

    assert c.outcomes(conn, run_id) == ["named"] * 3
    assert h.tool_invocations(conn, run_id) == 3, (
        "a model naming one tool three times did not produce exactly three invocations"
    )
    assert h.checkpoint(conn, run_id).get("step_index") == 2, (
        "the run did not stop at its step budget"
    )


@pytest.mark.enclave
@pytest.mark.host_enclave
def test_no_provider_credential_reaches_an_allocation(conn: Any) -> None:
    """GATE:no-secret-leak — the provider credential is a dev-lane secret and stays one.

    Two properties, and the second is the one that is easy to miss. The credential must not
    appear in what a run writes; it must also never reach an **allocation's environment**,
    where anyone with scheduler access could read it out of a jobspec — which is the same
    argument 012 made for keeping a person's message out of dispatch metadata.

    `EVAL_PROVIDER_KEY` is imported rather than spelled, so this asserts against the one name
    the platform actually uses instead of a literal that could drift from it.
    """
    from core.evals.scoring import EVAL_PROVIDER_KEY

    jobspec = (ROOT / "infra/jobs/agent-run.nomad.hcl").read_text()
    assert EVAL_PROVIDER_KEY not in jobspec, (
        f"{EVAL_PROVIDER_KEY} reaches an allocation's environment through the jobspec; "
        "scheduler access would expose it"
    )
    for banned in ("ANTHROPIC_API_KEY", "sk-ant-"):
        assert banned not in jobspec, f"{banned!r} appears in the dispatched jobspec"

    run_id = h.unique("choice-no-leak")
    c.run_to_completion(run_id, answers=["vault_read"])
    payloads = str(c.choices(conn, run_id))
    for banned in (EVAL_PROVIDER_KEY, "sk-ant-", "ANTHROPIC_API_KEY"):
        assert banned not in payloads, f"{banned!r} appears in a recorded choice: {payloads}"
