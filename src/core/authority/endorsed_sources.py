# SPDX-License-Identifier: Apache-2.0
"""Which of a customer's own sources the platform may cite — the governance half (045, T004).

**Endorsement is a governance fact, not a storage one.** The pinned corpus is trusted because
the supply chain reviewed it (ADR-0004); a customer's own documents cannot be trusted that way
and must not be trusted merely because they are present. What the citation gate needs is a
*trust statement about content the platform did not vendor*, and "an administrator of this
customer endorsed this source, at this time" is exactly that — a decision by a named person
that the trail can carry.

So this module holds who endorsed what, which synced version answers rest on, and whether the
endorsement still stands. The **words** live in Postgres (research R3): governance in the
fabric, weight in the store, the same split the audit plane already uses.

**`withdrawn` is read per request and not cached**, which is 044's toggle mechanism reused
rather than re-invented: withdrawal must zero citability at the next resolution without a
restart, because "we have stopped trusting this material" that takes effect at the next deploy
is not a withdrawal.

**This module lives in `authority` for the reason `ask_binding` does** — 025's never-acts rows
forbid the answering path from importing anything named `authority`, so the endorsement is
resolved *before* the answering path is entered, and what crosses into answering is content
plus a version identifier, never a governance decision waiting to be made.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final

from core.authority.errors import ResolutionRefused

SUPPORTED_SCHEMA_VERSION: Final[int] = 1

#: The citation namespace every endorsed document hangs under (research R2). No validated-design
#: path begins with this, which is what makes collision between the two corpora structurally
#: impossible rather than a uniqueness check somebody has to remember to run.
ENDORSED_PREFIX: Final[str] = "/endorsed/"

#: A source name is a path segment, so it is constrained like one. Rejecting `.` and `/` is not
#: fastidiousness — a name containing a separator would let one endorsement's documents resolve
#: under another's namespace, which is the collision the prefix exists to prevent.
_FORBIDDEN_IN_NAME: Final[frozenset[str]] = frozenset({"/", "\\", "..", " "})

#: What the console may write into an endorsed-source entry. A **closed set**, in 044's shape and
#: for 044's reason (FR-018b): there is no field a credential could be written into, so a private
#: source's material stays trust-store material referenced per sync. A filter over a
#: credential-shaped vocabulary is something a future field slips past; an enumeration is not.
SOURCE_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "location",
        "endorsed_by",
        "endorsed_at",
        "adopted_version",
        "adopted_by",
        "adopted_at",
        "withdrawn",
    }
)


@dataclass(frozen=True)
class EndorsedSource:
    """One customer source the platform has been told it may cite.

    `adopted_version` is the identity a run pins and a record names (FR-017h). It is empty
    between endorsement and the first sync, and a source in that state is endorsed but cites
    nothing — which is a legitimate state and not an error, so it is representable rather than
    rejected.
    """

    name: str
    location: str
    endorsed_by: str
    endorsed_at: str
    adopted_version: str = ""
    adopted_by: str = ""
    adopted_at: str = ""
    withdrawn: bool = False

    @property
    def citable(self) -> bool:
        """Whether this source contributes anything to resolution *right now*.

        Withdrawal beats adoption deliberately: a withdrawn source with an adopted version
        resolves nothing. The version stays recorded because runs already in flight pinned it
        (research R4) and their records must keep naming something real.
        """
        return not self.withdrawn and bool(self.adopted_version)

    @property
    def prefix(self) -> str:
        """The path prefix this source's documents live under."""
        return f"{ENDORSED_PREFIX}{self.name}/"


def parse_endorsed_sources(record: Mapping[str, Any] | None) -> dict[str, EndorsedSource]:
    """Read the `endorsed-sources` record into what resolution needs.

    **An absent or empty record is an empty mapping, not a refusal.** No customer has endorsed
    anything is the state every deployment starts in and most stay in; treating it as an error
    would make the endorsed corpus a required dependency of answering, which is precisely the
    coupling US6 exists to prevent.

    **A malformed record IS a refusal.** The distinction is 044's `read_matrix` finding
    generalised: unreadable must not present as empty, because empty means "nothing is
    endorsed" and answers would quietly stop citing material an administrator believes is
    trusted — a silent narrowing that reads as the platform having lost the documents.
    """
    if not record:
        return {}

    version = record.get("schema_version", SUPPORTED_SCHEMA_VERSION)
    if int(version) != SUPPORTED_SCHEMA_VERSION:
        raise ResolutionRefused(
            f"endorsed-sources record is schema version {version}; this build understands "
            f"{SUPPORTED_SCHEMA_VERSION}. Reading it under the wrong schema would mean "
            f"deciding what may be cited from fields whose meaning has changed.",
            reason_code="unsupported_schema_version",
        )

    sources: dict[str, EndorsedSource] = {}
    for name, entry in record.items():
        if name in {"schema_version", "set_by"}:
            continue
        if not isinstance(entry, Mapping):
            raise ResolutionRefused(
                f"endorsed source {name!r} is not a set of fields. A record that does not "
                f"parse must refuse rather than resolve to nothing — see this function's note.",
                reason_code="malformed_record",
            )
        sources[name] = _source_from(name, entry)
    return sources


def _source_from(name: str, entry: Mapping[str, Any]) -> EndorsedSource:
    validate_source_name(name)
    unknown = sorted(set(entry) - SOURCE_FIELDS)
    if unknown:
        raise ResolutionRefused(
            f"{unknown} are not fields of an endorsed source; the set is {sorted(SOURCE_FIELDS)}",
            reason_code="malformed_record",
        )

    location = str(entry.get("location", "")).strip()
    if not location:
        raise ResolutionRefused(
            f"endorsed source {name!r} names no location", reason_code="malformed_record"
        )

    endorsed_by = str(entry.get("endorsed_by", "")).strip()
    if not endorsed_by:
        raise ResolutionRefused(
            f"endorsed source {name!r} records no endorser. An endorsement whose author is "
            f"unknown is not a trust statement — it is content that arrived (FR-002).",
            reason_code="malformed_record",
        )

    return EndorsedSource(
        name=name,
        location=location,
        endorsed_by=endorsed_by,
        endorsed_at=str(entry.get("endorsed_at", "")).strip(),
        adopted_version=str(entry.get("adopted_version", "")).strip(),
        adopted_by=str(entry.get("adopted_by", "")).strip(),
        adopted_at=str(entry.get("adopted_at", "")).strip(),
        # Truthiness, not `is True`: the record round-trips through Vault's JSON and a field
        # somebody set to the string "true" must not read as not-withdrawn. 007's `wrap_info`
        # lesson in its general form — the shape a value arrives in is not the shape it was
        # written in.
        withdrawn=_as_bool(entry.get("withdrawn")),
    )


def _as_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1"}
    return bool(value)


def validate_source_name(name: str) -> None:
    """A name is a namespace segment, and the namespace is a security boundary.

    Called from the console's validator as well as from the parser: refusing at the route means
    an administrator is told *why* while they are still typing, and refusing at the parser means
    a record written by some other means still cannot smuggle a separator into a citation path.
    """
    if not name or not name.strip():
        raise ResolutionRefused(
            "an endorsed source needs a name; it is the citation namespace",
            reason_code="malformed_record",
        )
    for forbidden in _FORBIDDEN_IN_NAME:
        if forbidden in name:
            raise ResolutionRefused(
                f"endorsed source name {name!r} contains {forbidden!r}. The name is a path "
                f"segment under {ENDORSED_PREFIX}; a separator in it would let one source's "
                f"documents resolve inside another's namespace.",
                reason_code="malformed_record",
            )
    if name.startswith("."):
        raise ResolutionRefused(
            f"endorsed source name {name!r} may not begin with a dot",
            reason_code="malformed_record",
        )


def citable_sources(record: Mapping[str, Any] | None) -> dict[str, EndorsedSource]:
    """The sources that contribute to resolution, keyed by name.

    The one place the withdrawal rule is applied, so no caller has to remember it.
    """
    return {
        name: source for name, source in parse_endorsed_sources(record).items() if source.citable
    }
