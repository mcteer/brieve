# SPDX-License-Identifier: Apache-2.0
"""The only way work leaves the platform (038, FR-006, FR-013; research R5, R17).

**Built from the workspace and never from the subject.** The file set is `artifact.paths`; the
subject is read only to compute a diff for a path the agent already wrote. That is the path half
of containment, and it is structural — there is no code here that could include an untouched
file, so there is no rule to get wrong.

**The body is structured, with exactly one free-text field.** Task, files touched, disclosures
and limits are composed; the rationale is the one place model prose reaches the artefact, and it
is scanned like everything else. The structure is the bound; the scan covers what structure
cannot.

**The branch derives from the idempotency key, not the correlation ID.** `Observer.observe` is
handed `idempotency_key` and *nothing else*, and the key is ``run_id:step_index:tool_name`` —
so a branch derived from anything the observer does not hold could never be found again, and
every interrupted publish would park the run. Two runs carry different keys, so FR-009 holds; a
resumed run recomputes the same one, which is what makes the observation meaningful rather than
lucky.

**A limits statement, unconditionally**, and one of its clauses is not a caveat but a structural
fact: where the analysed source is itself the sensitive thing, an authored integration is a
*derivative of exactly that*. Containment bounds what is **copied** and cannot bound what is
**implied**. A reviewer deciding whether to publish needs that before they merge.
"""

from __future__ import annotations

import difflib
import hashlib
from dataclasses import dataclass, field
from enum import StrEnum

from core.authoring.artifact import AuthoredArtifact

#: The unconditional limit that containment cannot reach. Present in every proposal, because a
#: guarantee this feature cannot keep must not read like one it can.
DERIVATIVE_LIMIT = (
    "This change is a derivative of the analysed repository. Where the analysed source is "
    "itself the sensitive thing, containment bounds what was COPIED and cannot bound what is "
    "IMPLIED — an integration necessarily reflects what was read. Decide what to publish with "
    "that in mind."
)


class ProposalState(StrEnum):
    """Where a proposal is. The platform writes the first three and observes the rest."""

    COMPOSED = "composed"
    REFUSED = "refused"
    OPENED = "opened"
    #: **Observed from the host, never written by the platform.** A merge is a person's act,
    #: and no member of this vocabulary may be readable as the platform accepting its own work.
    MERGED = "merged"
    CLOSED = "closed"


def branch_for(idempotency_key: str) -> str:
    """The branch, derived from what the observer will actually hold.

    Not from the correlation ID: `Observer.observe(*, idempotency_key)` receives that string and
    nothing else, and `run_id` is not reliably the correlation ID. A branch the observer cannot
    recompute makes every interrupted publish resolve `CANNOT_DETERMINE` and park the run.
    """
    if not idempotency_key.strip():
        raise ValueError("an idempotency key is required to name a branch")
    digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()[:16]
    return f"brieve/authoring/{digest}"


@dataclass(frozen=True)
class ProposedFile:
    """One entry in the proposal: a created file's content, or an edited file's diff."""

    path: str
    #: Whole content for a created file; a unified diff for an edited one.
    body: str
    is_diff: bool


@dataclass
class Proposal:
    """What a person reviews."""

    target_repository: str
    branch: str
    task: str
    files: list[ProposedFile] = field(default_factory=list)
    rationale: str = ""
    disclosures: list[str] = field(default_factory=list)
    state: ProposalState = ProposalState.COMPOSED
    #: Platform-authored, never model-authored (041, FR-031). Correlation id, what was
    #: consulted, and the per-file digests, so a reviewer can trace the proposal back to the
    #: run that made it without leaving the page.
    #:
    #: Separate from `rationale` because the two have different authors and therefore different
    #: trust: the rationale is agent-controlled content and is scanned as such, while this is
    #: the platform's own statement about its own run.
    provenance: list[str] = field(default_factory=list)

    @property
    def limits(self) -> tuple[str, ...]:
        """Unconditional, and last. 037's finding transfers: a reviewer handed a clean artefact
        reads "clean" as "correct" unless it says otherwise, and the failure this feature is
        most likely to cause is a review that has been reassured rather than informed.
        """
        return (DERIVATIVE_LIMIT, *self.disclosures)

    def render(self) -> str:
        """The body a reviewer reads. Structured sections, then the one free-text field, then
        the limits — which are last so nothing follows them and reframes them.
        """
        lines = [f"## {self.task}", "", "### Files"]
        lines += [f"- `{f.path}` ({'edited' if f.is_diff else 'created'})" for f in self.files]
        if self.rationale.strip():
            lines += ["", "### Rationale", "", self.rationale.strip()]
        if self.provenance:
            # After the rationale and before the limits: a reviewer reads what was proposed,
            # then where it came from, then what it does not cover.
            lines += ["", "### Provenance", ""]
            lines += [f"- {entry}" for entry in self.provenance]
        lines += ["", "### Limits"]
        lines += [f"- {limit}" for limit in self.limits]
        return "\n".join(lines)


def compose(
    *,
    artifact: AuthoredArtifact,
    target_repository: str,
    branch: str,
    task: str,
    authored_content: dict[str, str],
    subject_content: dict[str, str],
    rationale: str = "",
    correlation_id: str = "",
    consulted: tuple[str, ...] = (),
    base_commit: str = "",
) -> Proposal:
    """Build the proposal from the **workspace**, never from the subject.

    ``subject_content`` is consulted only for paths the agent already wrote, to compute a diff.
    The subject is never enumerated here — which is the property, not a discipline.

    Raises:
        ValueError: the artefact claims truncation and carries no note. A proposal built from
            part of a codebase that does not say so reads identically to a complete one.
    """
    if artifact.truncated and not artifact.truncation_note.strip():
        raise ValueError(
            "the artefact is truncated and carries no note; an undisclosed partial read is a "
            "claim about work nobody did"
        )

    files: list[ProposedFile] = []
    for authored in artifact.files:
        new = authored_content[authored.path]
        if authored.edited:
            before = subject_content.get(authored.path, "")
            diff = "\n".join(
                difflib.unified_diff(
                    before.splitlines(),
                    new.splitlines(),
                    fromfile=f"a/{authored.path}",
                    tofile=f"b/{authored.path}",
                    lineterm="",
                )
            )
            files.append(ProposedFile(path=authored.path, body=diff, is_diff=True))
        else:
            files.append(ProposedFile(path=authored.path, body=new, is_diff=False))

    disclosures: list[str] = []
    if artifact.truncated:
        disclosures.append(f"Truncated read: {artifact.truncation_note}")
    if artifact.is_empty:
        disclosures.append(
            "This proposal contains no files. The run completed and produced nothing, which is "
            "an outcome rather than a failure."
        )

    # PLATFORM-AUTHORED, and assembled after the model's half rather than mixed into it
    # (041, FR-031). A reviewer who can see the correlation id, what was read, and the digest
    # of every file can reconcile this page against the trail; one who cannot is being asked
    # to trust prose.
    provenance: list[str] = []
    if correlation_id:
        provenance.append(f"Run: `{correlation_id}`")
    if base_commit:
        provenance.append(f"Analysed at commit `{base_commit}`")
    if consulted:
        provenance.append(
            f"Consulted {len(consulted)} subject path(s): "
            + ", ".join(f"`{path}`" for path in consulted)
        )
    provenance += [f"`{f.path}` — `{f.digest}`" for f in artifact.files]
    if artifact.truncated:
        # Repeated here as well as in the limits: the disclosure a reviewer most needs is the
        # one saying the analysis did not see everything, and a page they skim to the end of
        # should not be the only place it appears.
        provenance.append(f"**Partial read** — {artifact.truncation_note}")

    return Proposal(
        target_repository=target_repository,
        branch=branch,
        task=task,
        files=files,
        rationale=rationale,
        disclosures=disclosures,
        provenance=provenance,
    )


def scannable_text(proposal: Proposal) -> list[tuple[str, str]]:
    """Everything the containment scan must cover, as (location, text).

    **The whole proposal**, not only the prose: authored file contents, the *added* lines of
    every diff, and the rendered body. Scoping this to prose is the defect that left authored
    bytes unscanned for two drafts — an authored file is agent-controlled content, and the file
    set being unforgeable says nothing about what is inside it.
    """
    out: list[tuple[str, str]] = []
    for f in proposal.files:
        if f.is_diff:
            added = "\n".join(
                line[1:] for line in f.body.splitlines() if line.startswith("+") and line != "+++"
            )
            out.append((f"file:{f.path}", added))
        else:
            out.append((f"file:{f.path}", f.body))
    out.append(("body", proposal.render()))
    return out


__all__ = [
    "DERIVATIVE_LIMIT",
    "Proposal",
    "ProposalState",
    "ProposedFile",
    "branch_for",
    "compose",
    "scannable_text",
]
