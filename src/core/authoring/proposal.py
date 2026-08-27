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
import re
from dataclasses import dataclass, field
from enum import StrEnum

from core.authoring.artifact import AuthoredArtifact
from core.authoring.tool import is_dotenv_template

#: GitHub-comfortable title length. The intake task is often a pasted URL plus a paragraph;
#: that string is the Request section, never the title.
TITLE_LIMIT = 72

_URL = re.compile(r"https?://\S+", re.IGNORECASE)
_REPO_LINE = re.compile(r"^repository:\s*\S+\s*$", re.IGNORECASE | re.MULTILINE)
#: Conversational lead-in. The gist starts at the verb of the request.
_FILLER = re.compile(
    r"^(?:please\s+)?"
    r"(?:i\s+(?:need|want|would like)\s+you\s+to\s+"
    r"|can\s+you\s+(?:please\s+)?"
    r"|could\s+you\s+(?:please\s+)?"
    r"|would\s+you\s+(?:please\s+)?"
    r"|please\s+)",
    re.IGNORECASE,
)

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


def _clip_title(text: str) -> str:
    """Fit ``text`` to ``TITLE_LIMIT`` on a word boundary."""
    text = text.strip().strip("\"'")
    if len(text) <= TITLE_LIMIT:
        return text
    cut = text[:TITLE_LIMIT]
    space = cut.rfind(" ")
    if space >= TITLE_LIMIT // 2:
        cut = cut[:space]
    return cut.rstrip(" ,;:") + "…"


def _one_line_summary(text: str) -> str:
    """First sentence, no URL, no ``Files:`` tail — a title candidate, not a prompt dump."""
    text = _URL.sub("", text)
    text = _REPO_LINE.sub("", text)
    text = re.sub(r"(?i)\s+files:\s+\S.*$", "", text)
    text = " ".join(text.split()).strip(" :-")
    if not text:
        return ""
    sentence = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)[0]
    sentence = sentence.rstrip(".!?").strip()
    if not sentence:
        return ""
    if sentence[0].islower():
        sentence = sentence[0].upper() + sentence[1:]
    return _clip_title(sentence)


def _task_gist(task: str) -> str:
    """What was asked, short enough for ``--title``. Never a URL, never the whole prompt."""
    text = _FILLER.sub("", task, count=1).strip(" :-")
    return _one_line_summary(text)


#: Trailing ``Files: a, b`` from ``draft_write_plan`` — a list, not a paragraph.
_PLAN_FILES = re.compile(r"(?i)^(.*?)\s+files:\s+(.+)$")


def files_from_write_plan(text: str) -> list[str]:
    """Paths listed after ``Files:`` in a write-plan blob. Empty if the blob has none."""
    raw = (text or "").strip()
    match = _PLAN_FILES.match(raw)
    if match is None:
        return []
    return [
        p.strip().strip("`")
        for p in match.group(2).split(",")
        if p.strip() and not is_dotenv_template(p.strip().strip("`"))
    ]


#: Platform fallback when the writer did not supply usage notes. Author → propose → a
#: person merges → a person applies (038).
DEFAULT_USAGE = (
    "Nothing in this pull request is applied until a person merges it.\n\n"
    "After merge, apply the change using this repository's usual workflow."
)


def format_rationale(text: str) -> str:
    """Turn a one-line write-plan blob into markdown; leave real markdown alone."""
    raw = (text or "").strip()
    if not raw:
        return ""
    if "\n" in raw or raw.startswith(("#", "-", "*")):
        return raw
    match = _PLAN_FILES.match(raw)
    if match is None:
        return raw
    summary = match.group(1).strip()
    paths = files_from_write_plan(raw)
    lines: list[str] = []
    if summary:
        lines.extend([summary, ""])
    if paths:
        lines.append("This pull request includes:")
        lines.extend(f"- `{path}`" for path in paths)
    return "\n".join(lines).strip()


def _files_title(files: list[ProposedFile]) -> str:
    first = files[0]
    verb = "Update" if first.is_diff else "Add"
    shown = first.path if len(first.path) <= 48 else first.path.rsplit("/", 1)[-1]
    if len(files) == 1:
        return f"{verb} {shown}"
    others = len(files) - 1
    noun = "other file" if others == 1 else "other files"
    return f"{verb} {shown} and {others} {noun}"


def title_for(*, files: list[ProposedFile], task: str, summary: str = "") -> str:
    """A reviewer title: a short summary of the change, never the raw intake.

    Prefer a model (or write-plan) summary. The intake paragraph is the Request section.
    Putting it in ``--title`` made every PR a prompt snippet. Naming only the first file
    (``Add main.tf``) made every PR interchangeable.
    """
    planned = _one_line_summary(summary)
    if planned:
        return planned
    gist = _task_gist(task)
    if gist:
        return gist
    if files:
        return _files_title(files)
    return "Authored changes"


@dataclass
class Proposal:
    """What a person reviews."""

    target_repository: str
    branch: str
    task: str
    files: list[ProposedFile] = field(default_factory=list)
    #: Platform-composed. Empty at construction is filled in ``__post_init__``.
    title: str = ""
    rationale: str = ""
    #: How a reviewer applies the change after merge. Platform section; model or fallback.
    usage: str = ""
    disclosures: list[str] = field(default_factory=list)
    #: ADOPTED PRACTICE THIS PLATFORM COULD NOT CARRY OUT (051, FR-016).
    #:
    #: Derived from the bound pack's manifest and from nothing else — never from the progress
    #: record, never from what a model said it did. That is what makes the text identical
    #: across two runs of different content (FR-018), and it is the same reason the plan gate
    #: was withdrawn: a check the platform cannot perform honestly belongs to the person who
    #: can, stated rather than left to be discovered.
    #:
    #: Deliberately NOT folded into `limits`, which is `DERIVATIVE_LIMIT` plus run-derived
    #: disclosures. Run-derived and run-independent text must not share a field.
    unsatisfiable_recommendations: tuple[str, ...] = ()
    state: ProposalState = ProposalState.COMPOSED
    #: Platform-authored, never model-authored (041, FR-031). Correlation id, what was
    #: consulted, and the per-file digests, so a reviewer can trace the proposal back to the
    #: run that made it without leaving the page.
    #:
    #: Separate from `rationale` because the two have different authors and therefore different
    #: trust: the rationale is agent-controlled content and is scanned as such, while this is
    #: the platform's own statement about its own run.
    provenance: list[str] = field(default_factory=list)
    #: MEASURED FACTS ABOUT WHAT THE CHANGE DOES, platform-rendered (042).
    #:
    #: A third author, and therefore a third trust level. `rationale` is the model's;
    #: `provenance` is the platform's account of its own run; this is a **product's** answer,
    #: transcribed. 042's impact check asks Vault what a token under the proposed policy could
    #: do, and the platform renders the reply — a model verdict may gate a step and never
    #: satisfies what evidence must show (Principle IX).
    #:
    #: Its own section rather than folded into `provenance`, because a reviewer asking "what
    #: does this now permit" does not look under a heading about where the proposal came from.
    #: Generic on purpose: `core.authoring` stays product-blind and 042 supplies the lines.
    evidence: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        cleaned = _clip_title(_URL.sub("", (self.title or "").strip()).strip("\"'"))
        if cleaned:
            self.title = cleaned
        else:
            self.title = title_for(files=self.files, task=self.task)

    @property
    def limits(self) -> tuple[str, ...]:
        """Unconditional, and last. 037's finding transfers: a reviewer handed a clean artefact
        reads "clean" as "correct" unless it says otherwise, and the failure this feature is
        most likely to cause is a review that has been reassured rather than informed.
        """
        return (DERIVATIVE_LIMIT, *self.disclosures)

    def render(self) -> str:
        """The body a reviewer reads. One platform template, every proposal.

        The agent does not invent a layout: compose fills these sections. The intake task
        is **Request**, not the heading — the heading is the short title.
        """
        rationale = format_rationale(self.rationale)
        usage = (self.usage or "").strip() or DEFAULT_USAGE
        lines = [
            "## Summary",
            "",
            self.title,
        ]
        if rationale:
            lines += ["", "## Rationale", "", rationale]
        lines += ["", "## How to use", "", usage, "", "## Request", ""]
        lines += [self.task.strip() or "(none supplied)", "", "## Files"]
        lines += [f"- `{f.path}` ({'edited' if f.is_diff else 'created'})" for f in self.files]
        if self.evidence:
            # Between the rationale and the provenance: the reviewer reads what was proposed,
            # then what it MEASURABLY does, then where it came from, then what is not covered.
            # Ahead of provenance because it is the question a policy review actually asks.
            lines += ["", "## Measured impact", ""]
            lines += [f"- {entry}" for entry in self.evidence]
        if self.provenance:
            # After the rationale and before the limits: a reviewer reads what was proposed,
            # then where it came from, then what it does not cover.
            lines += ["", "## Provenance", ""]
            lines += [f"- {entry}" for entry in self.provenance]
        if self.unsatisfiable_recommendations:
            # Between provenance and limits: where the work came from, then what the adopted
            # practice asked for and this platform could not do, then what is not covered.
            # Empty renders nothing — a heading with no bullets tells a reviewer less than no
            # heading at all.
            lines += ["", "## Adopted practice not carried out", ""]
            lines += [f"- {entry}" for entry in self.unsatisfiable_recommendations]
        lines += ["", "## Limits"]
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
    title: str = "",
    usage: str = "",
    summary: str = "",
    correlation_id: str = "",
    consulted: tuple[str, ...] = (),
    base_commit: str = "",
    unsatisfiable_recommendations: tuple[str, ...] = (),
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
        title=title or title_for(files=files, task=task, summary=summary),
        files=files,
        rationale=rationale,
        usage=usage,
        disclosures=disclosures,
        unsatisfiable_recommendations=unsatisfiable_recommendations,
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
    out.append(("title", proposal.title))
    out.append(("body", proposal.render()))
    return out


__all__ = [
    "DEFAULT_USAGE",
    "DERIVATIVE_LIMIT",
    "TITLE_LIMIT",
    "Proposal",
    "ProposalState",
    "ProposedFile",
    "branch_for",
    "compose",
    "format_rationale",
    "scannable_text",
    "title_for",
]
