# SPDX-License-Identifier: Apache-2.0
"""How old the ground under an answer is, in words a reader can act on (033).

**The disclosure exists because the claim was already being made.** Every guidance answer
cites pinned documentation, and a citation carries an implicit currency claim — *this is what
the docs say* — that nothing was checking. The pin had no timestamp at all until 033, so no
layer above it could have disclosed an age even if it wanted to. This module is where the
platform stops making that claim silently.

**Never empty, and that is the load-bearing decision.** A note that appeared only past some
threshold would train readers that silence means fresh, which is exactly the unfounded claim
being removed — so a one-day-old pin discloses too, and "unknown" is its own wording rather
than an absence. The tiers tune the framing; the fact is stated in every one.

**Never a decline.** An operator who has not run a refresh has not made the platform wrong,
and declining would punish the asker for somebody else's omission. 024's intent was
latest-available content answered from the newest sync; this discloses the gap rather than
withholding the answer. The disposition machinery does not import this module.
"""

from __future__ import annotations

from datetime import datetime
from typing import Final

#: Under this many days, the pin is stated plainly. Documentation moves on a scale of weeks;
#: a fortnight-old pin is not news.
GROUND_FRESH_DAYS: Final[int] = 30

#: Past this many days, the wording suggests a refresh. Chosen with 024's intent in mind —
#: the corpus is meant to track latest-available content, and a quarter without a sync is
#: worth a sentence in front of whoever is reading the answer.
GROUND_STALE_DAYS: Final[int] = 90

#: What an answer says when its ground has no knowable age. The 024-era pin reads this way,
#: as does any manifest whose timestamp is malformed or ahead of now (`load_corpus` maps all
#: of those to `None` deliberately — see `core.answering.corpus`).
UNKNOWN_NOTE: Final[str] = (
    "The age of this answer's source material is unknown: the pinned corpus records no sync "
    "time. Refresh the corpus to establish one."
)


def describe_ground(synced_at: datetime | None, now: datetime) -> str:
    """One sentence about when this answer's source material was pinned.

    ``now`` is passed in rather than read here, for the same reason the estate window's is: a
    module that calls the clock cannot be tested at a boundary, and these boundaries are
    exactly where wording changes. The surface owns "when is now".

    Age is whole days, floored — a documentation corpus does not have an interesting number of
    hours, and a note that changed wording at 03:00 would be noise.
    """
    if synced_at is None:
        return UNKNOWN_NOTE

    days = (now - synced_at).days
    if days < 0:
        # Belt and braces: `load_corpus` already maps a future pin to `None`, so this is
        # unreachable through the loader. A caller constructing a `Corpus` by hand could still
        # get here, and "in -3 days" is not a sentence anyone should read.
        return UNKNOWN_NOTE

    pinned = synced_at.date().isoformat()
    age = "today" if days == 0 else "1 day ago" if days == 1 else f"{days} days ago"

    if days < GROUND_FRESH_DAYS:
        return f"Source material pinned {pinned} ({age})."
    if days < GROUND_STALE_DAYS:
        return f"Source material pinned {pinned} ({age}) — newer guidance may have been published."
    return (
        f"Source material pinned {pinned} ({age}) — this corpus is overdue a refresh, and "
        f"newer guidance is likely."
    )


__all__ = ["GROUND_FRESH_DAYS", "GROUND_STALE_DAYS", "UNKNOWN_NOTE", "describe_ground"]
