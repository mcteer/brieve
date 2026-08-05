# SPDX-License-Identifier: Apache-2.0
"""What is being proposed, identified by its bytes (037, FR-004b/FR-005).

**A candidate is its content, not its version string.** Everything downstream keys off the
digest so evidence cannot drift onto different bytes — the failure where upstream moves twice
while a proposal is open and a reviewer accepts a package describing a candidate that is no
longer the one in front of them.

The digest makes that drift *visible*. `superseded_by` is what makes it *refuse*: identifying
candidates precisely is necessary and not sufficient, and a proposal that merely knows it is
stale while remaining acceptable has recorded the problem instead of preventing it.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


def content_digest(content: bytes) -> str:
    """The identity of a candidate's bytes."""
    return hashlib.sha256(content).hexdigest()


@dataclass(frozen=True)
class Candidate:
    """A specific proposed version of an adopted skill.

    ``commit`` says where upstream put it; ``digest`` says what it actually is. Both are
    carried because they answer different questions: an upstream that re-tags a commit
    changes the first and not the second, and a supply chain has to notice either.
    """

    skill_name: str
    commit: str
    digest: str


@dataclass(frozen=True)
class Delta:
    """The difference between what is pinned and what is proposed.

    The analysis subject, which is why cost tracks upstream MOTION rather than upstream size
    (ADR-0053 stage 3). A pipeline that re-read the whole corpus on every bump would pay for
    upstream's history rather than for its change.
    """

    skill_name: str
    from_commit: str
    to_commit: str
    #: The changed text itself. Held as `str` because this is what a reviewer reads and what
    #: the analyzer is given as DATA — never as instruction (FR-008).
    body: str

    @property
    def is_empty(self) -> bool:
        return not self.body.strip()


def is_superseded(candidate: Candidate, upstream_digest: str) -> bool:
    """Whether the bytes this proposal describes are still the bytes upstream has.

    Called before a proposal may be accepted. The comparison is on the DIGEST rather than the
    commit: an upstream that moves a tag or force-pushes leaves the commit familiar and the
    content different, which is exactly the case a version string would miss.
    """
    return candidate.digest != upstream_digest


__all__ = ["Candidate", "Delta", "content_digest", "is_superseded"]
