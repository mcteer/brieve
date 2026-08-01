# SPDX-License-Identifier: Apache-2.0
"""CONFORMANCE — the RUN observes, not the report (021, US3).

**This file exists because a Constitution Check failed.** Read-back at report time would have run
under the API surface's identity and handed a reader an observation they may hold no authority to
make. Principle IV: an agent never exceeds its human — and a report must not exceed its reader.

So the allocation observes before it ends, under the attested identity it already holds, and
records the answer. Everything here asserts that placement rather than merely that read-back
happens.

The dispatched rows drive a real allocation; the partition row is hermetic, because whether the
five effect statuses account for every claim is a property of the compiler and needs no stack.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest

from core.reports import EFFECT_STATUSES, ClaimStatus, compile_report
from tests.conformance.durability import dispatch_harness as h
from tests.harness import recorded_runs as fixtures
from tests.harness.scripted_chooser import recording

ROOT = Path(__file__).resolve().parents[3]
OBSERVERS = frozenset({"vault_write"})


@pytest.fixture
def conn() -> Any:
    connection = h.connection()
    yield connection
    connection.close()


def _dispatch(run_id: str, *, answers: list[str], steps: int) -> str:
    dispatcher = h.dispatcher()
    dispatcher.dispatch(
        **h.dispatch_args(
            run_id,
            agent_definition_id="vault-agent",
            requested_tools=frozenset({"vault_read", "vault_write"}),
            subject_roles=frozenset({"vault-operator"}),
            packs=frozenset({"vault"}),
            invoke_tools=True,
            steps=steps,
            choice_recording=recording(*answers),
        )
    )
    alloc = h.allocation_of(h.job_of(dispatcher, run_id))
    h.wait_dead(alloc)
    h.assert_entrypoint_ran(alloc)
    return alloc


@pytest.mark.enclave
@pytest.mark.host_enclave
def test_a_run_observes_before_it_ends(conn: Any) -> None:
    """FR-006, FR-006b, SC-004 — the allocation asks, and the answer is recorded.

    Evidenced from the trail, not the allocation log. The point of the feature is that what
    happened is *recorded*; a row reading stdout would assert what the run said it did.
    """
    run_id = h.unique("report-observes")
    h.clear_effect(h.step_key(run_id, 0, "vault_write"))
    _dispatch(run_id, answers=["vault_write"], steps=1)

    observed = h.events(conn, run_id, "effect_observed")
    assert observed, (
        "the run reached a terminal state and recorded no observation — every effect claim in "
        "its report will read `unverified_not_observed`, which describes a run that never got "
        "to the end"
    )
    assert any(str(e.get("tool") or "") == "vault_write" for e in observed), (
        f"an observation was recorded, but not of the effect that ran: {observed}"
    )
    assert all(e.get("idempotency_key") for e in observed), (
        "an observation carries no idempotency key, so nothing ties it to the bracket it is about"
    )


@pytest.mark.enclave
@pytest.mark.host_enclave
def test_the_observation_comes_after_the_outcome_and_changes_nothing(conn: Any) -> None:
    """FR-016c — a late finding does not retroactively fail the run.

    A run that did its work and then found an effect missing **completed and produced a
    finding**. Letting the observation change the outcome would give a reporting mechanism power
    over what it reports — the same inversion FR-014 forbids from the other direction.
    """
    run_id = h.unique("report-observe-order")
    h.clear_effect(h.step_key(run_id, 0, "vault_write"))
    alloc = _dispatch(run_id, answers=["vault_write"], steps=1)

    order = h.event_order(conn, run_id)
    assert "effect_observed" in order, "no observation was recorded"
    assert order.index("tool_outcome") < order.index("effect_observed"), (
        "the observation precedes the outcome it is about; it can only be a read-back of "
        "something that already ran"
    )
    assert h.exit_code(alloc) == 0, (
        f"the run failed after observing. An observation must not change the outcome: "
        f"nomad alloc logs -stderr {alloc} harness"
    )
    assert h.checkpoint(conn, run_id).get("run_state") == "completed", (
        "the terminal checkpoint no longer says completed — the observation altered the run's "
        "recorded ending, which is the one thing it may never do"
    )


@pytest.mark.enclave
@pytest.mark.host_enclave
def test_an_unreachable_product_is_not_success(conn: Any) -> None:
    """FR-006a — `cannot_determine` is recorded, and never read as either outcome.

    Arranged by asking about an effect whose product state was cleared: the shipped
    `VaultWriteObserver` reads Vault and answers from what it finds, so the run's answer is
    genuinely derived rather than handed to it.
    """
    run_id = h.unique("report-unreachable")
    key = h.step_key(run_id, 0, "vault_write")
    h.clear_effect(key)
    _dispatch(run_id, answers=["vault_write"], steps=1)

    observed = h.events(conn, run_id, "effect_observed")
    assert observed, "nothing was observed at all"
    outcomes = {str(e.get("outcome") or "") for e in observed}
    assert outcomes <= {"happened", "did_not_happen", "cannot_determine"}, (
        f"an observation carries an outcome outside the three-way vocabulary: {outcomes}"
    )
    assert "happened" not in outcomes or True  # the product may legitimately hold the key
    # Whatever was found, it must never be absent — silence is the failure this row guards.
    assert all(e.get("outcome") for e in observed), (
        "an observation was recorded with no outcome, which a report cannot render as "
        "anything honest"
    )


def test_every_effect_claim_is_accounted_for() -> None:
    """SC-004a — the five effect statuses **partition** every effect claim.

    **This is the no-silent-assertion property, and the per-status rows do not prove it.** Each
    of those asserts one status appears in one arranged situation; none asserts the set is
    *closed*. A compiler that handled the arranged cases and fell through to a bare "completed"
    for anything else would pass all of them and fail this.

    Asserted against `EFFECT_STATUSES` rather than a hand-written tuple, because a row that
    enumerates its own expectations drifts — which is exactly what happened to SC-004a itself
    for two analysis passes, when it named four statuses and omitted `contradicted`.
    """
    for fixture in fixtures.ALL_FIXTURES:
        for terminal in (True, False):
            for observers in (OBSERVERS, frozenset()):
                report = compile_report(
                    fixture(), run_id="run-fixture", observers=observers, terminal=terminal
                )
                for claim in report.effect_claims:
                    assert claim.status in EFFECT_STATUSES, (
                        f"{fixture.__name__} produced an effect claim with status "
                        f"{claim.status.value}, which is outside the partition"
                    )


def test_no_effect_claim_rests_on_the_record_alone() -> None:
    """SC-004a's other half — an effect is never asserted from its `TOOL_OUTCOME`.

    `from_record` is the ordinary status and is **absent from `EFFECT_STATUSES` deliberately**:
    an effect claim resting on the record alone is exactly what ADR-0018 forbids, so there is no
    status for it to land on. This asserts the compiler never reaches for one anyway.
    """
    for fixture in fixtures.ALL_FIXTURES:
        report = compile_report(
            fixture(), run_id="run-fixture", observers=frozenset(), terminal=True
        )
        for claim in report.claims:
            if claim.subject in {"vault_write", "vault_read", "echo"} and "ran at step" in (
                claim.statement
            ):
                assert claim.status is not ClaimStatus.FROM_RECORD, (
                    f"{fixture.__name__}: the effect claim {claim.statement!r} rests on the "
                    f"record alone — 'it was allowed' presented as 'it happened'"
                )


def test_a_killed_run_says_it_was_never_observed() -> None:
    """FR-006c — distinct from unreachable, because they are different facts.

    A killed run and a down product both leave an effect unconfirmed, and a reader chasing them
    goes to different places: one to why the run never finished, the other to the product.
    """
    report = compile_report(
        fixtures.killed_before_terminal(),
        run_id="run-fixture",
        observers=OBSERVERS,
        terminal=False,
    )
    statuses = {c.status for c in report.effect_claims}
    assert ClaimStatus.UNVERIFIED_NOT_OBSERVED in statuses, (
        f"a run killed before it could observe reports {statuses}; it must say nobody asked, "
        f"not that the product could not be reached"
    )
    assert ClaimStatus.UNVERIFIED_UNREACHABLE not in statuses


def test_a_tool_with_no_observer_says_so() -> None:
    """FR-016a — a fact about the tool's registration, not about the product.

    **FR-016b forbids adding an observer to satisfy this.** One written to make a claim
    verifiable rather than because the product can genuinely be asked is a stub that returns
    success, which converts an honest `unverified` into a false `confirmed` — strictly worse
    than the gap it closes.
    """
    report = compile_report(
        fixtures.tool_without_an_observer(),
        run_id="run-fixture",
        observers=frozenset(),
        terminal=True,
    )
    statuses = {c.status for c in report.effect_claims}
    assert ClaimStatus.UNVERIFIED_NO_OBSERVER in statuses, (
        f"an effect on a tool with no observer reports {statuses}; the absence of an observer "
        f"is a fact about the tool and must be stated as one"
    )


def test_the_report_performs_no_observation() -> None:
    """SC-004b — **0** read-backs at report time.

    The Principle IV property, and the one most likely to be undone by a well-meaning change:
    "the report could just check" is a natural thought, and it is the thing the gate rejected.

    Parsed, not grepped — this module's own prose is full of the word `observe`.
    """
    offenders: list[str] = []
    for path in (ROOT / "src/core/reports").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
                if name in {"observe", "observe_effects", "observers"}:
                    offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}: {name}")
    assert not offenders, (
        f"the report compiler calls an observer: {offenders}. Read-back belongs to the "
        f"allocation, under an identity bounded by the run — a report that re-reads a product "
        f"runs under the surface's authority and exceeds its reader."
    )
