# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — the authoritative record points at things that exist, and says what is open.

Principle X makes the ADRs authoritative: they govern, and a planner reads them to find out what
was already decided. Two ways that record can lie without anyone noticing, both found on
2026-08-27 and both fixed in the same change as this file:

**Seventeen cross-links pointed at filenames that do not exist.** Every one was written as a
*paraphrase* of the target's idea rather than its filename — `0025-registry-isolation.md` for what
is really `0025-enclave-is-the-default-topology.md`. Prose that reads correctly and resolves to
nothing is worse than a missing link, because the reader believes a record was consulted.

**`ROADMAP.md` claimed one ADR remained Proposed when six did**, five of them governing features
that had already shipped. That section's own closing paragraph warns about exactly this staleness
and records that it had already happened twice, in the file a planner reads first. A third
recurrence is what a gate row exists to prevent — ADR-0047, one level up.

**Why the second row is the one worth keeping.** Link rot is annoying; a governing record silently
drifting out of agreement with what shipped is the failure Principle X is written against. The
count is not asserted as a number — a number goes stale the same way the prose did. What is
asserted is that the *set* named in `Open records` is the *set* whose Status reads Proposed.
"""

from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
ADR_DIR = ROOT / "docs" / "adr"

#: A markdown link to a sibling ADR file, e.g. `](0025-enclave-is-the-default-topology.md)`.
_LINK = re.compile(r"\]\((\d{4}-[a-z0-9-]+\.md)\)")

#: A row of the ROADMAP `Open records` table, whose first cell names the record.
_TABLE_ROW = re.compile(r"^\|\s*\*\*ADR-(\d{4})\*\*\s*\|", re.MULTILINE)

#: The one link that could NOT be repaired by inspection, kept explicit rather than deleted.
#:
#: ADR-0069's `Amends:` cites ADR-0026 and quotes it directly — *"where a model is reachable from
#: is assembly while which model is permitted is governance."* That sentence appears in no ADR but
#: 0069 itself, and ADR-0026 is *Long-running execution — delegation grants, per-step tokens*,
#: which is not about model reachability. Both the target and the quotation are unverified.
#:
#: It is listed rather than allowed: the row below fails if it is ever silently *repaired*, so
#: whoever establishes the real target has to come here and delete this entry. An allowlist that
#: stayed green either way would be the passing stub ADR-0047 forbids.
UNRESOLVED = {
    (
        "0069-governance-configuration-is-requested-at-a-console.md",
        "0026-per-source-model-bindings.md",
    ),
}


def _adr_files() -> list[pathlib.Path]:
    return sorted(p for p in ADR_DIR.glob("0*.md"))


def test_every_cross_link_resolves() -> None:
    """The seventeen. A link naming the target's idea, not its filename, resolves to nothing."""
    names = {p.name for p in _adr_files()}
    broken = {
        (f.name, target)
        for f in _adr_files()
        for target in _LINK.findall(f.read_text(encoding="utf-8"))
        if target not in names
    }
    assert broken - UNRESOLVED == set(), (
        "ADR cross-links point at files that do not exist. These are usually written as a "
        "paraphrase of the target's title; repoint them at the real filename for that number: "
        f"{sorted(broken - UNRESOLVED)}"
    )


def test_the_unresolved_citation_is_still_unresolved() -> None:
    """The other half of the exception, so a fix cannot leave a stale entry behind.

    Without this, repairing ADR-0069's citation would leave `UNRESOLVED` naming a link that no
    longer exists — an exemption nobody can tell is spent.
    """
    names = {p.name for p in _adr_files()}
    for source, target in UNRESOLVED:
        assert (ADR_DIR / source).exists(), f"{source} is gone; drop its UNRESOLVED entry"
        assert target not in names, (
            f"{target} now exists, so {source}'s citation resolves. Delete the UNRESOLVED entry "
            "in this file — the exemption has been earned out."
        )


def test_the_roadmap_names_exactly_the_open_records() -> None:
    """THE ROW THAT MATTERS. A shipped feature governed by an unaccepted record must be visible.

    Asserted as a set rather than a count, because a count drifts silently in precisely the way
    the prose already did — twice before this, by that section's own admission.
    """
    proposed = {
        p.name[:4]
        for p in _adr_files()
        if re.search(r"^- \*\*Status\*\*: Proposed", p.read_text(encoding="utf-8"), re.MULTILINE)
    }
    assert proposed, "no ADR reads Proposed; this row would pass by asserting nothing"

    roadmap = (ROOT / "ROADMAP.md").read_text(encoding="utf-8")
    start = roadmap.index("## Open records")
    section = roadmap[start : roadmap.index("\n## ", start + 1)]
    listed = set(_TABLE_ROW.findall(section))

    assert listed == proposed, (
        "`ROADMAP.md`'s Open records table disagrees with the ADRs' own Status lines.\n"
        f"  Proposed but unlisted: {sorted(proposed - listed) or 'none'}\n"
        f"  Listed but not Proposed: {sorted(listed - proposed) or 'none'}\n"
        "A record accepted since this was written should be dropped from the table; one that "
        "went Proposed should be added, with the feature it governs."
    )


def test_a_superseding_record_has_itself_been_accepted() -> None:
    """A shipped supersession resting on a record nobody accepted.

    ADR-0041 reads "Superseded by ADR-0065" while ADR-0065 is Proposed. That is recorded in
    `Open records` rather than repaired, because accepting 0065 is a maintainer decision under
    Principle X. This row keeps the pairing visible: it fails if a *new* one appears.
    """
    known = {"0041": "0065"}
    status = {
        p.name[:4]: re.search(r"^- \*\*Status\*\*: (.+)$", p.read_text(encoding="utf-8"), re.M)
        for p in _adr_files()
    }
    resting: dict[str, str] = {}
    for num, match in status.items():
        if match is None:
            continue
        cited = re.search(r"Superseded by \[?ADR-(\d{4})", match.group(1))
        if cited is None:
            continue
        target = status.get(cited.group(1))
        if target is not None and target.group(1).startswith("Proposed"):
            resting[num] = cited.group(1)

    assert resting == known, (
        f"a supersession now rests on an unaccepted record: {resting}. Either the superseding "
        "ADR should be accepted, or `ROADMAP.md`'s Open records section should say why not."
    )
