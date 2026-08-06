# SPDX-License-Identifier: Apache-2.0
"""The agent authors, and a person merges (038, ADR-0038).

Product-blind, like the rest of `core`: this package knows about workspaces, diffs and digests.
It does not know what Terraform or Vault are, and a change that taught it would put product
knowledge in the layer that is supposed to be able to govern anything.

## Which task runs what

The run is **one allocation, one correlation ID, two sequential tasks**. Every module below
belongs to exactly one of them, and the assignment is not cosmetic — an earlier draft gave the
publishing task work it could not do, because composition diffs *against the subject* and the
containment scan matches *subject files*, and the publishing task has no subject mount.

| Task | Runs | Sees |
| --- | --- | --- |
| `analyzer` | `read_subject`, `author_file`, `workspace`, | the subject (read-only), |
|            | `artifact`, `proposal`, `containment`        | `/alloc/data`            |
| `proposer` | `open_proposal`, `credential`                | `/alloc/data`, the host  |

**The proposer receives a finished, contained proposal and publishes it.** That is strictly
safer than mounting the subject twice: the task holding the credential never holds the analysed
content, so US3's exfiltration channel narrows to bytes that already passed containment.

**Sequential, and the `prestart` lifecycle is the only thing making it so.** `holder_identity`
derives from `NOMAD_ALLOC_ID`, which is per-allocation — so the two tasks are the *same* lease
holder. Concurrent, they would both pass `assert_held` and race on the checkpoint rather than
fence each other. The lease will not catch a violation of the ordering, which is why a row
asserts the lifecycle directly.

**The handoff is a checkpoint and a continuation, never a resume.** `resume_run` counts
attempts against `RESUME_ATTEMPT_CAP` and stops the run terminally past it, so routing a
designed-in handoff through it would spend attempt 1 of 5 on every healthy run and leave a
genuinely interrupted one with less margin than the platform believes it has.
"""

from core.authoring.artifact import AuthoredArtifact, AuthoredFile, record_artifact
from core.authoring.containment import ContainmentCode, ContainmentRefused, Finding
from core.authoring.proposal import Proposal, ProposalState, branch_for, compose
from core.authoring.provenance import Provenance, ProvenanceLedger
from core.authoring.request import AuthoringRequest, RequestRefused, resolve_subject_mount
from core.authoring.workspace import Trees, WorkspaceRefused

__all__ = [
    "AuthoredArtifact",
    "AuthoredFile",
    "AuthoringRequest",
    "ContainmentCode",
    "ContainmentRefused",
    "Finding",
    "Proposal",
    "ProposalState",
    "Provenance",
    "ProvenanceLedger",
    "RequestRefused",
    "Trees",
    "WorkspaceRefused",
    "branch_for",
    "compose",
    "record_artifact",
    "resolve_subject_mount",
]
