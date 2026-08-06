# SPDX-License-Identifier: Apache-2.0
"""Three platform tools, and the gate in front of them (038; research R2, R23, R29).

`read_subject` (read) · `author_file` (**write** — the registry's first) · `open_proposal`
(write, non-repeatable, observer required).

**Platform tools rather than pack tools, and the argument is one argument used twice.**
Producing a file is the same act for every product — a Terraform module and a Vault integration
are written identically — so a per-pack copy would be N implementations of one containment rule.
**Publishing is equally product-blind**: a pull request against a module and one against
application code are the same act. ADR-0064 amends ADR-0038's "pack tool target" clause rather
than departing from it quietly, because the eval suites are answering-shaped and a pack carrying
one PR-opening tool has no expertise for them to measure.

**What still gates authoring, three ways**: the **ceiling** decides whether a definition may
call these at all; **task scope** narrows that ceiling per task, so the analysing half's
effective authority carries nothing that egresses; and the **request** refuses a pack that
declares no authoring workflow. The pack's declared workflow no longer gates *publishing* —
that is ADR-0064's stated cost, and `request.py` carries the check that remains.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from core.authoring.artifact import AuthoredArtifact
from core.authoring.workspace import Trees, WorkspaceRefused
from core.authority.errors import ResolutionRefused
from core.authority.matrix import MatrixFallback, QualifiedCell, resolve_with_fallback
from core.observation.types import Observer
from core.registry.memory import ToolHandler, ToolRegistry

#: Registered names. Each is reachable only through a definition's ceiling — the registry is
#: the opt-in switch, not a flag somebody must remember to set.
READ_SUBJECT = "read_subject"
AUTHOR_FILE = "author_file"
OPEN_PROPOSAL = "open_proposal"

#: The role a `write` cell must be qualified for. The matrix's third, unbound until 038.
WRITE_ROLE = "write"

#: 4 MiB of subject content per run, after which reads refuse and the truncation is disclosed.
#: A module plus the surrounding application configuration is kilobytes, so this is generous for
#: genuine integration work and far below a large monorepo — which is the case the disclosure
#: exists for. Fixed with its reasoning because an unfixed threshold is one that gets raised
#: until the corpus passes.
READ_BUDGET_BYTES = 4 * 1024 * 1024


def resolve_write_cell(
    pinned: str,
    cells: Mapping[str, QualifiedCell],
    *,
    available: frozenset[str],
    agent_definition_id: str,
) -> tuple[QualifiedCell, MatrixFallback | None]:
    """The qualified `write` cell, or stop (FR-016).

    **Landed foundational deliberately.** This is US5's first acceptance scenario, and a
    capability that could run unqualified for even one commit is the gap 026 found for `ask`.

    No branch of its own: `resolve_with_fallback` already returns a cell that is present,
    un-withdrawn and qualified for this exact role, or raises. Adding a decision here would add
    the branch that function was written not to have.

    Raises:
        ResolutionRefused: `unqualified_cell` / `cell_withdrawn` / `no_qualified_fallback` —
            distinguishable from a provider being unavailable, which sends an operator to the
            outage rather than to governance.
    """
    return resolve_with_fallback(
        WRITE_ROLE,  # type: ignore[arg-type]
        pinned,
        cells,
        available=available,
        agent_definition_id=agent_definition_id,
    )


class SubjectReader:
    """`read_subject`'s handler: the governed way to read the mounted subject.

    **The read path FR-014, FR-005b and FR-004 were all written against and none of them had.**
    A read-only mount read by ordinary file access offers no hook for the injection lens, no
    place to record an attempt, nothing countable to truncate, and nothing enumerable to report
    as "what was consulted".
    """

    def __init__(self, trees: Trees, *, budget_bytes: int = READ_BUDGET_BYTES) -> None:
        self._trees = trees
        self._budget = budget_bytes
        self._spent = 0
        self._read: list[str] = []
        self.truncated = False

    @property
    def consulted(self) -> tuple[str, ...]:
        """Every subject path read, in order. FR-004's "what was consulted"."""
        return tuple(self._read)

    def __call__(self, arguments: Mapping[str, Any]) -> dict[str, Any]:
        path = str(arguments.get("path", "")).strip()
        if not path:
            raise ValueError("read_subject requires a 'path' argument")
        resolved = self._trees.resolve_in_subject(path)
        if not resolved.is_file():
            return {"path": path, "content": "", "present": False}
        content = resolved.read_text(errors="replace")
        cost = len(content.encode("utf-8"))
        if self._spent + cost > self._budget:
            # Refuse rather than truncate the file: half a file read as though whole is the
            # silent partial FR-005b exists to prevent, one level down.
            self.truncated = True
            return {"path": path, "content": "", "present": True, "over_budget": True}
        self._spent += cost
        self._read.append(path)
        return {"path": path, "content": content, "present": True}


class FileAuthor:
    """`author_file`'s handler: write into the workspace, and nowhere else.

    Returns paths and digests. The content stays in the workspace and reaches the proposal;
    it never reaches the trail, because the artefact is a derivative of a private repository
    and an append-only store holding a copy is one nobody can delete.
    """

    def __init__(self, trees: Trees, artifact: AuthoredArtifact) -> None:
        self._trees = trees
        self._artifact = artifact
        self.contents: dict[str, str] = {}

    def __call__(self, arguments: Mapping[str, Any]) -> dict[str, Any]:
        path = str(arguments.get("path", "")).strip()
        content = arguments.get("content")
        if not path:
            raise ValueError("author_file requires a 'path' argument")
        if not isinstance(content, str):
            raise ValueError("author_file requires a string 'content' argument")
        # Refuses absolute paths and any traversal that escapes, resolved rather than
        # string-matched. This is the only write surface in the platform (W3a).
        target = self._trees.resolve_in_workspace(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        self.contents[path] = content
        authored = self._artifact.record(path=path, content=content, trees=self._trees)
        return {"path": authored.path, "digest": authored.digest, "edited": authored.edited}


@dataclass(frozen=True)
class AuthoringTools:
    """The handlers a registered authoring run holds, so a caller can read their state.

    Returned by `register_authoring_tools` rather than reconstructed, because the artefact and
    the consulted list live on the handlers and the caller needs both when the run finishes.
    """

    reader: SubjectReader
    author: FileAuthor
    artifact: AuthoredArtifact


def register_authoring_tools(
    registry: ToolRegistry,
    *,
    trees: Trees,
    artifact: AuthoredArtifact,
    budget_bytes: int = READ_BUDGET_BYTES,
) -> AuthoringTools:
    """Register the analysing half's tools against **this run's** trees.

    **Registered per run rather than once at import**, because both handlers hold run-scoped
    state: the workspace they may write to, and the artefact they accumulate. A module-level
    singleton would either share a workspace between runs or need a lookup that amounts to the
    same thing with more steps.

    That does not weaken the opt-in property. The **ceiling** still decides whether a definition
    may call these — registration makes a tool resolvable, and `authority.py` decides whether
    this run may reach it. A definition whose ceiling omits `author_file` has no authoring even
    though the registry knows the name.

    `open_proposal` is deliberately **not** here: it belongs to the publishing task, which holds
    no trees, and registering it beside these would put the credential-holding tool in the same
    place as the subject-reading ones.
    """
    reader = SubjectReader(trees, budget_bytes=budget_bytes)
    author = FileAuthor(trees, artifact)
    registry.register(READ_SUBJECT, reader, risk_class="read")
    registry.register(AUTHOR_FILE, author, risk_class="write")
    return AuthoringTools(reader=reader, author=author, artifact=artifact)


def register_proposal_tool(
    registry: ToolRegistry,
    *,
    handler: ToolHandler,
    observer: Observer,
) -> None:
    """Register `open_proposal` for the publishing task.

    **Non-repeatable with an observer, asserted here rather than inherited.** The pack loader
    refuses `observer_required` when a manifest declares a non-repeatable tool without one —
    and this is a platform tool (ADR-0064), so that check does not cover it. Opening a proposal
    twice creates two proposals; without an observer an interrupted publish resolves
    `CANNOT_DETERMINE` and parks the run.
    """
    registry.register(
        OPEN_PROPOSAL,
        handler,
        risk_class="write",
        repeatable=False,
        observer=observer,
    )


__all__ = [
    "AuthoringTools",
    "AUTHOR_FILE",
    "OPEN_PROPOSAL",
    "READ_BUDGET_BYTES",
    "READ_SUBJECT",
    "WRITE_ROLE",
    "FileAuthor",
    "ResolutionRefused",
    "SubjectReader",
    "WorkspaceRefused",
    "register_authoring_tools",
    "register_proposal_tool",
    "resolve_write_cell",
]
