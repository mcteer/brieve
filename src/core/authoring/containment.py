# SPDX-License-Identifier: Apache-2.0
"""Nothing the agent read leaves with what it wrote (038, FR-010–013b; research R21, R22).

**Two claims of different strength, and they are two functions for that reason.**

| Claim | Covers | Strength |
| --- | --- | --- |
| which **paths** appear | the file set | **structural** — the workspace is the only source |
| what those paths **contain** | authored bytes, diff additions, prose | **inspected** — below |

The path half needs no code here: :mod:`core.authoring.proposal` builds the file set from
`artifact.paths`, so a file the agent never wrote has no route in. An earlier draft wrote that
up as containment being *"not expressible"* — true of paths, **false of bytes**, since an
authored file is agent-controlled content and the agent can write whatever it read into a file
it did create. Nothing scanned that for two drafts. A guarantee that is genuinely airtight over
a narrow subject is the easiest kind to over-generalise: the confidence transfers and the
reasoning does not.

**The threshold is two conditions because either alone fails.** Once the scan covers *code*,
short overlaps are not suspicious — they are the point: an integration reuses the subject's
identifiers, type names, config keys and signatures. A character count alone trips on a long
identifier or a URL; a line count alone trips on two short adjacent lines any integration would
reproduce. Together, no single token can trip the scan while a copied comment block, docstring
or function body does.

**Diff context needs no exemption.** The scan ignores files *in* `artifact.paths`, and an edited
file is in that set by definition — so FR-013b holds without a special case, which is what stops
a rule that would forbid editing.

**The residual risk, stated rather than discovered**: a determined **paraphrase** defeats a
verbatim scan anywhere it runs. That is bounded — by the structured composition on the prose
side, by the correctness gates on the content side — rather than eliminated.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum

from core.audit.schema import AuditEventType
from core.authoring.workspace import digest_of
from core.errors import CoreError
from core.run import GovernedRun

#: A span refuses only when it is at least this long **and** spans at least two non-blank
#: lines. 120 characters is a couple of lines of real code — an order of magnitude above
#: identifier scale, and below a copied paragraph. Stated with its reasoning because a
#: threshold nobody fixed is one that gets tuned until the suite passes.
MIN_SPAN_CHARS = 120
MIN_SPAN_LINES = 2

_WHITESPACE = re.compile(r"\s+")


class ContainmentCode(StrEnum):
    """Why something was refused. Two codes for analysed content, not one.

    A leak in the code and a leak in the description are different mistakes with different
    fixes, and a reviewer should not have to go looking for which one happened.
    """

    SECRET_IN_OUTPUT = "secret_value_in_output"
    ANALYSED_IN_ARTIFACT = "analysed_content_in_artifact"
    ANALYSED_IN_PROSE = "analysed_content_in_prose"


class ContainmentRefused(CoreError):
    """Something that must not leave was found heading into an artefact.

    Carries a code, a location and a digest — **never the matched text**. `CANARY_CONTACT`'s
    rule, for its reason: the record of a leak must not be a second copy of what leaked.
    """

    def __init__(self, message: str, *, code: ContainmentCode, location: str, digest: str) -> None:
        super().__init__(message)
        self.code = code
        self.location = location
        self.digest = digest


@dataclass(frozen=True)
class Finding:
    """One refusal, in the shape the audit member carries."""

    code: ContainmentCode
    location: str
    digest: str


def _normalise(text: str) -> str:
    return _WHITESPACE.sub(" ", text).strip()


def _spans(text: str) -> Iterable[str]:
    """Every window of at least MIN_SPAN_LINES consecutive non-blank lines.

    Windows rather than the whole text, because a match has to be *located* — a reviewer
    handed "something in this file matched" has been told less than nothing.
    """
    lines = [line for line in text.splitlines() if line.strip()]
    for start in range(len(lines)):
        for end in range(start + MIN_SPAN_LINES, len(lines) + 1):
            window = _normalise("\n".join(lines[start:end]))
            if len(window) >= MIN_SPAN_CHARS:
                yield window
                break


def scan_for_analysed_content(
    *,
    text: str,
    location: str,
    subject_files: Mapping[str, str],
    authored_paths: frozenset[str],
    code: ContainmentCode,
) -> Finding | None:
    """Find a verbatim span from an **untouched** subject file, or return None.

    ``subject_files`` is path → content for the files the analysis read. Files in
    ``authored_paths`` are skipped: the change is allowed to contain itself, and an edited
    file's diff carries its surrounding context because that is what a diff *is*.
    """
    haystacks = {
        path: _normalise(content)
        for path, content in subject_files.items()
        if path not in authored_paths
    }
    if not haystacks:
        return None
    for span in _spans(text):
        for path, content in haystacks.items():
            if span in content:
                return Finding(code=code, location=f"{location}:{path}", digest=digest_of(span))
    return None


def scan_for_secrets(
    *, text: str, location: str, detectors: Iterable[re.Pattern[str]]
) -> Finding | None:
    """Find a secret-shaped value, or return None.

    The detector set is supplied rather than owned here, so the same patterns govern files,
    commits and prose — one implementation, three subjects. A second copy would eventually
    disagree with the first about what a secret looks like.
    """
    for pattern in detectors:
        match = pattern.search(text)
        if match is not None:
            return Finding(
                code=ContainmentCode.SECRET_IN_OUTPUT,
                location=location,
                digest=digest_of(match.group(0)),
            )
    return None


def record_refusal(run: GovernedRun, finding: Finding) -> None:
    """Write `CONTAINMENT_REFUSED` — codes, locations and digests only.

    The payload-shape gate at the sink enforces the same rule, so a later caller adding an
    ``excerpt`` fails the write rather than the review. Both, because a rule enforced in one
    place is a rule that holds until somebody writes a second call site.
    """
    run.audit_sink.append_event(
        correlation_id=run.correlation_id,
        tenant_id=run.tenant_id,
        event_type=AuditEventType.CONTAINMENT_REFUSED,
        payload={
            "code": finding.code.value,
            "location": finding.location,
            "digest": finding.digest,
        },
    )


__all__ = [
    "MIN_SPAN_CHARS",
    "MIN_SPAN_LINES",
    "ContainmentCode",
    "ContainmentRefused",
    "Finding",
    "record_refusal",
    "scan_for_analysed_content",
    "scan_for_secrets",
]
