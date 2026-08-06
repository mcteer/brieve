# SPDX-License-Identifier: Apache-2.0
"""What the agent produced — paths and digests, never content (038, FR-004).

**No content field, deliberately.** `ARTIFACT_AUTHORED` carries paths and per-path digests
because the artefact is a **derivative of the requester's private repository**, and an
append-only trail holding a verbatim copy puts it somewhere nobody can delete it.

`PROGRAM_SUBMITTED`'s verbatim rule does not transfer, and the difference is worth stating
rather than assuming: that member records *the model's own words as the cause*, which is
`TURN_RECORDED`'s argued case. This one records somebody else's private code, one derivation
removed. The content a reviewer needs is in the proposal, which is where a reviewer reads it.

**An empty artefact is an outcome, not a failure** (FR-021's edge case). A run that produced
nothing completes, records that it produced nothing, and is distinguishable from a run that
died — because "the agent found nothing worth writing" and "the agent fell over" are different
answers and only one of them means try again.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from core.audit.schema import AuditEventType
from core.authoring.workspace import Trees, digest_of
from core.run import GovernedRun


@dataclass(frozen=True)
class AuthoredFile:
    """One file the agent wrote, and whether it already existed in the subject."""

    path: str
    digest: str
    #: True when the subject holds this path — so the proposal shows a **diff** rather than a
    #: whole file. Decided against the subject at authoring time rather than at composition,
    #: because the subject is mounted for the analysing task and not for the publishing one.
    edited: bool


@dataclass
class AuthoredArtifact:
    """The set of paths the agent wrote, in write order.

    Mutable during the run and read as a whole afterwards: `author_file` appends, and nothing
    else does. A path written twice keeps its first position and takes the later digest, which
    is what "in write order" has to mean once a file can be revised.
    """

    files: list[AuthoredFile] = field(default_factory=list)
    #: The subject was not read in full. Disclosed in the proposal — a proposal built from part
    #: of a codebase that does not say so is a claim about work nobody did.
    truncated: bool = False
    #: Required non-empty when ``truncated``. Refused otherwise at composition.
    truncation_note: str = ""

    @property
    def paths(self) -> tuple[str, ...]:
        return tuple(f.path for f in self.files)

    @property
    def created(self) -> frozenset[str]:
        return frozenset(f.path for f in self.files if not f.edited)

    @property
    def edited(self) -> frozenset[str]:
        return frozenset(f.path for f in self.files if f.edited)

    @property
    def is_empty(self) -> bool:
        """No files. A legitimate outcome, and the proposal says so."""
        return not self.files

    def record(self, *, path: str, content: str, trees: Trees) -> AuthoredFile:
        """Note a write. Idempotent in position, current in digest."""
        entry = AuthoredFile(
            path=path,
            digest=digest_of(content),
            edited=trees.exists_in_subject(path),
        )
        for i, existing in enumerate(self.files):
            if existing.path == path:
                self.files[i] = entry
                return entry
        self.files.append(entry)
        return entry

    def as_payload(self) -> dict[str, object]:
        """What `ARTIFACT_AUTHORED` carries. Digests, never content — see the module docstring.

        The shape is also enforced at the sink by `assert_payload_shape`, so a later caller
        adding a `content` key fails the write rather than the review.
        """
        return {
            "paths": list(self.paths),
            "digests": {f.path: f.digest for f in self.files},
            "created": sorted(self.created),
            "edited": sorted(self.edited),
            "truncated": self.truncated,
        }


def record_artifact(
    run: GovernedRun,
    artifact: AuthoredArtifact,
    *,
    consulted: Sequence[str] = (),
) -> None:
    """Write `ARTIFACT_AUTHORED` — including for an empty artefact.

    **Especially for an empty one.** The record is how "produced nothing" stays distinguishable
    from "never got there", and omitting it for the empty case would erase exactly the
    distinction FR-021's edge case exists to keep.

    ``consulted`` is the subject paths `read_subject` returned, in read order — FR-004's *"what
    was consulted to produce it"*, so a reader can reconstruct the **work** rather than only its
    outcome. Paths, never content, for the same reason the artefact carries digests.

    **External guidance is not here and needs no second path.** ADR-0030's provenance-at-read
    already archives a URL, a timestamp and a content hash for anything fetched fresh
    (`core.packs.consulted`), and ADR-0004's skills-first layering means the agent applies
    adopted skills with retrieval only on a gap. This records the one thing that mechanism does
    not see: which files of the *subject* were read.
    """
    payload = artifact.as_payload()
    payload["consulted"] = list(consulted)
    run.audit_sink.append_event(
        correlation_id=run.correlation_id,
        tenant_id=run.tenant_id,
        event_type=AuditEventType.ARTIFACT_AUTHORED,
        payload=payload,
    )


__all__ = ["AuthoredArtifact", "AuthoredFile", "record_artifact"]
