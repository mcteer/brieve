# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — nothing the pipeline produced decided anything (H1–H5).

**The sentence the whole feature is measured against**: the gauntlet decides what a reviewer
reads, never whether a skill promotes. A pipeline that quietly became an approval mechanism
would have replaced a slow human gate with a fast machine one, which is strictly worse than
the status quo it was built to improve.

H1 is asserted over the whole sequence rather than per stage, because the failure is
emergent: each stage individually declining to promote is not the same as no path promoting.
"""

from __future__ import annotations

import pytest

from core.audit.schema import AuditEventType
from core.intake.manual import BypassRefused, record_bypass
from core.intake.package import EvidencePackage, Stage
from core.intake.verdict import Verdict
from tests.harness.adapter_fixtures import CountingHandler, governed_agent_fixture

#: This row starts a run to record against; identity resolution is not its subject and no
#: authority behaviour is exercised.
FAKE_FABRIC_IS_FAULT_INJECTION = "recording a manual adoption with identity held constant"


def _clean_package() -> EvidencePackage:
    """A candidate that passed every stage — the most favourable outcome the pipeline has."""
    package = EvidencePackage(
        skill_name="terraform",
        from_commit="a" * 40,
        to_commit="b" * 40,
        candidate_digest="c" * 64,
        delta="- a\n+ b",
        stages_run={Stage.DETECTION, Stage.ANALYSIS, Stage.DETONATION},
        verdict=Verdict.CLEAN.value,
        comparison={"new_attempts": [], "new_denials": []},
    )
    return package


def test_no_sequence_of_pipeline_outcomes_promotes() -> None:
    """H1 (FR-021, SC-006) — the whole sequence, not stage by stage."""
    package = _clean_package()

    # Everything the pipeline can say, said as favourably as it can say it.
    assert package.verdict == "clean"
    assert package.canary_contacts == []
    assert package.acceptable() is True

    # `acceptable` is a statement about the EVIDENCE, not an approval. There is no attribute
    # here that promotes, and no verdict value that means approved.
    assert not hasattr(package, "promote")
    assert not hasattr(package, "approved")
    assert "approved" not in {v.value for v in Verdict}


def test_a_superseded_package_is_not_acceptable() -> None:
    """H1 — the one thing the pipeline may refuse: evidence about the wrong bytes."""
    package = _clean_package()
    package.superseded = True
    assert package.acceptable() is False


def test_a_machine_verdict_is_distinguishable_from_a_human_approval() -> None:
    """H2 (FR-022, ADR-0043) — separate members, so neither can be read as the other."""
    machine = {AuditEventType.ANALYSIS_VERDICT, AuditEventType.DETONATION_COMPARED}
    human = {AuditEventType.INTAKE_BYPASSED}
    assert not (machine & human)
    # The analyzer's record carries no field a reader could take for an acceptance.
    assert "approv" not in AuditEventType.ANALYSIS_VERDICT.value


def test_the_manual_path_works_and_is_recorded() -> None:
    """H4 (FR-025, FR-025a) — adoption survives the pipeline being down."""
    _agent, deps, _handlers, audit = governed_agent_fixture(
        tool_calls=[], registry_tools={"noop": CountingHandler()}
    )
    record_bypass(
        deps.governed_run,
        skill_name="terraform",
        to_version="b" * 40,
        subject_user_id="dan",
        reason="intake poller unavailable during incident response",
    )
    entries = [e for e in audit.all_entries() if e.event_type == AuditEventType.INTAKE_BYPASSED]
    assert len(entries) == 1
    payload = entries[0].payload
    assert payload["subject_user_id"] == "dan"
    assert "unavailable" in payload["reason"]


def test_an_unattributed_bypass_is_refused() -> None:
    """H4 (FR-025b) — the manual path must not be quieter than the automated one."""
    _agent, deps, _handlers, _audit = governed_agent_fixture(
        tool_calls=[], registry_tools={"noop": CountingHandler()}
    )
    with pytest.raises(BypassRefused, match="no name"):
        record_bypass(
            deps.governed_run,
            skill_name="terraform",
            to_version="b" * 40,
            subject_user_id="  ",
            reason="in a hurry",
        )
    with pytest.raises(BypassRefused, match="justify"):
        record_bypass(
            deps.governed_run,
            skill_name="terraform",
            to_version="b" * 40,
            subject_user_id="dan",
            reason="",
        )


def test_the_package_states_what_it_does_not_establish() -> None:
    """H5 (FR-027, FR-027a, SC-008) — stage-aware, and unconditional."""
    full = _clean_package()
    limits = full.limits()
    assert any("corpus provokes" in s for s in limits), (
        "a fully-run package must still name ADR-0053's residual — this is the case where "
        "the limits statement is most needed and most likely to be dropped"
    )
    assert any("is safe" in s for s in limits)

    partial = EvidencePackage("t", "a" * 40, "b" * 40, "c" * 64, "d")
    partial_limits = partial.limits()
    assert any("not a clean read" in s for s in partial_limits), (
        "an unrun stage must say so; 'no analysis has run' is a different claim from "
        "'analysis found nothing'"
    )
    # And absence is legible where presence would be.
    assert partial.section(Stage.ANALYSIS) == "not run: analysis"
