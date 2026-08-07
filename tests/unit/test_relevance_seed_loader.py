# SPDX-License-Identifier: Apache-2.0
"""R13 — the seed floor is enforced at load, and fails rather than warns (043, T005).

The floor is not decoration. A relevance judge qualified on ten easy cases is qualified for a
world the defect does not live in: the failure mode is claims that are **true, cited, resolving,
and about something else**, and a seed set without those cases has measured nothing that matters.

Each row here writes a seed file that is wrong in exactly one way and asserts the loader refuses
it — because a floor that only holds for the file we happen to have is a floor nobody can rely on.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from core.evals.relevance_seed import (
    MINIMUM_CASES,
    load_relevance_seed,
)
from core.evals.suites import UnrunnableSuite

AUTHOR = "Dan McTeer"


def _case(ident: str, *, verdicts: list[str], author: str = AUTHOR, question: str = "Q?") -> str:
    claims = "\n".join(
        textwrap.dedent(f"""
        [[cases.claims]]
        statement = "statement {index}"
        citation = "/validated-designs/vault-operating-guides-adoption#a"
        verdict = "{verdict}"
        """).strip()
        for index, verdict in enumerate(verdicts)
    )
    return (
        textwrap.dedent(f"""
    [[cases]]
    id = "{ident}"
    question = "{question}"
    author = "{author}"
    """).strip()
        + "\n"
        + claims
        + "\n"
    )


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "seed.toml"
    path.write_text(body)
    return path


def _healthy(count: int = MINIMUM_CASES) -> str:
    """A set that clears every floor: 3 irrelevant, 3 relevant, 1 mixed, rest relevant."""
    parts = [_case(f"irrelevant-{i}", verdicts=["irrelevant", "irrelevant"]) for i in range(3)]
    parts += [_case(f"relevant-{i}", verdicts=["relevant", "relevant"]) for i in range(3)]
    parts.append(_case("mixed-0", verdicts=["relevant", "irrelevant"]))
    while len(parts) < count:
        parts.append(_case(f"filler-{len(parts)}", verdicts=["relevant"]))
    return "\n".join(parts)


def test_a_healthy_seed_set_loads(tmp_path: Path) -> None:
    cases = load_relevance_seed(_write(tmp_path, _healthy()))
    assert len(cases) == MINIMUM_CASES
    assert sum(1 for c in cases if c.supported_but_irrelevant) >= 3
    assert sum(1 for c in cases if c.mixed) >= 1


def test_a_missing_file_refuses(tmp_path: Path) -> None:
    with pytest.raises(UnrunnableSuite, match="no relevance seed set"):
        load_relevance_seed(tmp_path / "absent.toml")


def test_a_short_set_refuses(tmp_path: Path) -> None:
    body = "\n".join(
        [_case(f"irrelevant-{i}", verdicts=["irrelevant"]) for i in range(3)]
        + [_case(f"relevant-{i}", verdicts=["relevant"]) for i in range(3)]
    )
    with pytest.raises(UnrunnableSuite, match="below the floor"):
        load_relevance_seed(_write(tmp_path, body))


def test_too_few_supported_but_irrelevant_cases_refuses(tmp_path: Path) -> None:
    """The floor that matters most: those cases ARE the defect."""
    parts = [_case("irrelevant-0", verdicts=["irrelevant"])]
    parts += [_case(f"relevant-{i}", verdicts=["relevant"]) for i in range(8)]
    parts.append(_case("mixed-0", verdicts=["relevant", "irrelevant"]))

    with pytest.raises(UnrunnableSuite) as exc:
        load_relevance_seed(_write(tmp_path, "\n".join(parts)))

    assert "supported-but-irrelevant" in str(exc.value)
    assert "the defect" in str(exc.value)


def test_too_few_fully_relevant_cases_refuses(tmp_path: Path) -> None:
    """A judge measured only on refusing would be qualified to refuse everything."""
    parts = [_case(f"irrelevant-{i}", verdicts=["irrelevant"]) for i in range(9)]
    parts.append(_case("mixed-0", verdicts=["relevant", "irrelevant"]))

    with pytest.raises(UnrunnableSuite, match="fully-relevant"):
        load_relevance_seed(_write(tmp_path, "\n".join(parts)))


def test_no_mixed_case_refuses(tmp_path: Path) -> None:
    """Partial keep is a real outcome; a judge that only answers all-or-nothing is unmeasured."""
    parts = [_case(f"irrelevant-{i}", verdicts=["irrelevant"]) for i in range(4)]
    parts += [_case(f"relevant-{i}", verdicts=["relevant"]) for i in range(6)]

    with pytest.raises(UnrunnableSuite, match="mixed"):
        load_relevance_seed(_write(tmp_path, "\n".join(parts)))


def test_a_case_with_no_author_refuses(tmp_path: Path) -> None:
    """038's precedent: a generated label measures the generator against itself."""
    body = _healthy().replace(f'author = "{AUTHOR}"', 'author = ""', 1)

    with pytest.raises(UnrunnableSuite) as exc:
        load_relevance_seed(_write(tmp_path, body))

    assert "author" in str(exc.value)


def test_a_verdict_outside_the_vocabulary_refuses(tmp_path: Path) -> None:
    body = _healthy().replace('verdict = "relevant"', 'verdict = "probably"', 1)

    with pytest.raises(UnrunnableSuite, match="not a label"):
        load_relevance_seed(_write(tmp_path, body))


def test_a_case_with_no_claims_refuses(tmp_path: Path) -> None:
    """A case with nothing to judge passes for any judge."""
    body = _healthy() + textwrap.dedent("""
    [[cases]]
    id = "empty"
    question = "Q?"
    author = "Dan McTeer"
    """)

    with pytest.raises(UnrunnableSuite, match="no claims"):
        load_relevance_seed(_write(tmp_path, body))


def test_a_missing_required_field_refuses(tmp_path: Path) -> None:
    body = _healthy().replace('question = "Q?"', "", 1)
    with pytest.raises(UnrunnableSuite, match="missing required field"):
        load_relevance_seed(_write(tmp_path, body))


def test_expected_indices_are_zero_based(tmp_path: Path) -> None:
    """What a correct judge affirms, in the protocol's internal numbering."""
    cases = load_relevance_seed(_write(tmp_path, _healthy()))
    mixed = next(c for c in cases if c.mixed)
    assert mixed.expected == frozenset({0})
