# SPDX-License-Identifier: Apache-2.0
"""How a deployed estate answer names the records it cites — the branch 027 introduced.

**The eval lane and a deployment identify records differently, and only one of them had a test.**
Eval fixtures author friendly ids (`rec-vault-002`) and pass a mapping, so the provider offers
those ids to the model and translates citations back to entry hashes. A deployment has no authored
ids: the records are the tenant's own, and nobody named them.

`served.py` is the first assembly to construct one of these, and constructing it the eval lane's
way — with an empty mapping — offered every record as ``id: ?`` and resolved every citation to
``unresolvable:?``. The provider would answer, the path would drop every claim for an unresolvable
reference, and the caller would be told *the records do not support an answer*. A wrong answer
would have been recoverable; that one is indistinguishable from an honest decline.

So `ids_to_hashes=None` means **the entry hash is the id**, and these rows cover it, because the
live lane exercises only the mapped shape and no other row constructs this class at all.
"""

from __future__ import annotations

from typing import Any

from adapters.anthropic_answering import LiveEstateProvider

HASH_A = "a" * 64
HASH_B = "b" * 64


class _Record:
    def __init__(self, entry_hash: str) -> None:
        self.entry_hash = entry_hash
        self.event_type = "authority_denied"
        self.correlation_id = "run-1"
        self.payload: dict[str, Any] = {"tool": "vault_write"}


def test_the_deployed_shape_offers_entry_hashes_and_resolves_them_back() -> None:
    """`None` is not "an empty mapping"; it is a different identity scheme, round-tripping."""
    provider = LiveEstateProvider()

    assert provider._id_for(HASH_A) == HASH_A  # noqa: SLF001 — the branch is the claim
    assert provider._hash_for(HASH_A) == HASH_A  # noqa: SLF001


def test_the_fixture_shape_still_translates_both_ways() -> None:
    """The eval lane's behaviour, unchanged — asserted so the new branch cannot cost it."""
    provider = LiveEstateProvider(ids_to_hashes={"rec-vault-002": HASH_B})

    assert provider._id_for(HASH_B) == "rec-vault-002"  # noqa: SLF001
    assert provider._hash_for("rec-vault-002") == HASH_B  # noqa: SLF001


def test_a_mapped_provider_still_marks_an_invented_id_unresolvable() -> None:
    """Precision failing, exactly as it should — a model citing a record nobody has.

    Kept distinct from the deployed shape on purpose: with a mapping, an unknown id is an
    invention and must not resolve. Without one, every id IS a hash and there is nothing to
    invent against — which is why the two schemes cannot share one branch.
    """
    provider = LiveEstateProvider(ids_to_hashes={"rec-vault-002": HASH_B})

    assert provider._hash_for("rec-invented-999") == "unresolvable:rec-invented-999"  # noqa: SLF001


def test_an_empty_mapping_is_not_silently_treated_as_the_deployed_shape() -> None:
    """The distinction that caused the defect, pinned so it cannot be collapsed back.

    `{}` and `None` mean different things: an empty mapping is a fixture that authored no ids —
    a fixture problem, and every citation should fail to resolve so somebody notices. `None` is a
    deployment, where hashes are the ids. A reader tempted to simplify this with
    `ids_to_hashes or {}` would reintroduce exactly the state `served.py` shipped with.
    """
    empty = LiveEstateProvider(ids_to_hashes={})

    assert empty._id_for(HASH_A) == "?"  # noqa: SLF001
    assert empty._hash_for(HASH_A) == f"unresolvable:{HASH_A}"  # noqa: SLF001


def test_no_records_declines_without_calling_a_vendor() -> None:
    """The guard that keeps a deployed estate ask from spending a call on nothing.

    Constructed with no credential and no client: reaching a vendor here would raise, so the row
    passing is itself the assertion that nothing was reached.
    """
    assert LiveEstateProvider().answer("Which runs were denied?", ()) == []
