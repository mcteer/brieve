# SPDX-License-Identifier: Apache-2.0
"""The `write` role's corpus, and the floor that fails rather than warns (038, FR-017/018).

**Both gates are mechanical, and that is the spec's own reading.** FR-018 says an artefact is
correct when it *"matches a human-authored reference **on the properties the task is about**"* —
a property is checkable, and ADR-0038's warning case is a property rather than an impression:
*a module wiring a static credential where dynamic secrets were asked for* validates perfectly
and is the wrong answer. So a reference carries a **declared property set**, and the gate checks
the artefact against it.

The must-deny half is mechanical too — the secret detector, the containment scan, and a
byte-identical comparison for injection resistance. **No judge participates anywhere**, which
is why ADR-0063 lets `promote_model_version` record a scorer where a judge would otherwise go.

**The floor is stated in numbers so "representative" is checkable at its edges**, on
`intake_seed`'s mechanism. The clause most likely to erode is the human-authored reference, and
it erodes by *generating* the references — which measures the generator against itself and
passes everything. So each reference records its **author**: "human-authored" becomes a claim in
the artefact rather than an intention in a review.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from core.errors import CoreError


class CorpusRefused(CoreError):
    """The corpus does not meet the floor. Raised, never warned (FR-018b)."""


class DenyClass(StrEnum):
    """What a must-deny case is an example of (FR-017)."""

    SECRET_IN_OUTPUT = "secret_in_output"
    EXFILTRATION = "exfiltration"
    INJECTION_RESISTANCE = "injection_resistance"


#: The floor. A corpus below any clause is refused at load.
MIN_GOLDEN_TASKS = 5
MIN_DENY_PER_CLASS = 1
#: At least one golden task must be **syntactically valid and substantively wrong** — a corpus
#: that only catches malformed output has not measured integration correctness, and would
#: qualify a cell for the exact failure mode ADR-0038 warns about (SC-008).
MIN_VALID_BUT_WRONG = 1


@dataclass(frozen=True)
class Reference:
    """A human-authored answer, and the properties the task is about.

    ``author`` is required and non-empty. The expensive clause of this feature is that a person
    writes these, and the cheap way to satisfy it is to generate them — which measures the
    generator against itself. Recording who wrote it makes the claim inspectable.
    """

    author: str
    properties: frozenset[str]


@dataclass(frozen=True)
class GoldenTask:
    """One correctness case.

    Declares **either** a property set **or** ``expects_no_artifact`` — never neither. An empty
    property set matches trivially, which is the vacuous pass `parse_cases` already refuses for
    measured suites elsewhere.
    """

    name: str
    prompt: str
    reference: Reference | None
    expects_no_artifact: bool
    #: Syntactically valid and substantively wrong. The case that makes the second gate mean
    #: something, because the first gate passes it.
    valid_but_wrong: bool
    #: Whether this task may join the Write GEPA trainset (051). Default true.
    #:
    #: **A measurement task must not train the thing it measures.** SC-002 asks whether
    #: delivering a vendored skill changes the output, answered by running the same task with
    #: the binding present and then removed. An optimiser that had already been trained on
    #: that task would produce a card carrying the rule regardless, and both arms would pass —
    #: measuring the trainset rather than the skill.
    trains: bool = True


@dataclass(frozen=True)
class DenyCase:
    """One must-deny case, scored over the **artefact** rather than over a stated refusal.

    A cell that says "I will not do that" and then does it passes a verb-scored suite. The
    injection class carries a **paired** subject — the same task with and without the injected
    text — because it is scored by comparing the two artefacts, and one subject gives that
    nothing to compare against.
    """

    name: str
    deny_class: DenyClass
    subject: str
    paired_subject: str = ""


@dataclass(frozen=True)
class Corpus:
    golden: tuple[GoldenTask, ...]
    deny: tuple[DenyCase, ...]


def load_corpus(path: Path) -> Corpus:
    """Load and validate, or raise. **Never warns, never returns a short corpus.**"""
    if not path.is_file():
        raise CorpusRefused(
            f"no authoring corpus at {path}; a pack declaring an authoring workflow ships one, "
            f"and a gate with no cases must fail rather than pass vacuously"
        )
    document = tomllib.loads(path.read_text())
    golden = tuple(_golden(entry) for entry in document.get("golden", []))
    deny = tuple(_deny(entry) for entry in document.get("deny", []))
    corpus = Corpus(golden=golden, deny=deny)
    assert_floor(corpus)
    return corpus


def _golden(entry: dict[str, object]) -> GoldenTask:
    name = str(entry.get("name", "")).strip()
    if not name:
        raise CorpusRefused("a golden task has no name")
    expects_no_artifact = bool(entry.get("expects_no_artifact", False))
    raw_reference = entry.get("reference")

    if not expects_no_artifact and raw_reference is None:
        raise CorpusRefused(
            f"golden task {name!r} declares neither a reference nor expects_no_artifact; a task "
            f"without one cannot participate in the second gate, and scoring it on the first "
            f"alone would report a correctness number the corpus did not measure"
        )
    reference: Reference | None = None
    if raw_reference is not None:
        assert isinstance(raw_reference, dict)
        author = str(raw_reference.get("author", "")).strip()
        if not author:
            raise CorpusRefused(
                f"golden task {name!r} has a reference with no author. This is the clause that "
                f"erodes by generating references, which measures the generator against itself "
                f"— so 'human-authored' is recorded as a claim rather than assumed"
            )
        properties = frozenset(str(p) for p in raw_reference.get("properties", []))
        if not properties:
            raise CorpusRefused(
                f"golden task {name!r} declares an empty property set, which matches trivially"
            )
        reference = Reference(author=author, properties=properties)

    return GoldenTask(
        name=name,
        prompt=str(entry.get("prompt", "")),
        reference=reference,
        expects_no_artifact=expects_no_artifact,
        valid_but_wrong=bool(entry.get("valid_but_wrong", False)),
        trains=bool(entry.get("trains", True)),
    )


def _deny(entry: dict[str, object]) -> DenyCase:
    name = str(entry.get("name", "")).strip()
    try:
        deny_class = DenyClass(str(entry["deny_class"]))
    except (KeyError, ValueError) as exc:
        raise CorpusRefused(f"must-deny case {name!r}: {exc}") from exc
    paired = str(entry.get("paired_subject", ""))
    if deny_class is DenyClass.INJECTION_RESISTANCE and not paired:
        raise CorpusRefused(
            f"must-deny case {name!r} is an injection-resistance case and carries no paired "
            f"subject. That class is scored by comparing the artefacts produced with and "
            f"without the injected text, and one subject gives the comparison nothing to "
            f"compare against"
        )
    return DenyCase(
        name=name,
        deny_class=deny_class,
        subject=str(entry.get("subject", "")),
        paired_subject=paired,
    )


def assert_floor(corpus: Corpus) -> None:
    """The floor, enforced. Below it the gate goes red rather than amber."""
    if len(corpus.golden) < MIN_GOLDEN_TASKS:
        raise CorpusRefused(
            f"the corpus has {len(corpus.golden)} golden tasks, below the floor of "
            f"{MIN_GOLDEN_TASKS}"
        )
    valid_but_wrong = sum(1 for t in corpus.golden if t.valid_but_wrong)
    if valid_but_wrong < MIN_VALID_BUT_WRONG:
        raise CorpusRefused(
            "the corpus has no syntactically-valid-but-substantively-wrong task. A corpus that "
            "only catches malformed output has not measured integration correctness, and would "
            "qualify a cell for exactly the failure mode ADR-0038 warns about"
        )
    for deny_class in DenyClass:
        count = sum(1 for c in corpus.deny if c.deny_class is deny_class)
        if count < MIN_DENY_PER_CLASS:
            raise CorpusRefused(
                f"the corpus has {count} must-deny cases for {deny_class.value!r}, below the "
                f"floor of {MIN_DENY_PER_CLASS}; FR-017 names all three and a missing class is "
                f"a gate that reports green over a hazard it never looked for"
            )


__all__ = [
    "MIN_DENY_PER_CLASS",
    "MIN_GOLDEN_TASKS",
    "MIN_VALID_BUT_WRONG",
    "Corpus",
    "CorpusRefused",
    "DenyCase",
    "DenyClass",
    "GoldenTask",
    "Reference",
    "assert_floor",
    "load_corpus",
]
