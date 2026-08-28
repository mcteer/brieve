# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — the subject's configuration contract survives all three cards.

Measured on 2026-08-28 over fifty authored artefacts for one subject: with the skills bound
and nothing naming the application's own required configuration, between one and three runs
in ten set every name the subject needs at startup. The delivered guides are thorough about
encryption and they displace — an artefact can apply customer-managed keys throughout and
still be a deployment that cannot boot.

The counterweight is a chain across three cards, and a chain is exactly what a row has to
hold together, because each link is silently useless without the others:

  * Research reads the contract and records it. Nothing else can — Write and Judge never see
    the subject directly.
  * Write is told to satisfy it.
  * Judge checks it *where Research recorded one*.

Delete Research's section and Judge's check is conditioned on a finding that can never be
produced: it passes every artefact, forever, while reading as a gate. That is ADR-0047's
passing stub arriving by deletion at a distance rather than by a stubbed body, which is why
the row is here and not left to a reviewer noticing.

These rows assert the chain is wired, NOT that it works. Whether the wording changes what a
Build authors is an eval question and is recorded as such — see the feature record.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
CARDS = ROOT / "packs" / "terraform" / "agents"


def card(phase: str) -> str:
    """The card with newlines flattened.

    Every phrase these rows look for is prose the cards wrap at 88 columns, so a literal
    substring search finds a sentence only while nobody reflows the paragraph. Normalising
    here keeps the rows about what the card SAYS rather than about where its line breaks
    happen to fall.
    """
    raw = (CARDS / phase / "AGENTS.md").read_text(encoding="utf-8")
    return " ".join(raw.split())


def test_research_records_the_contract() -> None:
    """The only cell that sees the subject is the only cell that can record what it needs."""
    text = card("research")
    assert "## Record the subject's configuration contract" in text, (
        "Research no longer records the subject's configuration contract. Write is instructed "
        "to satisfy it and Judge checks it only where Research recorded one, so removing this "
        "section does not relax one card — it silently disarms the other two."
    )
    assert "no declared configuration contract" in text, (
        "Research must state explicitly when a subject declares no contract. Judge treats "
        "'not recorded' as 'not checked', so silence there is indistinguishable from not "
        "having looked, and the check would be skipped rather than passed."
    )


def test_research_may_read_what_it_must_not_recommend() -> None:
    """The anti-pattern forbids authoring dotenv files; it must not forbid reading one.

    These are one sentence apart and the distinction is the whole contract. A card that bans
    `.env.example` outright leaves Research unable to record the names, which is how the
    chain broke before this feature.
    """
    text = card("research")
    assert ".env.example" in text.split("## Record the subject's configuration contract")[0], (
        "Research's read list no longer reaches `.env.example`. It cannot record a contract "
        "it is not permitted to open."
    )
    assert "not recommending them" in text or "not a recommendation" in text, (
        "Nothing distinguishes reading the subject's dotenv from recommending one. Without "
        "that sentence the anti-pattern reads as a ban on the read the contract depends on."
    )


def test_write_is_told_to_satisfy_the_contract() -> None:
    text = card("write")
    assert "## What the subject requires of you" in text
    assert "then apply the delivered guides' depth" in text, (
        "Write must be told to get the subject running BEFORE applying the guides' depth. "
        "Measured 2026-08-28: stating this as its own section instead of one line made the "
        "card longer and the artefact truncate 5 runs in 10 against the filler control's 1. "
        "A cut-off artefact is worse than a terse complete one, so this stays one line here "
        "and the scoring of it stays in Judge, where it costs Write no output budget."
    )
    assert "Anti-patterns" in text, "the dotenv prohibition must remain in force"
    assert "do not author" in text.lower(), (
        "Write must still be barred from authoring dotenv files. Satisfying the contract "
        "means wiring the names through configuration and secret injection — not writing "
        "the file the anti-pattern forbids."
    )


def test_judge_checks_the_contract_and_refuses_depth_as_a_substitute() -> None:
    text = card("judge")
    assert "every name it recorded reaches the workload" in text
    assert "Where Research recorded no such contract" in text, (
        "Judge must not penalise an artefact for a contract the subject never declared."
    )
    assert "Encryption depth is not a substitute" in text, (
        "The measured failure is an artefact that encrypts everything and cannot start. "
        "Judge scoring depth without scoring bootability rewards exactly that artefact."
    )


def contract_prose(phase: str) -> str:
    """Just the text this feature added to a card, not the whole card.

    The rest of every card is free to discuss `required_version` — the overrides in Plan and
    Judge do exactly that on purpose. What must stay clean is the counterweight itself.
    """
    raw = (CARDS / phase / "AGENTS.md").read_text(encoding="utf-8")
    headings = {
        "research": ["## Record the subject's configuration contract"],
        "write": ["## What the subject requires of you"],
        "judge": None,
    }[phase]
    if headings is None:
        return " ".join(
            line
            for line in raw.splitlines()
            if "reaches the workload" in line
            or "Encryption depth" in line
            or "recorded no such contract" in line
            or "customer-managed keys" in line
        )
    out = []
    for h in headings:
        after = raw.split(h, 1)[1]
        out.append(after.split("\n## ", 1)[0])
    return " ".join(out)


@pytest.mark.parametrize("phase", ["research", "write", "judge"])
def test_the_chain_does_not_restate_the_delivered_guide(phase: str) -> None:
    """053's rule still governs: this counterweight is not a licence to re-add HCL craft.

    The guide teaches style, naming, versions and encryption. This chain teaches none of
    them — it names the job the artefact has to do. If a link starts explaining how to write
    HCL, it has stopped counterweighting the skills and started competing with them.
    """
    prose = contract_prose(phase)
    assert prose.strip(), f"no contract prose found in the {phase} card"
    for term in ("required_version", "terraform fmt", "snake_case", "default_tags"):
        assert term not in prose, (
            f"the contract chain in the {phase} card restates `{term}`, which the delivered "
            "guide already teaches. 053 moved craft upstream; this section is about the job, "
            "not the HCL."
        )
