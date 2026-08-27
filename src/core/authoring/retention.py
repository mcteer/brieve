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

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

#: The key the composed proposal rests under in a checkpoint payload (052).
#:
#: Restated here rather than imported from `surfaces.dispatch.authoring`: `core` never imports a
#: surface, and this module needs the name to know what to clear.
PROPOSAL_KEY = "authoring_proposal"

#: Set on a scrubbed proposal so a reader can tell WHY the bodies are empty (052, D1).
#:
#: **A marker, not an emptiness test**, and the difference is load-bearing.
#: `proposal_from_payload` does `str(f["body"])`, which succeeds on `""` — so with emptied keys
#: and no marker it returns a proposal carrying no content, and a publish opens an empty pull
#: request. That is the outcome the refusal exists to prevent, and analysis found the two rules
#: contradicting each other before either was written.
#:
#: Refusing on emptiness was rejected: nothing in `compose` or containment forbids a
#: legitimately empty authored file, so that rule would conflate "this was scrubbed" with "the
#: agent wrote an empty file" and refuse a proposal nobody touched.
#:
#: It earns its place twice. The reader refuses on it, and an auditor reading a scrubbed payload
#: learns why the bodies are empty — which the record could not otherwise say.
SCRUBBED_MARKER = "scrubbed"

#: The proposal fields that hold a customer's content rather than the platform's words.
#:
#: `rationale` is here because FR-032 already decided it: model-authored prose that reaches the
#: customer's repository is content, subject to the same containment the files get. Taking the
#: narrow answer 041 took for intents would have contradicted a decision this platform has
#: already made.
#:
#: `title` and `usage` are NOT here. They are prose *about* the change rather than extracts
#: *from* it, and a reviewer reading a scrubbed run needs them to know what was proposed.
CONTENT_BEARING_PROPOSAL_FIELDS = frozenset({"rationale"})

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


def scrub_proposal_payload(payload: Mapping[str, Any]) -> tuple[dict[str, Any], int]:
    """Clear a finished run's authored content from its checkpoint payload (052, FR-001).

    Returns the rewritten payload and the number of file bodies cleared. **The count is the
    assertion**: "scrubbed nothing" and "scrubbed everything" are otherwise the same silent
    success, which is the reasoning 041's SQL already records one column over.

    **Pure.** No store, no clock, no run — the caller persists. That split is deliberate: *what
    counts as content* is authoring knowledge and belongs beside `CONTENT_BEARING_TOOLS`, while
    *how a payload is stored* is the durability provider's and is already provided. Selecting
    fields in SQL would have put the first inside the second.

    **The durability provider gains no method**, unlike 041. `scrub_closed_arguments` exists
    because clearing intents is a bulk `UPDATE` across a join — real SQL work. This is one blob
    the caller already holds, and `save` upserts by `blob_id`, so a second method would widen a
    sealed-core seam (Principle V) to do what the seam does.

    **What survives is the point.** `files[].path` and `provenance` stay, and `provenance`
    already carries a path-and-digest line per authored file — so a reviewer can hash a merged
    pull request and match it against what the run recorded proposing, while the platform holds
    none of the content. Retention and attestation do not trade here only because that manifest
    already existed.

    **Total and idempotent.** A payload with no proposal, and one already scrubbed, both return
    unchanged with count 0: a run that authored nothing and one that published must not take
    different cleanup paths.
    """
    out = deepcopy(dict(payload))
    proposal = out.get(PROPOSAL_KEY)
    if not isinstance(proposal, dict) or proposal.get(SCRUBBED_MARKER):
        return out, 0

    cleared = 0
    for entry in proposal.get("files", []):
        if isinstance(entry, dict) and entry.get("body"):
            # EMPTIED, never removed. A reader distinguishing "absent" from "emptied" would
            # treat a scrubbed run as a malformed one, and the shape is what a report reads.
            entry["body"] = ""
            cleared += 1

    for field in CONTENT_BEARING_PROPOSAL_FIELDS:
        if proposal.get(field):
            proposal[field] = ""

    proposal[SCRUBBED_MARKER] = True
    return out, cleared


__all__ = [
    "CONTENT_BEARING_PROPOSAL_FIELDS",
    "CONTENT_BEARING_TOOLS",
    "PROPOSAL_KEY",
    "SCRUBBED_MARKER",
    "scrub_authoring_requests",
    "scrub_proposal_payload",
]
