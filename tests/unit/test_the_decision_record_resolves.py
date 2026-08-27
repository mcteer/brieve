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

#: A bullet in ROADMAP's `Open records` naming a record that is still open. Matched at line
#: start so that prose *mentioning* an accepted record elsewhere in the section is not read as
#: a claim that it is open — the section explains what was accepted and why, and must stay free
#: to do so.
_OPEN_BULLET = re.compile(r"^- \*\*ADR-(\d{4})\*\*", re.MULTILINE)

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
    listed = set(_OPEN_BULLET.findall(section))

    assert listed == proposed, (
        "`ROADMAP.md`'s Open records table disagrees with the ADRs' own Status lines.\n"
        f"  Proposed but unlisted: {sorted(proposed - listed) or 'none'}\n"
        f"  Listed but not Proposed: {sorted(listed - proposed) or 'none'}\n"
        "A record accepted since this was written should lose its `- **ADR-NNNN**` bullet; one "
        "that went Proposed should gain one, saying which feature it governs and why it is open."
    )


def test_no_supersession_rests_on_an_unaccepted_record() -> None:
    """A record cannot be retired by one nobody accepted.

    ADR-0041 read "Superseded by ADR-0065" while ADR-0065 was Proposed — for three weeks, with
    `docs/adr/README.md` listing 0041 as Accepted the whole time. Both were settled on
    2026-08-27 when 0065 was accepted, so this asserts the empty set rather than carrying an
    exception: the pairing is fixed, and a new one should fail here rather than be grandfathered.
    """
    status = {}
    for p in _adr_files():
        match = re.search(r"^- \*\*Status\*\*: (.+)$", p.read_text(encoding="utf-8"), re.M)
        if match is not None:
            status[p.name[:4]] = match.group(1)

    resting = {}
    for num, line in status.items():
        cited = re.search(r"Superseded by \[?ADR-(\d{4})", line)
        if cited is None:
            continue
        target = status.get(cited.group(1), "")
        if target.startswith("Proposed"):
            resting[num] = cited.group(1)

    assert resting == {}, (
        f"a supersession rests on an unaccepted record: {resting}. Either accept the superseding "
        "ADR, or say in `ROADMAP.md`'s Open records why it is right to leave it Proposed."
    )


def test_the_index_agrees_with_each_record() -> None:
    """The fourth place a status lives, and the one that was wrong for three weeks.

    A status is written in the ADR itself, in `ROADMAP.md`'s Open records, in the feature table,
    and in `docs/adr/README.md`'s index — which is the table a reader scans to find out what was
    already decided. It listed ADR-0041 as **Accepted** while ADR-0041 itself read "Superseded by
    ADR-0065", so the index was recommending a record that had been retired.

    Only the leading verdict is compared. The index legitimately carries more than the file does
    (*"Accepted (one clause superseded by 0008)"*) and a checker demanding equality would force
    the two to say exactly the same thing, which is not what an index is for.
    """
    index = {}
    for line in (ADR_DIR / "README.md").read_text(encoding="utf-8").splitlines():
        row = re.match(r"^\| \[(\d{4})\]\([^)]+\) \| .+? \| (.+?) \|$", line)
        if row is not None:
            index[row.group(1)] = row.group(2)

    assert len(index) == len(_adr_files()), (
        f"the index lists {len(index)} records and {len(_adr_files())} files exist; a record "
        "missing from the index is invisible to anyone reading it to find prior decisions"
    )

    def verdict(text: str) -> str:
        return re.sub(r"[*_]", "", text).split()[0].rstrip(",;:—-").capitalize()

    disagree = {}
    for path in _adr_files():
        stated = re.search(r"^- \*\*Status\*\*: (.+)$", path.read_text(encoding="utf-8"), re.M)
        if stated is None:
            continue
        listed = index.get(path.name[:4])
        if listed is not None and verdict(listed) != verdict(stated.group(1)):
            disagree[path.name[:4]] = (verdict(stated.group(1)), verdict(listed))

    assert disagree == {}, (
        "`docs/adr/README.md`'s index disagrees with the records themselves, as "
        f"{{num: (record says, index says)}}: {disagree}"
    )
