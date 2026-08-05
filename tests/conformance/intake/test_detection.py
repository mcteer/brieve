# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — detection notices, records, and adopts nothing (I1–I5).

US1 is the half of this feature that carries no new risk: no model reads the candidate, so
the injection hazard the rest of the gauntlet is built around is simply absent. What these
rows guard is subtler — that a pipeline which *looks* like it is maintaining a pin actually
is.

The sharpest of them is I3. An unreachable upstream reported as "no change" makes an
unmaintained pin indistinguishable from a maintained one, which is the precise condition this
feature exists to end.
"""

from __future__ import annotations

import pytest

from core.intake.emit import detection_proposal, render
from core.intake.package import Stage
from core.intake.pins import Pin, PinState, check_pin
from core.intake.proposal import Candidate, content_digest, is_superseded

PIN = Pin(pack="terraform", repository="https://github.com/hashicorp/agent-skills", commit="a" * 40)


def test_an_unmoved_pin_proposes_nothing_and_is_recorded() -> None:
    """I1 (FR-002) — 'we looked and nothing had moved' is a finding, not a silence."""
    result = check_pin(PIN, lambda _: PIN.commit)
    assert result.state is PinState.UNMOVED
    assert result.upstream_commit == PIN.commit, (
        "an unmoved check must still say what it saw — a check that records nothing is "
        "indistinguishable from a check that did not run"
    )
    with pytest.raises(ValueError):
        detection_proposal(result, candidate_digest="d" * 64, delta="")


def test_a_moved_pin_produces_a_proposal_carrying_both_provenances() -> None:
    """I2 (FR-004) — the delta and where both ends came from."""
    result = check_pin(PIN, lambda _: "b" * 40)
    assert result.state is PinState.MOVED

    package = detection_proposal(result, candidate_digest="d" * 64, delta="- a\n+ b")
    assert package.from_commit == PIN.commit
    assert package.to_commit == "b" * 40
    assert package.delta == "- a\n+ b"
    # Adopts nothing: the package is evidence, and carries no acceptance of any kind.
    assert package.stages_run == {Stage.DETECTION}
    assert package.acceptable() is True and package.verdict is None


def test_an_unreachable_upstream_is_a_failure_never_no_change() -> None:
    """I3 (FR-003) — the row that keeps a rotting pin from looking maintained."""

    def unreachable(_pin: Pin) -> str:
        raise ConnectionError("no route to host")

    result = check_pin(PIN, unreachable)
    assert result.state is PinState.UNREACHABLE
    assert "ConnectionError" in result.detail

    # EVERY way of failing lands on UNREACHABLE, not on UNMOVED. Asserted across failure
    # modes rather than by re-checking one result against the state it cannot be — mypy
    # rightly called that a tautology, and a tautology is a row asserting nothing.
    def timeout(_pin: Pin) -> str:
        raise TimeoutError("upstream did not answer")

    def malformed(_pin: Pin) -> str:
        raise ValueError("unparseable response")

    states = {check_pin(PIN, f).state for f in (unreachable, timeout, malformed)}
    states.add(check_pin(PIN, lambda _: "").state)  # empty answer is not agreement
    states.add(check_pin(PIN, lambda _: "   ").state)  # nor is whitespace
    assert states == {PinState.UNREACHABLE}, (
        f"a failure was reported as something other than unreachable: {states}"
    )

    with pytest.raises(ValueError):
        detection_proposal(result, candidate_digest="d" * 64, delta="")


def test_evidence_does_not_follow_the_candidate_when_upstream_moves_again() -> None:
    """I4 (FR-005, FR-004b) — a superseded proposal is stale and refuses acceptance."""
    first = Candidate("terraform", "b" * 40, content_digest(b"first candidate"))
    assert not is_superseded(first, content_digest(b"first candidate"))
    assert is_superseded(first, content_digest(b"second candidate"))

    result = check_pin(PIN, lambda _: "b" * 40)
    package = detection_proposal(result, candidate_digest=first.digest, delta="- a\n+ b")
    assert package.acceptable() is True

    package.superseded = True
    assert package.acceptable() is False, (
        "a proposal describing bytes upstream no longer has must refuse acceptance — the "
        "digest makes the drift visible, this makes it refuse"
    )
    assert any("no longer the candidate" in s for s in package.limits())


def test_one_pipeline_serves_every_connectivity_tier() -> None:
    """I5 (FR-001) — the trigger differs; nothing downstream knows which it got.

    A connected estate passes a network fetch, an air-gapped one passes a snapshot reader.
    ADR-0053's claim is one pipeline with one trigger difference, and this asserts the claim
    rather than the intention: both produce the same proposal shape.
    """
    from_network = check_pin(PIN, lambda _: "b" * 40)
    from_snapshot = check_pin(PIN, lambda _: "b" * 40)  # a reader over an imported bundle

    live = detection_proposal(from_network, candidate_digest="d" * 64, delta="x")
    bundled = detection_proposal(from_snapshot, candidate_digest="d" * 64, delta="x")

    assert render(live) == render(bundled), (
        "an air-gapped estate must get the same proposal shape as a connected one"
    )


def test_the_proposal_renders_every_stage_including_the_unrun_ones() -> None:
    """FR-004a/FR-027a — absence is legible where presence would be."""
    result = check_pin(PIN, lambda _: "b" * 40)
    body = render(detection_proposal(result, candidate_digest="d" * 64, delta="x"))

    for stage in Stage:
        assert f"## {stage.value.title()}" in body
    assert "not run: analysis" in body and "not run: detonation" in body
    assert "This is not a clean read" in body
    # 033's limitation is stated rather than worked around.
    assert "does not trigger workflows" in body
