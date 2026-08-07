# SPDX-License-Identifier: Apache-2.0
"""What an authoring run leaves in the control plane when it finishes (041, FR-033).

**The finding this closes was not in the plan; an analyze pass found it in 040's own design.**
040 keeps a model's stated arguments durably so an interrupted act can be repeated faithfully.
For `author_file` those arguments are **file content** — authored from a customer's private
repository, resting in the control plane. FR-013 refused the trail a copy nobody can delete;
nothing had said anything about the control plane.

**040 made this safe to close, deliberately.** Its schema comment states the bound: *"clearing
this column on a CLOSED bracket is safe (resume reads arguments only for pending steps), and
clearing it on an OPEN one would make that revival re-invoke with nothing — finished acts
only."* It also recorded that the request was left **removable rather than load-bearing** so a
successor could consume it. This is that successor.

**Scoped to authoring runs, not global.** 040's retention decision for ordinary runs stands —
a run whose arguments are a Vault path or a workspace name is not the case this exists for, and
widening the scrub to every run would be re-deciding 040's requirement in a different feature.
"""

from __future__ import annotations

from typing import Any

#: The tools whose arguments are somebody else's content rather than a reference to it.
#:
#: `author_file` carries the whole file. `read_subject` carries a path — a reference, and the
#: consulted list already records those deliberately, so scrubbing it would remove provenance
#: rather than content. `open_proposal` carries neither.
CONTENT_BEARING_TOOLS = frozenset({"author_file"})


def scrub_authoring_requests(durability: Any, *, run_id: str) -> int:
    """Clear finished authoring acts' arguments from the control plane. Returns the count.

    Called at terminal state. Safe to call twice, and safe to call on a run that authored
    nothing: a scrub with nothing to scrub returns zero rather than failing, because a
    successful run and an empty one must not have different cleanup paths.

    Returns 0 rather than raising when the provider predates the method — an older provider is
    a deployment fact, not a reason to fail a run that has already finished its work.
    """
    scrub = getattr(durability, "scrub_closed_arguments", None)
    if scrub is None:
        return 0
    return int(scrub(run_id))


__all__ = ["CONTENT_BEARING_TOOLS", "scrub_authoring_requests"]
