# SPDX-License-Identifier: Apache-2.0
"""A1-A4 — a ceiling can grant authoring, and the rows can lose (041, US1).

FAKE_FABRIC_IS_FAULT_INJECTION = (
    "These rows resolve authority through the fake fabric to inject the ONE failure they are "
    "about: a ceiling that names a tool the platform's vocabulary does or does not carry. The "
    "production fabric derives `known_tools` from a registry, so reaching it would make the "
    "vocabulary the thing under test AND the thing supplying the answer."
)

**What these rows assert that 038's do not.** 038's suite constructs `FileAuthor` and
`SubjectReader` directly and synthesizes the ceiling with `fake_identity_fabric(ceiling_tools=
permitted)`. Every one of those rows was green for months while the trio was registered
nowhere, because none of them traverses registration and none consults the vocabulary a ceiling
may actually name. These rows drive **the entrypoint's construction**, which is the path that
was missing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.authoring.tool import AUTHOR_FILE, OPEN_PROPOSAL, READ_SUBJECT
from core.errors import ToolNotRegisteredError
from surfaces.dispatch.authoring import ANALYZER, PROPOSER
from tests.harness.authoring_dispatch import build_as_entrypoint, role_from

FAKE_FABRIC_IS_FAULT_INJECTION = (
    "These rows resolve authority through the fake fabric to inject the ONE failure they are "
    "about: a ceiling naming a tool the vocabulary does or does not carry."
)

TRIO = {READ_SUBJECT, AUTHOR_FILE, OPEN_PROPOSAL}


def test_row_a1_a_ceiling_naming_the_trio_resolves_after_and_refused_before(
    tmp_path: Path,
) -> None:
    """A1 — the row pins the CHANGE, not the end state (FR-002, SC-001).

    The "before" is the rigged-off construction, in-process. There is no pre-041 tree to run
    in a single checkout, and a row that diffed git history would assert about the repository
    rather than about the platform.
    """
    before = build_as_entrypoint(role=ANALYZER, tmp_path=tmp_path, authoring_enabled=False)
    after = build_as_entrypoint(role=ANALYZER, tmp_path=tmp_path, authoring_enabled=True)

    assert not ({READ_SUBJECT, AUTHOR_FILE} & before.vocabulary), (
        "before the authoring branch, a ceiling naming these refuses `unknown_ceiling_entry` "
        "— which is the defect 041 exists to close, and it must be demonstrable"
    )
    assert {READ_SUBJECT, AUTHOR_FILE} <= after.vocabulary


def test_row_a1_the_proposer_half_is_reachable_too(tmp_path: Path) -> None:
    """`open_proposal` is registered by the publishing task, and only by it."""
    proposer = build_as_entrypoint(role=PROPOSER, tmp_path=tmp_path)
    assert OPEN_PROPOSAL in proposer.vocabulary


def test_row_a3_registration_is_the_opt_in_and_the_ceiling_still_decides(
    tmp_path: Path,
) -> None:
    """A3 — a resolvable name is not a permitted one (FR-003).

    The registry knowing `author_file` must not be the same fact as this run being allowed to
    call it. Asserted at the vocabulary layer, which is where the two could be conflated:
    `known_tools` says what a ceiling MAY name, never what one DOES.
    """
    built = build_as_entrypoint(role=ANALYZER, tmp_path=tmp_path)

    # The name resolves...
    assert built.registry.resolve(AUTHOR_FILE) is not None
    # ...and a ceiling that omits it grants nothing. The vocabulary is the set a ceiling may
    # draw from; a ceiling drawing a subset of it is the ordinary case.
    ceiling_without: frozenset[str] = frozenset({READ_SUBJECT})
    assert AUTHOR_FILE not in ceiling_without
    assert ceiling_without <= built.vocabulary


def test_row_a3_a_non_authoring_run_is_untouched(tmp_path: Path) -> None:
    """No authoring role means no authoring vocabulary — every other run is unchanged."""
    ordinary = build_as_entrypoint(role=None, tmp_path=tmp_path)
    assert not (TRIO & ordinary.vocabulary)
    assert {"echo", "plan", "apply"} <= ordinary.vocabulary, (
        "the fixture toolset carries 008-012's lanes and must survive this feature"
    )


def test_row_a4_the_suite_can_lose(tmp_path: Path) -> None:
    """A4 — with the branch rigged off, A1 and A3's assertions must FAIL (FR-018).

    A suite that cannot lose proves nothing. This row runs A1's and A3's central assertions
    against the rigged-off construction and requires each to raise.
    """
    rigged = build_as_entrypoint(role=ANALYZER, tmp_path=tmp_path, authoring_enabled=False)

    with pytest.raises(AssertionError):
        assert {READ_SUBJECT, AUTHOR_FILE} <= rigged.vocabulary

    with pytest.raises(ToolNotRegisteredError):
        rigged.registry.resolve(AUTHOR_FILE)


def test_row_a4_the_rigged_proposer_registers_nothing(tmp_path: Path) -> None:
    """The other half of the self-test, so neither task's row can pass by the other's work."""
    rigged = build_as_entrypoint(role=PROPOSER, tmp_path=tmp_path, authoring_enabled=False)
    assert OPEN_PROPOSAL not in rigged.vocabulary


def test_the_role_is_declared_by_the_jobspec_never_inferred() -> None:
    """A role read from the environment, and nothing else resolves to one.

    The jobspec declares `HARNESS_AUTHORING_ROLE`. Inferring the role from which tools a
    ceiling grants would turn a coincidence into a role — the mistake the resume discriminator
    refuses one layer over.
    """
    assert role_from({"HARNESS_AUTHORING_ROLE": "analyzer"}) == ANALYZER
    assert role_from({"HARNESS_AUTHORING_ROLE": "  Proposer "}) == PROPOSER
    assert role_from({}) is None
    assert role_from({"HARNESS_AUTHORING_ROLE": ""}) is None
    assert role_from({"HARNESS_AUTHORING_ROLE": "publisher"}) is None, (
        "an unrecognised role must be no role at all, never a default one"
    )


def test_the_analyzer_and_proposer_hold_disjoint_registrations(tmp_path: Path) -> None:
    """Task scope expressed twice: by the jobspec, and by what each task can resolve.

    A task that forgot its `RUN_REQUESTED_TOOLS` declaration still cannot resolve the other
    half's tools, because they were never registered into its registry.
    """
    analyzer = build_as_entrypoint(role=ANALYZER, tmp_path=tmp_path)
    proposer = build_as_entrypoint(role=PROPOSER, tmp_path=tmp_path)

    assert OPEN_PROPOSAL not in analyzer.vocabulary, (
        "the analysing task must not be able to resolve the publishing tool; it holds the "
        "analysed content and must not hold a route out"
    )
    assert not ({READ_SUBJECT, AUTHOR_FILE} & proposer.vocabulary), (
        "the publishing task holds the credential and must not be able to read a subject"
    )


def test_registration_refuses_a_half_built_analyzer(tmp_path: Path) -> None:
    """No trees, no registration.

    A registered name whose handler holds no state fails at call time — which is after the
    ceiling has already said yes, and therefore too late to read as a governance answer.
    """
    from core.registry.memory import ToolRegistry
    from surfaces.dispatch.authoring import authoring_registry_for

    with pytest.raises(ValueError, match="run-scoped state"):
        authoring_registry_for(ANALYZER, registry=ToolRegistry())


def test_registration_refuses_a_proposer_with_no_observer() -> None:
    """`open_proposal` is non-repeatable; one without an observer parks an interrupted run."""
    from core.registry.memory import ToolRegistry
    from surfaces.dispatch.authoring import authoring_registry_for

    with pytest.raises(ValueError, match="observer"):
        authoring_registry_for(
            PROPOSER, registry=ToolRegistry(), proposal_handler=lambda args: None
        )
