# SPDX-License-Identifier: Apache-2.0
"""GATE:fail-closed — the platform's first brokered credential, and what it refuses.

**027 does not reuse a broker; it builds the first one.** Research F1 measured that:
`core.authority.entitlements.BrokeredMaterialSource` is a Protocol whose docstring says the
credential-translation mechanism "is its own feature", and nothing implements it. Principle IV's
one named exception describes how a credential *would* be governed — no code holds, rotates, or
delivers one. So the shape built here becomes the precedent the TFE path later inherits, which is
why the refusals below are written as carefully as the happy path.

**A vendor key is not derivable** (research F2). Vault mints lesser material for products with
credential APIs — database roles, PKI. A model vendor has no such API: there is nothing to derive
*from*. So the posture cannot be "short-lived derived material"; it is **never persisted** —
fetched per task, held in process, gone with it. Anyone reaching for response-wrapping ceremony
should read this paragraph first: it buys a second hop and changes nothing about what the workload
ends up holding.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import Any

import pytest

from core.authority.entitlements import BrokeredMaterialSource
from core.authority.errors import ResolutionRefused
from core.authority.model_credential import BrokeredModelCredential

SRC = Path(__file__).resolve().parents[2] / "src"

VENDOR = "anthropic"
KEY = "sk-ant-not-a-real-key-0000000000"


def _store(*, key: str = KEY, version: int = 3) -> dict[str, Any]:
    """What a KV v2 `data/` read returns: the secret under `data`, the version under `metadata`."""
    return {"data": {"api_key": key}, "metadata": {"version": version}}


def _reader(record: dict[str, Any] | None, *, raises: Exception | None = None) -> Any:
    calls: list[int] = []

    def read(path: str) -> dict[str, Any] | None:
        calls.append(1)
        if raises is not None:
            raise raises
        return record

    read.calls = calls  # type: ignore[attr-defined]
    return read


# ------------------------------------------------------------------ T001/T002: the premises


def test_the_brokered_material_protocol_still_has_no_production_implementation() -> None:
    """Research F1, kept executable: 027 is the FIRST broker, not a second user of one.

    `BrokeredMaterialSource` is a Protocol and `entitlements.py` says the mechanism it exists for
    is a separate feature. Every reference to it under `src/` is an *annotation* — a parameter or
    field typed as "a source, if one is ever supplied" — and no class declares it as a base. So
    the shape 027 builds is the first working one, and becomes the precedent the TFE path inherits.

    Written by parsing rather than by `issubclass`, because the Protocol is not
    `@runtime_checkable` and a structural check would answer a different question: whether some
    class happens to match the shape, not whether anything *claims* the contract.

    When a real broker lands, this row goes from "nothing implements it" to naming what does, and
    whoever changes it will find the reason it was written.
    """
    implementors = []
    for path in SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and any(
                isinstance(base, ast.Name) and base.id == "BrokeredMaterialSource"
                for base in node.bases
            ):
                implementors.append(f"{path.relative_to(SRC)}::{node.name}")

    assert implementors == [], (
        f"a broker now exists ({implementors}) — research F1's premise has changed. Rewrite this "
        f"row to say what implements it, and check whether 027's shape is still the precedent."
    )


def test_the_model_credential_deliberately_does_not_claim_the_broker_protocol() -> None:
    """Two brokerings, two contracts, and flattening them would lose the difference.

    `BrokeredMaterialSource` delivers **derived** material for a product with a credential API.
    `BrokeredModelCredential` delivers the **shared-grain** credential itself, because a model
    vendor has no such API (research F2). One protocol over both would name them the same thing
    and hide exactly the property that makes the second one need governance instead of scope.
    """
    assert inspect.isclass(BrokeredMaterialSource)
    assert BrokeredMaterialSource not in BrokeredModelCredential.__mro__


def test_the_credential_is_delivered_not_derived() -> None:
    """Research F2, as a property rather than a comment.

    `obtain` returns exactly what the store holds. There is no minting step, no lesser scope, no
    second credential — because a vendor API key has no credential API to derive one from. The
    posture that makes this safe is **never persisted**, which the rows below assert, not
    **derived**, which is unavailable at any price.
    """
    reader = _reader(_store())
    credential = BrokeredModelCredential(read=reader)
    assert credential.obtain(VENDOR).secret == KEY


# ------------------------------------------------------------------ T005: the reader


def test_a_present_record_fetches_and_the_reference_carries_the_version() -> None:
    credential = BrokeredModelCredential(read=_reader(_store(version=7)))
    obtained = credential.obtain(VENDOR)
    assert obtained.secret == KEY
    assert obtained.reference == f"vault:model-credentials/{VENDOR}@v7"


def test_the_secret_and_its_reference_come_from_one_read_and_cannot_disagree() -> None:
    """The correction to the planned two-method shape, pinned so it is not undone.

    `fetch()` and `credential_reference()` as separate calls would be separate reads, and a
    rotation landing between them would have the trail record a generation the call did not use.
    On a record whose whole value is *which rotation generation authorised this*, that is the one
    inaccuracy worth designing away — so one read yields both, and rotating between two `obtain`
    calls moves the secret and the reference **together**.
    """
    record = _store(key="first", version=1)
    reader = _reader(record)
    credential = BrokeredModelCredential(read=reader)

    before = credential.obtain(VENDOR)
    assert (before.secret, before.reference) == ("first", f"vault:model-credentials/{VENDOR}@v1")

    record["data"]["api_key"] = "second"
    record["metadata"]["version"] = 2
    after = credential.obtain(VENDOR)
    assert (after.secret, after.reference) == ("second", f"vault:model-credentials/{VENDOR}@v2")


def test_the_reference_never_contains_the_key() -> None:
    """FR-008 at the seam that produces the trail's value.

    A reference is a location and a rotation generation. Not the key, and not a hash of it — a
    hash of a low-entropy-format secret is an oracle, and the platform's rule everywhere else is
    references only.
    """
    credential = BrokeredModelCredential(read=_reader(_store()))
    assert KEY not in credential.obtain(VENDOR).reference


def test_an_absent_record_refuses_credential_unavailable() -> None:
    credential = BrokeredModelCredential(read=_reader(None))
    with pytest.raises(ResolutionRefused) as refused:
        credential.obtain(VENDOR)
    assert refused.value.reason_code == "credential_unavailable"


def test_a_record_without_the_key_field_refuses_rather_than_returning_empty() -> None:
    """An empty string would sail into a provider and fail as a vendor error — the wrong cause."""
    credential = BrokeredModelCredential(read=_reader({"data": {}, "metadata": {"version": 1}}))
    with pytest.raises(ResolutionRefused) as refused:
        credential.obtain(VENDOR)
    assert refused.value.reason_code == "credential_unavailable"


def test_an_unreadable_store_refuses_distinguishably_from_an_absent_record() -> None:
    """SC-004's shape, one layer down: an outage is not a governance state.

    A store that cannot be reached and a credential nobody wrote send an operator to different
    places, so they must not share a reason code.
    """
    credential = BrokeredModelCredential(read=_reader(None, raises=ConnectionError("vault down")))
    with pytest.raises(ResolutionRefused) as refused:
        credential.obtain(VENDOR)
    assert refused.value.reason_code == "fabric_unreachable"


def test_two_fetches_are_two_reads_and_never_share_cached_state() -> None:
    """The whole posture: material's lifetime is the task's.

    Mutating the backing store between calls and observing the change proves there is no instance
    state carrying a key forward. A reader that cached would pass every other row here and hold a
    credential across tasks — which is the standing credential this feature exists to avoid.
    """
    record = _store(key="first", version=1)
    reader = _reader(record)
    credential = BrokeredModelCredential(read=reader)

    assert credential.obtain(VENDOR).secret == "first"
    record["data"]["api_key"] = "second"
    record["metadata"]["version"] = 2
    assert credential.obtain(VENDOR).secret == "second"
    assert len(reader.calls) == 2
