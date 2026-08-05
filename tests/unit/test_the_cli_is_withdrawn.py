# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — the platform has three transports, and every document agrees.

ADR-0060 withdrew the CLI. The reason it needed a decision record rather than a find-and-
replace is that the count was **normative**: the constitution asserted "exactly four
transports — MCP, API, CLI, portal", and that document is what every `/speckit.analyze` pass
measures a specification against. A governing document naming a surface nobody built is the
failure mode ADR-0047 identified in tests, one level up — a passing stub asserts a property
nothing holds, and so does a clause describing a shape the platform does not have.

So the withdrawal is asserted rather than merely written. Without these rows, a future
amendment could restore the fourth transport to the prose and nothing would notice until a
reader believed it.

**The trap, and it is the same one `test_parked_is_gone.py` documents:** the constitution's
Sync Impact Report legitimately QUOTES the old wording — that is what a change record is for,
and the amendment is unreadable without it. A checker matching the whole file would fail on
the very passage explaining the change. The report is excluded by structure, and a positive
control below proves the exclusion did not swallow the body.

**"CLI" is not a banned string** and must not become one. Vault and Nomad both ship a CLI,
this repository talks about theirs in several places, and a check that forbade the three
letters would force those comments to lie about the tools they describe. What is asserted is
narrower and is the thing that was actually wrong: no document may enumerate a CLI among *this
platform's* northbound transports.
"""

from __future__ import annotations

import pathlib
import re

REPO = pathlib.Path(__file__).resolve().parents[2]
CONSTITUTION = REPO / ".specify" / "memory" / "constitution.md"
GLOSSARY = REPO / "docs" / "glossary.md"
SURFACES = REPO / "src" / "surfaces"


#: The shape that says THIS PLATFORM has a CLI: a CLI named alongside the other transports.
#: Not the word on its own — Vault and Nomad ship CLIs and this repository discusses theirs.
_ENUMERATION = re.compile(r"MCP[^.\n]{0,40}\bCLI\b|\bCLI\b[^.\n]{0,40}portal", re.I)


def _enumerates_a_cli(line: str) -> bool:
    """Whether a line ASSERTS a CLI transport, as opposed to quoting the withdrawn wording.

    Quoted spans are stripped first. Every document propagating ADR-0060 has to reproduce
    the clause it withdrew — an amendment whose before-state cannot be read is not a record —
    and quotation marks distinguish citation from claim structurally. A keyword exemption
    list would not: "withdrawn" anywhere on a line would also excuse one that genuinely
    re-enumerated it.
    """
    return bool(_ENUMERATION.search(re.sub(r'"[^"]*"|\u201c[^\u201d]*\u201d', "", line)))


def _constitution_body() -> str:
    """The constitution without its change record, which quotes what it replaced."""
    return re.sub(r"<!--.*?-->", "", CONSTITUTION.read_text(), flags=re.DOTALL)


def test_the_check_covers_something() -> None:
    """Without this, an empty or moved file would make every assertion below vacuous.

    The stripper is load-bearing — it removes an HTML comment that is most of the file's
    top — so it gets a positive control rather than trust.
    """
    body = _constitution_body()
    assert len(body) > 2000, "the change-record stripper swallowed the constitution's body"
    assert "Northbound:" in body, "the transport clause is not in the stripped body"


def test_the_constitution_enumerates_three_transports() -> None:
    """The clause ADR-0060 amended, asserted in both directions.

    Absence alone would pass if somebody deleted the enumeration entirely, which would be a
    different defect with the same test result — so the replacement is asserted too.
    """
    body = " ".join(_constitution_body().split())
    assert "exactly four transports" not in body
    assert "exactly three transports — MCP, API, portal" in body


def test_no_document_lists_a_cli_among_this_platform_s_transports() -> None:
    """The enumeration, wherever it is restated.

    Matched as a LIST rather than as the word: `MCP, API, CLI, portal` in any order is the
    shape that says this platform has a CLI. Prose about Vault's or Nomad's CLI does not
    match it, which is the point — see the module docstring.
    """
    offenders = []
    for path in [CONSTITUTION, GLOSSARY, REPO / "ROADMAP.md", *SURFACES.rglob("*.py")]:
        text = _constitution_body() if path == CONSTITUTION else path.read_text()
        for line in text.splitlines():
            # QUOTED TEXT IS A CITATION, NOT A CLAIM. Every document that propagates ADR-0060
            # has to reproduce the wording it withdrew — an amendment nobody can read the
            # before-state of is not a record. Stripping quoted spans distinguishes the two
            # structurally, which a keyword exemption list does not: "withdrawn" appearing
            # somewhere on the line would also excuse a line that genuinely re-enumerated it.
            if _enumerates_a_cli(line):
                offenders.append(f"{path.relative_to(REPO)}: {line.strip()[:90]}")
    assert offenders == [], f"a CLI is still enumerated as a transport in: {offenders}"


def test_the_surfaces_package_holds_exactly_the_three() -> None:
    """The tree itself, because prose agreeing with prose proves nothing.

    `dispatch` is not a transport — it is the seam beside them, which is why it is named
    here rather than counted.
    """
    packages = {p.name for p in SURFACES.iterdir() if p.is_dir() and not p.name.startswith("__")}
    assert packages == {"api", "mcp", "portal", "dispatch"}, (
        f"not the three transports plus the dispatch seam: {packages}"
    )


def test_the_detector_can_actually_fail() -> None:
    """A checker that has never rejected anything is indistinguishable from `return []`.

    The repository has shipped prose-stripping checks that passed by removing too much —
    006's boundary checker, 007's run-reference check, 008's read-path isolation test — so
    every one of them now carries a control like this. Both directions are asserted: the
    detector must catch a real re-enumeration and must NOT catch the citation that every
    propagating document contains, or it would force those documents to be unreadable.
    """
    assert _enumerates_a_cli("Northbound: exactly four transports — MCP, API, CLI, portal")
    assert _enumerates_a_cli("the CLI and portal both reach the core")
    assert not _enumerates_a_cli('it asserted "exactly four transports — MCP, API, CLI, portal"')
    assert not _enumerates_a_cli(
        "urllib does NOT read VAULT_CACERT — that is a Vault CLI convention"
    )
