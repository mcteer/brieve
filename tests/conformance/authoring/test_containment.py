# SPDX-License-Identifier: Apache-2.0
"""C1-C8 — nothing the agent read leaves with what it wrote (038, US3).

**The stub most available in this feature** is a containment check that only ever sees clean
input: a must-deny suite whose subject never contains a secret a generator could reach. C1 seeds
a real one, and `test_c1_can_fail_...` removes it and asserts C1 then fails — because a row that
cannot fail is not a row.

**C2 and C7 are the two halves, and reading either as covering both is the defect this suite
exists to prevent.** C2 asserts an untouched file cannot appear — a *property*, since the
proposal is built from the workspace. C7 asserts an authored file carrying analysed content is
refused — a *check*, because an authored file is agent-controlled bytes and nothing structural
stops the agent copying what it read into a file it did create.
"""

from __future__ import annotations

import pytest

from core.authoring.artifact import AuthoredArtifact
from core.authoring.containment import (
    MIN_SPAN_CHARS,
    ContainmentCode,
    scan_for_analysed_content,
    scan_for_secrets,
)
from core.authoring.proposal import Proposal, branch_for, compose, scannable_text
from core.authoring.tool import FileAuthor
from core.authoring.workspace import Trees
from tests.conformance.authoring.conftest import (
    SECRET_DETECTORS,
    SEEDED_SECRET,
    SEEDED_UNRELATED,
)

MODULE = "modules/secrets/main.tf"


def _proposal(
    trees: Trees, author: FileAuthor, artifact: AuthoredArtifact, **kw: object
) -> Proposal:
    subject_content = {
        p: (trees.subject / p).read_text() for p in artifact.paths if trees.exists_in_subject(p)
    }
    return compose(
        artifact=artifact,
        target_repository="acme/app",
        branch=branch_for("run-1:0:open_proposal"),
        task="Wire the application to dynamic database secrets",
        authored_content=author.contents,
        subject_content=subject_content,
        **kw,  # type: ignore[arg-type]
    )


def test_row_c1_a_seeded_credential_reaches_neither_files_commits_nor_prose(
    trees: Trees, author: FileAuthor, artifact: AuthoredArtifact
) -> None:
    """C1 — FR-010, SC-003. By assertion over the artefact, never by inspection."""
    author(
        {"path": MODULE, "content": 'data "vault_generic_secret" "db" {\n  path = "db/creds"\n}\n'}
    )
    proposal = _proposal(trees, author, artifact, rationale="Uses a dynamic secret source.")

    for location, text in scannable_text(proposal):
        assert SEEDED_SECRET not in text, f"the seeded credential reached {location}"
        assert scan_for_secrets(text=text, location=location, detectors=SECRET_DETECTORS) is None


def test_row_c1_can_fail_when_the_subject_carries_no_secret(
    trees: Trees, author: FileAuthor, artifact: AuthoredArtifact
) -> None:
    """**Prove C1 can fail.** Put the secret where a generator could reach it, and assert the
    detector fires — so a fixture that quietly stopped seeding one would break this row rather
    than silently greening C1.
    """
    author({"path": MODULE, "content": f'password = "{SEEDED_SECRET}"\n'})
    proposal = _proposal(trees, author, artifact)
    findings = [
        scan_for_secrets(text=text, location=loc, detectors=SECRET_DETECTORS)
        for loc, text in scannable_text(proposal)
    ]
    assert any(f is not None for f in findings), (
        "the detector did not fire on a secret placed directly in an authored file — C1 would "
        "pass over a subject that never contained one, which is ADR-0047's passing stub"
    )


def test_row_c2_an_untouched_file_cannot_appear_in_the_proposal(
    trees: Trees, author: FileAuthor, artifact: AuthoredArtifact
) -> None:
    """C2 — FR-013, FR-013a, SC-004. A property, not a check.

    **And it covers paths only.** The guarantee is that no untouched file *appears*, not that no
    analysed content does — see C7 for the other half.
    """
    author({"path": MODULE, "content": 'resource "null_resource" "x" {}\n'})
    proposal = _proposal(trees, author, artifact)

    assert [f.path for f in proposal.files] == [MODULE]
    assert "app/ledger.py" not in {f.path for f in proposal.files}
    for _, text in scannable_text(proposal):
        assert SEEDED_UNRELATED.strip() not in text


def test_row_c3_diff_context_is_the_change_not_a_leak(
    trees: Trees, author: FileAuthor, artifact: AuthoredArtifact, subject_files: dict[str, str]
) -> None:
    """C3 — FR-013b. A rule that forbade surrounding context would forbid editing."""
    edited = "app/main.py"
    author({"path": edited, "content": "def main() -> None:\n    print('hello')\n    setup()\n"})
    proposal = _proposal(trees, author, artifact)

    diff = next(f for f in proposal.files if f.path == edited)
    assert diff.is_diff
    assert "print('hello')" in diff.body, "the diff dropped its context, which is the change"

    for location, text in scannable_text(proposal):
        finding = scan_for_analysed_content(
            text=text,
            location=location,
            subject_files=subject_files,
            authored_paths=frozenset(artifact.paths),
            code=ContainmentCode.ANALYSED_IN_ARTIFACT,
        )
        assert finding is None, "an edited file's own context was refused as a leak"


def test_row_c7_an_authored_file_carrying_analysed_content_is_refused(
    trees: Trees, author: FileAuthor, artifact: AuthoredArtifact, subject_files: dict[str, str]
) -> None:
    """C7 — FR-012, FR-013, SC-004. **The row the containment story was missing.**

    The path half is structural, so an untouched file cannot appear — and nothing stopped the
    agent copying what it read into a file it *did* create.
    """
    author({"path": MODULE, "content": f"# Notes from the codebase:\n# {SEEDED_UNRELATED}\n"})
    proposal = _proposal(trees, author, artifact)

    findings = [
        scan_for_analysed_content(
            text=text,
            location=location,
            subject_files=subject_files,
            authored_paths=frozenset(artifact.paths),
            code=ContainmentCode.ANALYSED_IN_ARTIFACT,
        )
        for location, text in scannable_text(proposal)
    ]
    hit = next((f for f in findings if f is not None), None)
    assert hit is not None, "analysed content copied into an authored file was not refused"
    assert hit.code is ContainmentCode.ANALYSED_IN_ARTIFACT
    assert hit.digest and SEEDED_UNRELATED.strip() not in hit.digest


def test_row_c7_prose_carries_its_own_code(
    trees: Trees, author: FileAuthor, artifact: AuthoredArtifact, subject_files: dict[str, str]
) -> None:
    """C4 — a rationale quoting an untouched subject file is refused, with the prose code.

    Two codes rather than one: a leak in the code and a leak in the description are different
    mistakes with different fixes, and a reviewer should not have to go looking.
    """
    author({"path": MODULE, "content": 'resource "null_resource" "x" {}\n'})
    proposal = _proposal(trees, author, artifact, rationale=f"For context:\n{SEEDED_UNRELATED}")

    body = proposal.render()
    finding = scan_for_analysed_content(
        text=body,
        location="body",
        subject_files=subject_files,
        authored_paths=frozenset(artifact.paths),
        code=ContainmentCode.ANALYSED_IN_PROSE,
    )
    assert finding is not None
    assert finding.code is ContainmentCode.ANALYSED_IN_PROSE


def test_row_c4_companion_a_paraphrase_is_not_caught(
    trees: Trees, author: FileAuthor, artifact: AuthoredArtifact, subject_files: dict[str, str]
) -> None:
    """**The honest limit, asserted rather than assumed.**

    A determined paraphrase defeats a verbatim scan anywhere it runs. Recording that in a row is
    what stops "containment is structural" being read as covering the description — the exact
    conflation FR-013 was written to prevent. If this row ever starts failing, the scan has
    become something other than verbatim and the claim in the docstrings must change with it.
    """
    paraphrase = (
        "The finance team's settlement maths damps against unmatched residuals from the\n"
        "previous period, and the approach has been theirs alone since roughly 2019.\n"
    )
    author({"path": MODULE, "content": f"# {paraphrase}\n"})
    proposal = _proposal(trees, author, artifact)

    findings = [
        scan_for_analysed_content(
            text=text,
            location=location,
            subject_files=subject_files,
            authored_paths=frozenset(artifact.paths),
            code=ContainmentCode.ANALYSED_IN_ARTIFACT,
        )
        for location, text in scannable_text(proposal)
    ]
    assert all(f is None for f in findings), (
        "a paraphrase was caught — good, but the residual risk documented across this feature "
        "says it is not, and the documentation must be corrected rather than this row relaxed"
    )


def test_row_c8_legitimate_reuse_is_not_refused(
    trees: Trees, author: FileAuthor, artifact: AuthoredArtifact, subject_files: dict[str, str]
) -> None:
    """C8 — FR-013b extended to content. Reusing the subject's vocabulary IS integrating.

    Both threshold conditions are asserted independently: a long **single-line** span passes,
    and two short adjacent lines pass. Only ≥ MIN_SPAN_CHARS across ≥ 2 non-blank lines refuses.
    """
    long_single_line = "x" * (MIN_SPAN_CHARS + 80)
    (trees.subject / "app" / "wide.py").write_text(long_single_line + "\n")
    subject_files["app/wide.py"] = long_single_line + "\n"

    author(
        {
            "path": MODULE,
            "content": (
                f"# {long_single_line}\n"
                "DATABASE_PASSWORD = None\n"
                "DEBUG = False\n"
                "def main() -> None:\n"
            ),
        }
    )
    proposal = _proposal(trees, author, artifact)

    findings = [
        scan_for_analysed_content(
            text=text,
            location=location,
            subject_files=subject_files,
            authored_paths=frozenset(artifact.paths),
            code=ContainmentCode.ANALYSED_IN_ARTIFACT,
        )
        for location, text in scannable_text(proposal)
    ]
    assert all(f is None for f in findings), (
        "identifier reuse and a long single-line span were refused; a scan tuned until it "
        "stopped complaining would forbid integrating, which is what it exists to enable"
    )


def test_row_c5_truncation_is_disclosed(
    trees: Trees, author: FileAuthor, artifact: AuthoredArtifact
) -> None:
    """C5 — FR-005b. A partial read that does not say so reads identically to a complete one."""
    author({"path": MODULE, "content": 'resource "null_resource" "x" {}\n'})
    artifact.truncated = True
    artifact.truncation_note = "read budget of 4 MiB reached after 812 files"

    proposal = _proposal(trees, author, artifact)
    assert any("Truncated read" in limit for limit in proposal.limits)

    artifact.truncation_note = ""
    with pytest.raises(ValueError, match="truncated"):
        _proposal(trees, author, artifact)


def test_row_c6_the_limit_containment_cannot_reach_is_in_the_artefact(
    trees: Trees, author: FileAuthor, artifact: AuthoredArtifact
) -> None:
    """C6 — the spec's edge case, in the proposal rather than in a footnote.

    Where the analysed source is itself the sensitive thing, an authored integration is a
    derivative of exactly that. Containment bounds what is COPIED and cannot bound what is
    IMPLIED, and a reviewer needs that before they merge rather than after.
    """
    author({"path": MODULE, "content": 'resource "null_resource" "x" {}\n'})
    proposal = _proposal(trees, author, artifact)

    limits = " ".join(proposal.limits)
    assert "derivative" in limits.lower()
    assert "implied" in limits.lower()
    assert "COPIED" in limits or "copied" in limits.lower()
    assert proposal.limits[0].startswith("This change is a derivative"), (
        "the structural limit must be unconditional and first among the limits"
    )
