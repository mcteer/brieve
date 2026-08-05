# SPDX-License-Identifier: Apache-2.0
"""Q1-Q9 — the model is qualified for the role it is acting in (038, US5).

**The stub most available here** is a golden-task corpus whose references were generated rather
than written, which measures the generator against itself and passes everything. Q4 makes that
shape fail by requiring each reference to record its author.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.authoring.tool import WRITE_ROLE, resolve_write_cell
from core.authority.errors import ResolutionRefused
from core.authority.matrix import QualifiedCell
from core.evals.authoring_corpus import (
    Corpus,
    CorpusRefused,
    DenyClass,
    GoldenTask,
    Reference,
    assert_floor,
    load_corpus,
)
from core.evals.authoring_scoring import (
    GateReport,
    ToolingResult,
    score_corpus,
    score_deny_case,
    score_reference,
)
from core.evals.promotion import PromotionRefused, promote_model_version
from core.evals.suites import (
    AUTHORING_QUALIFICATION,
    AUTHORING_REQUIRED_SUITES,
    OWED,
    SUITES,
    UnrunnableSuite,
)

ROOT = Path(__file__).resolve().parents[3]
CORPUS = ROOT / "evals" / "authoring" / "corpus.toml"
MODEL = "anthropic/claude-opus@5"


@pytest.fixture(scope="module")
def corpus() -> Corpus:
    return load_corpus(CORPUS)


def _cell(role: str = WRITE_ROLE, **kw: object) -> QualifiedCell:
    defaults: dict[str, object] = {
        "pack": "terraform",
        "model": MODEL,
        "role": role,
        "qualified_by": "live",
        "judge": "",
    }
    defaults.update(kw)
    return QualifiedCell(**defaults)  # type: ignore[arg-type]


def test_row_q1_no_qualified_write_cell_refuses_distinguishably_from_an_outage() -> None:
    """Q1 — FR-016, SC-006.

    An operator sent to argue with governance during an outage, or to the outage during a
    governance gap, has been told the wrong thing.
    """
    with pytest.raises(ResolutionRefused) as exc:
        resolve_write_cell(
            f"terraform:{MODEL}:write",
            {},
            available=frozenset({MODEL}),
            agent_definition_id="authoring-agent",
        )
    assert exc.value.reason_code == "no_qualified_fallback"

    # A cell qualified for another role does not license this one.
    plan_cell = _cell(role="plan")
    with pytest.raises(ResolutionRefused) as exc:
        resolve_write_cell(
            plan_cell.reference,
            {plan_cell.reference: plan_cell},
            available=frozenset({MODEL}),
            agent_definition_id="authoring-agent",
        )
    assert exc.value.reason_code == "no_qualified_fallback"

    # And the positive case, so the refusals above are not passing for the wrong reason.
    write_cell = _cell()
    resolved, fallback = resolve_write_cell(
        write_cell.reference,
        {write_cell.reference: write_cell},
        available=frozenset({MODEL}),
        agent_definition_id="authoring-agent",
    )
    assert resolved.role == WRITE_ROLE
    assert fallback is None


def test_row_q2_correctness_is_two_gates_reported_separately(corpus: Corpus) -> None:
    """Q2 — FR-018, FR-018a. The case that **validates cleanly and diverges from the reference**
    passes gate one and fails gate two.

    Collapsing them into one number would report a module wiring a static credential where
    dynamic secrets were asked for as a partial pass rather than as the specific failure it is.
    """
    good = frozenset(
        {
            "reads_credentials_from_secret_store",
            "no_literal_credential_in_source",
            "credential_has_a_lease",
        }
    )
    # Parses fine; stores a long-lived credential instead of taking a leased one.
    subtly_wrong = frozenset({"reads_credentials_from_secret_store"})

    properties = {
        "dynamic_database_secret": good,
        "static_credential_lookalike": subtly_wrong,
        "pin_the_provider": frozenset(
            {"provider_version_is_pinned", "no_floating_version_constraint"}
        ),
        "existing_integration_is_not_duplicated": frozenset(),
        "least_privilege_role": frozenset({"policy_scoped_to_one_path", "no_wildcard_capability"}),
    }

    report = score_corpus(
        corpus,
        tooling=lambda _t, _a, _c: ToolingResult(ran=True, passed=True),
        artefacts={t.name: (None, {}) for t in corpus.golden},  # type: ignore[misc]
        properties_of=lambda t, _a, _c: properties[t.name],
    )
    assert isinstance(report, GateReport)


def test_row_q2_the_valid_but_wrong_case_passes_one_gate_and_fails_the_other(
    corpus: Corpus,
) -> None:
    """Q2's substance, asserted per task rather than through the whole run."""
    wrong = next(t for t in corpus.golden if t.valid_but_wrong)
    assert wrong.reference is not None

    tooling = ToolingResult(ran=True, passed=True)
    assert tooling.passed, "gate one must accept it — that is what makes it 'valid'"
    assert not score_reference(wrong, frozenset({"reads_credentials_from_secret_store"})), (
        "gate two accepted an artefact missing the properties the task is about; without this "
        "the corpus measures malformed output and calls it integration correctness"
    )
    assert score_reference(wrong, wrong.reference.properties)


def test_row_q2_unrunnable_tooling_fails_rather_than_degrading(corpus: Corpus) -> None:
    """Q2-unrunnable — `UnrunnableSuite`'s discipline.

    No degradation to a formatter-only check while still reporting "validated". 012 shipped the
    skip-reads-as-green shape twice, and this is the costume it would wear here.
    """
    with pytest.raises(UnrunnableSuite, match="cannot run FAILS|could not run"):
        score_corpus(
            corpus,
            tooling=lambda _t, _a, _c: ToolingResult(ran=False, passed=False, detail="no binary"),
            artefacts={t.name: (None, {}) for t in corpus.golden},  # type: ignore[misc]
            properties_of=lambda _t, _a, _c: frozenset(),
        )


def test_row_q3_the_floor_fails_rather_than_warns(corpus: Corpus) -> None:
    """Q3 — FR-018b, SC-008. A raise, not a warning.

    The valid-but-wrong clause is asserted specifically: a corpus that only catches malformed
    output has not measured integration correctness.
    """
    thin = Corpus(golden=corpus.golden[:2], deny=corpus.deny)
    with pytest.raises(CorpusRefused, match="below the floor"):
        assert_floor(thin)

    without_wrong = Corpus(
        golden=tuple(
            GoldenTask(
                name=t.name,
                prompt=t.prompt,
                reference=t.reference,
                expects_no_artifact=t.expects_no_artifact,
                valid_but_wrong=False,
            )
            for t in corpus.golden
        ),
        deny=corpus.deny,
    )
    with pytest.raises(CorpusRefused, match="substantively-wrong"):
        assert_floor(without_wrong)

    for missing in DenyClass:
        pruned = Corpus(
            golden=corpus.golden,
            deny=tuple(c for c in corpus.deny if c.deny_class is not missing),
        )
        with pytest.raises(CorpusRefused, match=missing.value):
            assert_floor(pruned)


def test_row_q4_every_golden_task_carries_a_human_authored_reference(
    corpus: Corpus, tmp_path: Path
) -> None:
    """Q4 — FR-018c. **The clause most likely to erode**, and it erodes by generating them.

    Recording the author makes "human-authored" a claim in the artefact rather than an intention
    in a review.
    """
    for task in corpus.golden:
        if task.expects_no_artifact:
            continue
        assert task.reference is not None
        assert task.reference.author.strip(), f"{task.name} has a reference with no author"
        assert task.reference.properties

    bad = tmp_path / "corpus.toml"
    bad.write_text(
        '[[golden]]\nname = "x"\nprompt = "p"\n'
        '[golden.reference]\nauthor = ""\nproperties = ["a"]\n'
    )
    with pytest.raises(CorpusRefused, match="author"):
        load_corpus(bad)

    neither = tmp_path / "neither.toml"
    neither.write_text('[[golden]]\nname = "y"\nprompt = "p"\n')
    with pytest.raises(CorpusRefused, match="neither a reference nor expects_no_artifact"):
        load_corpus(neither)


def test_row_q5_must_deny_cases_are_scored_over_the_artefact_not_a_verb(corpus: Corpus) -> None:
    """Q5 — FR-017, SC-007.

    A cell that says "I will not do that" and then does it passes a verb-scored suite. All three
    classes FR-017 names are present, and injection resistance carries a **paired** subject.
    """
    classes = {c.deny_class for c in corpus.deny}
    assert classes == set(DenyClass)

    injection = next(c for c in corpus.deny if c.deny_class is DenyClass.INJECTION_RESISTANCE)
    assert injection.paired_subject, "the injection case has nothing to compare against"

    assert score_deny_case(
        injection, produced="module {}", paired_produced="module {}", leaked=False
    )
    assert not score_deny_case(
        injection, produced="module { backdoor }", paired_produced="module {}", leaked=False
    )

    secret = next(c for c in corpus.deny if c.deny_class is DenyClass.SECRET_IN_OUTPUT)
    assert score_deny_case(secret, produced="", leaked=False)
    assert not score_deny_case(secret, produced="", leaked=True)


def test_row_q5_a_cell_failing_a_must_deny_suite_cannot_be_promoted() -> None:
    """Q5's promotion half — SC-007, demonstrated by attempting it."""
    with pytest.raises(PromotionRefused) as exc:
        promote_model_version(
            pack="terraform",
            model=MODEL,
            role=WRITE_ROLE,
            suites_passed=(),
            required_suites=AUTHORING_REQUIRED_SUITES,
            qualified_by="live",
            judge="",
            scorer="authoring-reference-comparison",
        )
    assert exc.value.reason_code == "promotion_incomplete"


def test_row_q6_owed_is_empty_and_the_qualification_is_not_a_per_pack_suite() -> None:
    """Q6 — FR-019, research R7. 037's finding held rather than re-learned."""
    assert OWED == {}
    assert AUTHORING_QUALIFICATION not in SUITES, (
        "`SUITES` is the per-pack list; membership would demand an integration-correctness "
        "corpus from every pack for a capability most of them do not offer"
    )
    assert AUTHORING_REQUIRED_SUITES == (AUTHORING_QUALIFICATION,), (
        "nothing else supplies what promote_model_version checks a write cell against, because "
        "the qualification is deliberately outside SUITES"
    )


def test_row_q7_the_adoption_and_promotion_path_is_unchanged() -> None:
    """Q7 — FR-021. **Not theoretical**: this feature moves a module out of `core/intake/` and
    edits `core/evals/suites.py` and `core/evals/promotion.py`.
    """
    from core.evals.promotion import promote_skill

    source = (ROOT / "src" / "core" / "evals" / "promotion.py").read_text()
    order = [source.index(k) for k in ("provenance", "injection_lens", "suites_passed")]
    assert order == sorted(order), "promote_skill's gate order changed"
    for reason in ("promotion_incomplete", "digest_mismatch", "injection_suspected"):
        assert reason in source, f"{reason} is gone; the refusal vocabulary is unchanged"
    assert callable(promote_skill)


def test_row_q8_a_write_cell_qualified_only_against_a_recording_is_refused() -> None:
    """Q8 — FR-016, research R20.

    `matrix.py` anticipates this feature by name: the fixture/live distinction *"matters most
    for `write` — a model permitted to make changes."* A cell qualified against a recording,
    permitted to author changes to a requester's repository, is what that warns about.
    """
    live = promote_model_version(
        pack="terraform",
        model=MODEL,
        role=WRITE_ROLE,
        suites_passed=AUTHORING_REQUIRED_SUITES,
        required_suites=AUTHORING_REQUIRED_SUITES,
        qualified_by="live",
        judge="",
        scorer="authoring-reference-comparison",
    )
    assert live["qualified_by"] == "live"

    fixture_cell = _cell(qualified_by="fixture")
    assert fixture_cell.qualified_by == "fixture"
    assert live["qualified_by"] != fixture_cell.qualified_by, (
        "the first write cell must be live-qualified; a model permitted to make changes, "
        "qualified against a replay, is exactly what matrix.py warns about"
    )


def test_row_q9_a_cell_with_neither_a_judge_nor_a_scorer_is_refused() -> None:
    """Q9 — ADR-0063.

    Both correctness gates and all three must-deny classes here are mechanical, so no judge
    participates — and the pre-existing check refuses any non-`judge` cell naming none, which
    would make this cell unpromotable. A human-authored reference terminates ADR-0052's regress
    **one link earlier** than a judge does: there is no scoring model to qualify.

    Forcing a judge into the field to satisfy a string check is the "gate that passes by
    vocabulary" 027 refused.
    """
    with pytest.raises(PromotionRefused) as exc:
        promote_model_version(
            pack="terraform",
            model=MODEL,
            role=WRITE_ROLE,
            suites_passed=AUTHORING_REQUIRED_SUITES,
            required_suites=AUTHORING_REQUIRED_SUITES,
            qualified_by="live",
            judge="",
            scorer="",
        )
    assert exc.value.reason_code == "promotion_incomplete"
    assert "judge nor a scorer" in str(exc.value)

    recorded = promote_model_version(
        pack="terraform",
        model=MODEL,
        role=WRITE_ROLE,
        suites_passed=AUTHORING_REQUIRED_SUITES,
        required_suites=AUTHORING_REQUIRED_SUITES,
        qualified_by="live",
        judge="",
        scorer="authoring-reference-comparison",
    )
    assert recorded["scorer"] == "authoring-reference-comparison"
    assert recorded["judge"] == ""


def test_row_the_corpus_ships_and_clears_its_own_floor(corpus: Corpus) -> None:
    """The corpus in the repository is the one the floor is asserted against."""
    assert_floor(corpus)
    assert len(corpus.golden) >= 5
    assert any(t.expects_no_artifact for t in corpus.golden), (
        "the already-integrated case is missing; a duplicate is a wrong answer that looks "
        "exactly like a right one"
    )
    assert isinstance(corpus.golden[0].reference, Reference)
