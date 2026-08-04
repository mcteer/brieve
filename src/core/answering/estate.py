# SPDX-License-Identifier: Apache-2.0
"""An estate question becomes an answer from records — or a decline. It never becomes an action.

**This is ADR-0035's sentence, executable.** *"Everyone asks in the same place, and the answer is
bounded by the asker's own entitlements."* Decided 2026-07-01; until now implemented by nothing.

**The bounding is not here, and that is the design.** This module receives `records` — the result
of a read the surface already performed through the one governed door, narrowed to what the asker
may see. It holds no query, no store, no credential, and cannot widen anything. A module that
fetched its own material could read whatever it liked, and every scope guarantee would degrade
into a review of whether it happened to behave.

**A reference resolves against those records, not against the trail.** *"Exists in the trail"*
would let a model cite an entry the asker was never allowed to see, and the citation would look
like evidence. Resolving against the scoped read is what makes FR-005a structural: nothing outside
scope ever enters this path, so no answer can carry its shape — including by implication, counts,
or absences.

**Evidence, never a verdict** (ADR-0035, ADR-0018). The platform presents what the records show
with references; a human decides what it means. An assistant that declares an estate compliant has
issued a judgement it has no standing to issue, and the caller cannot tell that judgement from a
fact.

**A store failure is not a decline.** It raises. *"The records do not show this"* and *"we could
not read the records"* send a reader to different people, so they must not share a shape — the
same rule 024 established for provider failures.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

from core.audit.schema import AuditEntry

#: The source name this path records. Matches `routing.Route.ESTATE`, and is duplicated as a
#: string rather than imported to keep this module's imports to the two it needs.
ESTATE_SOURCE = "estate"

ANSWERED = "answered"
DECLINED = "declined"

#: Words that adjudicate rather than report. **Refused in answers, not just discouraged** — the
#: distinction between "the records show three failed applies" and "your estate is compliant" is
#: the whole of what ADR-0035 means by evidence rather than verdict.
VERDICT_WORDS: frozenset[str] = frozenset(
    {"compliant", "non-compliant", "noncompliant", "passing", "healthy", "safe", "secure"}
)


class EstateProviderUnavailable(Exception):
    """The model could not be reached, or answered unusably. **Never shaped like a decline.**"""


class VerdictRefused(Exception):
    """A claim adjudicated instead of reporting.

    Raised rather than dropped, deliberately: a dropped verdict would leave a shorter answer that
    still read as complete, and the reader would never learn the platform had an opinion it was
    not entitled to. This is a defect in the provider's output and it should be loud.
    """


class EstateProvider(Protocol):
    """The seam. A fixture replays a recording; a live provider asks a vendor.

    **Injected, never constructed here** — the same arrangement 024 established, and for the same
    reason: the blocking eval lane drives this path with a recording, which is the only way those
    gates score what the product produced rather than authored material.
    """

    def answer(
        self, question: str, records: tuple[AuditEntry, ...], context: str = ""
    ) -> list[dict[str, Any]]:
        """Candidate claims, each with the entry hashes it rests on."""
        ...


@dataclass(frozen=True)
class EstateReference:
    """A pointer from a claim to the record behind it — 024's citation, for the trail."""

    entry_hash: str

    def resolves(self, records: tuple[AuditEntry, ...]) -> bool:
        return any(record.entry_hash == self.entry_hash for record in records)


@dataclass(frozen=True)
class EstateClaim:
    statement: str
    references: tuple[EstateReference, ...]


@dataclass(frozen=True)
class EstateAnswer:
    """Answered or declined. **Never `failed`** — a store or provider failure raises instead."""

    disposition: str
    #: Always `estate`, carried so a decline can name the door that was opened (FR-010c).
    source: str = ESTATE_SOURCE
    claims: tuple[EstateClaim, ...] = ()
    declined_reason: str = ""
    #: What the answer rests on, when the read returned a window rather than everything (029).
    #:
    #: Empty when nothing was truncated, which is the common case and renders as no caveat at all.
    #: **On the answer, never on the `ASK_ANSWERED` record** — the trail's access record already
    #: carries the narrowed request and serves the investigator; this serves the *asker*, who is
    #: about to act on "3 runs failed" without otherwise knowing whether that is 3 of 3 or 3 of the
    #: 200 examined out of 1,847. Keeping it here is also what keeps this feature out of sealed
    #: core.
    window_note: str = ""
    dropped: tuple[str, ...] = field(default_factory=tuple)


def _adjudicates(statement: str) -> bool:
    words = {w.strip(".,;:!?").lower() for w in statement.split()}
    return bool(words & VERDICT_WORDS)


def describe_window(window: Mapping[Any, tuple[int, int]]) -> str:
    """What a bounded read left out, in words a person can act on (029, FR-006).

    Empty string when nothing was truncated — the common case, which must render as no caveat at
    all rather than as a reassurance nobody asked for.

    **Per type, because that is the grain that helps.** "The 200 most recent run records of 1,847"
    tells a reader whether "3 runs failed" means 3 of 3 or 3 of a sample; "1,000 of 63,947" across
    mixed types tells them nothing they can use.
    """
    truncated = {kind: counts for kind, counts in window.items() if counts[0] < counts[1]}
    if not truncated:
        return ""
    parts = [
        f"the {returned} most recent {str(kind).replace('_', ' ')} records of {matched}"
        for kind, (returned, matched) in sorted(truncated.items(), key=lambda kv: str(kv[0]))
    ]
    return "Based on " + ", ".join(parts) + "."


def answer_estate_question(
    *,
    question: str,
    records: tuple[AuditEntry, ...],
    provider: EstateProvider,
    window_note: str = "",
    context: str = "",
) -> EstateAnswer:
    """Ask, keep only what the asker's own records support, and decline if that is nothing.

    ``window_note`` describes what the read left out, and is carried onto every outcome — an
    answer, a decline and a refusal all rest on the same evidence, and a decline drawn from a
    window is exactly the case a reader most needs told.

    ``context`` is earlier conversation (035), so a follow-up in a records conversation has a
    subject. It changes what is ASKED and never what is KEPT: a reference still has to resolve
    to a record actually read, and history carries no references to resolve.
    """
    try:
        candidates = (
            provider.answer(question, records, context)
            if context
            else provider.answer(question, records)
        )
    except EstateProviderUnavailable:
        raise
    except Exception as exc:  # noqa: BLE001 — any provider fault is a provider fault
        raise EstateProviderUnavailable(
            f"the records could not be interpreted: {type(exc).__name__}"
        ) from exc

    kept: list[EstateClaim] = []
    dropped: list[str] = []
    for candidate in candidates:
        statement = str(candidate.get("statement", "")).strip()
        if not statement:
            continue
        if _adjudicates(statement):
            raise VerdictRefused(
                f"an estate answer adjudicated rather than reported: {statement!r}. The platform "
                f"presents what the records show; a human decides what it means (ADR-0035)"
            )
        references = tuple(
            EstateReference(entry_hash=str(ref["entry_hash"]))
            for ref in candidate.get("references", [])
            if isinstance(ref, dict) and "entry_hash" in ref
        )
        # EVERY reference must resolve. One unresolvable among several still leaves a claim
        # resting partly on something this asker was never shown.
        if not references or not all(ref.resolves(records) for ref in references):
            dropped.append(statement)
            continue
        kept.append(EstateClaim(statement=statement, references=references))

    if not kept:
        return EstateAnswer(
            disposition=DECLINED,
            declined_reason=(
                "the records you may see do not show this"
                if not dropped
                else "every claim rested on a record that is not in what you may see"
            ),
            dropped=tuple(dropped),
            window_note=window_note,
        )
    return EstateAnswer(
        disposition=ANSWERED,
        claims=tuple(kept),
        dropped=tuple(dropped),
        window_note=window_note,
    )


class RecordedEstateProvider:
    """Replays a case's recording **into the product path** — the blocking lane's substrate.

    The recording is what the *model* said; the path then does its work over it, resolving every
    reference against the scoped records. That is what makes `estate_state` score the product
    rather than replay a string, which is the defect 024 removed for two suites and this removes
    for the last one.

    The recording names records by their **authored id** (`rec-vault-001`), never by content hash:
    a case author cannot write a hash by hand, and a hash in a case would be invalidated by any
    edit to the fixture it points at. `ids_to_hashes` is the loader's map.
    """

    def __init__(self, recorded: str, ids_to_hashes: dict[str, str] | None = None) -> None:
        self._recorded = recorded
        self._ids = ids_to_hashes or {}

    def answer(
        self, question: str, records: tuple[AuditEntry, ...], context: str = ""
    ) -> list[dict[str, Any]]:
        import re as _re

        cited = _re.findall(r"\brec-[a-z0-9-]+\b", self._recorded)
        if not cited:
            # A model that cited nothing. The path declines, which is correct and is what the
            # decline-side rows exist to observe.
            return [{"statement": self._recorded.strip(), "references": []}]
        return [
            {
                "statement": self._recorded.strip(),
                "references": [
                    {"entry_hash": self._ids.get(name, f"unresolvable:{name}")} for name in cited
                ],
            }
        ]


__all__ = [
    "describe_window",
    "ANSWERED",
    "DECLINED",
    "ESTATE_SOURCE",
    "VERDICT_WORDS",
    "EstateAnswer",
    "EstateClaim",
    "EstateProvider",
    "EstateProviderUnavailable",
    "EstateReference",
    "RecordedEstateProvider",
    "VerdictRefused",
    "answer_estate_question",
]
