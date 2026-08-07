# SPDX-License-Identifier: Apache-2.0
"""The endorsement record and the second corpus, without a fabric or a database (045, T004/T006).

The governance decisions this feature turns on are decidable from a mapping and a dictionary,
so they are asserted here where they can be exercised exhaustively, and again in the
conformance rows where they are exercised through the surfaces.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from core.answering.endorsed.corpus import (
    CUSTOMER_ENDORSED,
    VALIDATED_DESIGN,
    CombinedCorpus,
    EndorsedCorpus,
    build_endorsed_corpus,
    endorsed_path,
    provenance_of,
)
from core.answering.endorsed.records import (
    ADOPTED,
    EndorsedDocument,
    SyncedVersion,
    compute_version_id,
    digest_of_document,
)
from core.authority.endorsed_sources import (
    citable_sources,
    parse_endorsed_sources,
    validate_source_name,
)
from core.authority.errors import ResolutionRefused


def _record(**overrides: object) -> dict[str, object]:
    entry: dict[str, object] = {
        "location": "https://git.example.com/acme/standards",
        "endorsed_by": "dan@acme.example",
        "endorsed_at": "2026-08-07T09:00:00+00:00",
        "adopted_version": "v-one",
    }
    entry.update(overrides)
    return {"acme-standards": entry}


def _document(path: str, anchors: dict[str, str]) -> EndorsedDocument:
    return EndorsedDocument(
        path=path,
        url=f"https://git.example.com{path}",
        digest=digest_of_document(anchors),
        anchors=frozenset(anchors),
        sections=dict(anchors),
    )


def test_an_absent_record_is_no_endorsements_and_not_an_error() -> None:
    """The state every deployment starts in and most stay in.

    Refusing here would make the endorsed corpus a required dependency of answering, which is
    the coupling US6 exists to prevent.
    """
    assert parse_endorsed_sources(None) == {}
    assert parse_endorsed_sources({}) == {}


def test_a_malformed_record_refuses_rather_than_reading_as_empty() -> None:
    """044's `read_matrix` finding generalised, and the reason it matters is directional.

    Empty means "nothing is endorsed". An unreadable record presenting as empty would make
    answers quietly stop citing material an administrator believes is trusted — the platform
    looking like it lost the documents rather than looking like it is broken.
    """
    with pytest.raises(ResolutionRefused):
        parse_endorsed_sources({"acme": "https://not-a-mapping"})

    with pytest.raises(ResolutionRefused):
        parse_endorsed_sources(_record(endorsed_by=""))


def test_a_source_with_no_endorser_is_refused() -> None:
    """FR-002. The endorsement IS the trust statement the citation gate rests on.

    A source whose endorser is unknown is content that arrived. The gate's whole reason for
    existing is that content the platform did not vendor needs somebody answerable for it.
    """
    with pytest.raises(ResolutionRefused) as raised:
        parse_endorsed_sources(_record(endorsed_by="   "))

    assert "trust statement" in str(raised.value)


def test_a_credential_shaped_field_is_not_a_field_of_an_endorsement() -> None:
    """044's FR-018b posture, unchanged: the vocabulary has nowhere to put a secret.

    A closed set rather than a filter over a credential-shaped one — a filter is what a future
    field slips past.
    """
    with pytest.raises(ResolutionRefused) as raised:
        parse_endorsed_sources(_record(token="ghp_notasecret"))

    assert "not fields of an endorsed source" in str(raised.value)


@pytest.mark.parametrize(
    "name",
    ["../escape", "two words", "a/b", "back\\slash", ".hidden", ""],
)
def test_a_name_that_could_escape_its_namespace_is_refused(name: str) -> None:
    """The name is a path segment and the namespace is what keeps the two corpora disjoint.

    A separator in a name would let one source's documents resolve inside another's — the
    collision `/endorsed/` exists to make structurally impossible.
    """
    with pytest.raises(ResolutionRefused):
        validate_source_name(name)


def test_withdrawal_beats_adoption() -> None:
    """FR-004. A withdrawn source cites nothing regardless of what it has adopted.

    The adopted version stays recorded because runs in flight pinned it and their records must
    keep naming something real (research R4).
    """
    sources = parse_endorsed_sources(_record(withdrawn=True))
    assert sources["acme-standards"].adopted_version == "v-one"
    assert not sources["acme-standards"].citable
    assert citable_sources(_record(withdrawn=True)) == {}


def test_withdrawn_survives_arriving_as_a_string() -> None:
    """007's `wrap_info` lesson in its general form.

    The record round-trips through the fabric's JSON. A `withdrawn` that arrives as the string
    "true" and reads as not-withdrawn would mean a withdrawal that silently did nothing —
    which is the failure mode with the worst consequence in this module.
    """
    assert not citable_sources(_record(withdrawn="true"))
    assert not citable_sources(_record(withdrawn="True"))
    assert citable_sources(_record(withdrawn="false"))


def test_an_endorsed_source_with_nothing_synced_is_citable_in_principle_and_cites_nothing() -> None:
    """A legitimate state, representable rather than an error.

    Between endorsement and the first sync there is nothing to cite, and treating that as
    malformed would make the console reject its own first step.
    """
    sources = parse_endorsed_sources(_record(adopted_version=""))
    assert not sources["acme-standards"].citable


def test_the_version_identity_is_over_content_not_over_the_upstream_tip() -> None:
    """Two syncs that find the same content produce the same identity, and that is the pin.

    The tip is deliberately not an input: a repository can be force-pushed, and a tip naming
    different content than it did yesterday would silently change what a pinned version means.
    """
    documents = {"/endorsed/acme/policy.md": _document("/endorsed/acme/policy.md", {"scope": "x"})}
    first = compute_version_id("acme", documents)
    assert first == compute_version_id("acme", dict(documents))

    changed = {"/endorsed/acme/policy.md": _document("/endorsed/acme/policy.md", {"scope": "y"})}
    assert compute_version_id("acme", changed) != first


def test_resolution_tries_the_pin_then_the_endorsed_set() -> None:
    """The combined view, and the property that makes it safe: the two are disjoint."""

    class _Pinned:
        digest = "corpus-digest"
        documents: dict[str, object] = {}

        def resolves(self, path: str, anchor: str) -> bool:
            return path == "/vault/policies" and anchor == "acl"

        def url_for(self, path: str, anchor: str) -> str:
            return f"https://developer.hashicorp.com{path}#{anchor}"

    endorsed = EndorsedCorpus(
        digest="v-one",
        documents={"/endorsed/acme/policy.md": _document("/endorsed/acme/policy.md", {"s": "t"})},
    )
    combined = CombinedCorpus(pinned=_Pinned(), endorsed=endorsed)

    assert combined.resolves("/vault/policies", "acl")
    assert combined.resolves("/endorsed/acme/policy.md", "s")
    assert not combined.resolves("/endorsed/acme/policy.md", "absent")
    assert not combined.resolves("/endorsed/other/policy.md", "s")


def test_the_combined_digest_is_the_pinned_one_and_the_endorsed_version_is_beside_it() -> None:
    """Research R1's rejected alternative, asserted as a property rather than a comment.

    One digest covering content with two trust stories would make the supply-chain scan either
    cover customer content — wrong — or exempt part of its own manifest — worse.
    """

    class _Pinned:
        digest = "corpus-digest"
        documents: dict[str, object] = {}

        def resolves(self, path: str, anchor: str) -> bool:
            return False

        def url_for(self, path: str, anchor: str) -> str:
            return ""

    combined = CombinedCorpus(pinned=_Pinned(), endorsed=EndorsedCorpus(digest="v-one"))
    assert combined.digest == "corpus-digest"
    assert combined.endorsed_version == "v-one"


def test_provenance_is_one_function_and_falls_out_of_the_namespace() -> None:
    """Clarify Q2. Data, with exactly one reader, so the convention cannot decay."""
    assert provenance_of("/endorsed/acme/policy.md") == CUSTOMER_ENDORSED
    assert provenance_of("/vault/docs/policies") == VALIDATED_DESIGN
    assert endorsed_path("acme", "policy.md") == "/endorsed/acme/policy.md"
    assert provenance_of(endorsed_path("acme", "/policy.md")) == CUSTOMER_ENDORSED


def test_several_sources_compose_into_one_identity_and_the_oldest_sync_time() -> None:
    """FR-017h with more than one source endorsed, and the age disclosure's direction.

    The OLDEST sync, because the disclosure must describe the staleness a reader could actually
    be affected by; reporting the freshest would let one recent source vouch for material
    synced months ago.
    """
    old = datetime(2026, 1, 1, tzinfo=UTC)
    new = datetime(2026, 8, 1, tzinfo=UTC)
    versions = [
        SyncedVersion(
            version_id="v-a",
            tenant_id="acme",
            source="standards",
            upstream_tip="abc",
            synced_at=new,
            synced_by="dan",
            state=ADOPTED,
            documents={
                "/endorsed/standards/a.md": _document("/endorsed/standards/a.md", {"x": "1"})
            },
        ),
        SyncedVersion(
            version_id="v-b",
            tenant_id="acme",
            source="policies",
            upstream_tip="def",
            synced_at=old,
            synced_by="dan",
            state=ADOPTED,
            documents={"/endorsed/policies/b.md": _document("/endorsed/policies/b.md", {"y": "2"})},
        ),
    ]

    corpus = build_endorsed_corpus(versions)
    assert corpus.synced_at == old
    assert corpus.sources == frozenset({"standards", "policies"})
    assert corpus.resolves("/endorsed/standards/a.md", "x")
    assert corpus.resolves("/endorsed/policies/b.md", "y")
    assert corpus.digest not in {"v-a", "v-b"}
    # Order of endorsement must not change the identity a record names.
    assert build_endorsed_corpus(list(reversed(versions))).digest == corpus.digest


def test_no_endorsed_versions_is_an_empty_corpus_that_resolves_nothing() -> None:
    corpus = build_endorsed_corpus([])
    assert corpus.empty
    assert corpus.digest == ""
    assert not corpus.resolves("/endorsed/anything/at.md", "all")
