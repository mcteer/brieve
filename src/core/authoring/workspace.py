# SPDX-License-Identifier: Apache-2.0
"""The two trees, and why there are two (038, FR-013a; research R5, R21).

| Tree | Mount | Contains | Written by |
| --- | --- | --- | --- |
| **subject** | read-only | the requester's repository | nobody — the mount forbids it |
| **workspace** | read-write | only what the agent authored | `author_file`, and nothing else |
| *(the platform's own tree)* | **absent** | — | — |

**The proposal is built from the workspace and never from the subject.** That is what FR-013a
asks for *about paths*: a file the agent did not write has no route into the proposal, because
the code that builds one never enumerates the subject — it reads it only for paths the agent
already wrote, to compute a diff.

**It says nothing about bytes, and an earlier draft of this design claimed otherwise.** An
authored file is agent-controlled content: the agent can write whatever it read into a file it
did create. So containment is two claims of different strength, and
:mod:`core.authoring.containment` keeps them as two functions for that reason — the path half
is structural, the content half is inspected, and one function would let the strong guarantee
read as covering both.

**The workspace lives in the shared allocation directory**, because the analysing task writes it
and the publishing task reads it. That is the handoff: `analyzer` composes and contains,
`proposer` publishes what already passed. The task holding the credential never holds the
analysed content.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from core.errors import CoreError

#: Where the two tasks meet. Nomad gives every task in a group the same allocation directory,
#: which is what makes a baton pass possible without a second allocation — and therefore
#: without a second correlation ID, which Principle IX would not have.
ALLOC_WORKSPACE = "/alloc/data/workspace"


class WorkspaceRefused(CoreError):
    """A write that would leave the workspace, or a read that would leave the subject."""


@dataclass(frozen=True)
class Trees:
    """The subject and the workspace, as resolved paths.

    Held together rather than passed separately because every containment property in this
    feature is a statement about the *relationship* between them, and two loose paths are two
    things a caller can get out of step.
    """

    subject: Path
    workspace: Path

    def resolve_in_workspace(self, relative: str) -> Path:
        """A path inside the workspace, or refuse.

        Refuses absolute paths and any traversal that escapes, resolved rather than string-
        matched — ``a/../../b`` is not caught by looking for ``..`` in the right places, and a
        symlink is not caught by looking at the string at all.
        """
        return _resolve_within(self.workspace, relative, tree="workspace")

    def resolve_in_subject(self, relative: str) -> Path:
        """A path inside the subject, or refuse. Reading only; nothing here writes."""
        return _resolve_within(self.subject, relative, tree="subject")

    def exists_in_subject(self, relative: str) -> bool:
        """Whether the subject holds this path — which is what makes an authored path `edited`.

        A refused path is not an existing one. A traversal that escapes the subject must not be
        able to report `True` and turn an out-of-tree file into an "edit".
        """
        try:
            return self.resolve_in_subject(relative).is_file()
        except WorkspaceRefused:
            return False


def _resolve_within(root: Path, relative: str, *, tree: str) -> Path:
    if not relative.strip():
        raise WorkspaceRefused(f"an empty path is not a path in the {tree}")
    candidate = Path(relative)
    if candidate.is_absolute():
        raise WorkspaceRefused(
            f"{relative!r} is absolute; a path in the {tree} is relative to it, and an absolute "
            f"path is a request to write somewhere else wearing a relative path's clothes"
        )
    resolved_root = root.resolve()
    resolved = (resolved_root / candidate).resolve()
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise WorkspaceRefused(
            f"{relative!r} resolves outside the {tree} at {resolved_root}; resolved rather than "
            f"string-matched, because 'a/../../b' passes a check for '..' in the wrong place"
        )
    return resolved


def digest_of(content: str) -> str:
    """The digest carried in `ARTIFACT_AUTHORED`, in place of the content itself."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


__all__ = ["ALLOC_WORKSPACE", "Trees", "WorkspaceRefused", "digest_of"]
