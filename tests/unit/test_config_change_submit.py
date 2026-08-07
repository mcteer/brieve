# SPDX-License-Identifier: Apache-2.0
"""C3 and the ConfigChange shape — the submitter generalised, not reimplemented (044, T003).

**C3 is 007's lesson driven directly.** `wrap_info` is present as `null` on **every** Vault
response, so `"wrap_info" in body` is true for all inputs and proves nothing. Three tests once
passed regardless of behaviour on exactly that, and the mistake is invisible because the
passing case looks identical. This file drives the present-as-null shape on purpose.

**Why `submit_change` returns where `submit` raises.** 007's method raises on pending because
its caller maps each outcome to an HTTP status, and the asymmetry protects it: a caller
treating "returned normally" as success cannot mistake a queued request for an applied one.
The console needs all three as data — it renders them as three different things on one page —
so this returns an outcome and the route decides. Same mapping, different consumer.
"""

from __future__ import annotations

import json
import urllib.error
from typing import Any

import pytest

from surfaces.api.authority_submit import (
    CONSOLE_RECORDS,
    AuthorityChangeRefused,
    AuthoritySubmitUnavailable,
    ChangeOutcome,
    ConfigChange,
    RecordMoved,
    VaultAuthoritySubmitter,
)

MOUNT_PATH = "harness-authority/data/claim-mappings"


class _Response:
    def __init__(self, body: dict[str, Any], status: int = 200) -> None:
        self._body = json.dumps(body).encode()
        self.status = status

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_: object) -> None:
        return None


def _submitter(
    monkeypatch: pytest.MonkeyPatch, response: Any
) -> tuple[VaultAuthoritySubmitter, list[Any]]:
    seen: list[Any] = []

    def _urlopen(request: Any, **_: Any) -> Any:
        seen.append(request)
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr("urllib.request.urlopen", _urlopen)
    return VaultAuthoritySubmitter(
        vault_addr="https://vault.test", controlled_path=MOUNT_PATH
    ), seen


def _change(**over: Any) -> ConfigChange:
    base = {
        "record": "ask-bindings",
        "payload": {"schema_version": 1, "relevance_enabled": False},
        "requester": "alice",
    }
    return ConfigChange(**{**base, **over})


def test_row_c3_wrap_info_present_as_null_is_applied_not_pending(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C3 — the row 007 paid for.

    Vault returns `wrap_info: null` on every ungated write. A membership check would read
    every applied change as pending, and the console would tell an administrator their change
    is awaiting an approval that will never come.
    """
    submitter, _ = _submitter(monkeypatch, _Response({"wrap_info": None, "data": {}}))

    outcome = submitter.submit_change(_change())

    assert outcome == ChangeOutcome(state="applied")
    assert not outcome.is_pending


def test_row_c3_a_truthy_wrap_info_is_pending_and_carries_its_accessor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The other half: a queued change is data the console renders, not an exception."""
    submitter, _ = _submitter(
        monkeypatch, _Response({"wrap_info": {"accessor": "acc-42", "creation_time": "2026-08-07"}})
    )

    outcome = submitter.submit_change(_change())

    assert outcome.is_pending
    assert outcome.accessor == "acc-42", "an approver acts on the accessor; without it, on what?"


def test_a_refused_change_raises_rather_than_returning_an_outcome(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Refusal is not a third state beside applied and pending.

    Rendering it as an outcome would invite a caller to `if outcome.state == "applied"` and
    treat everything else as "not yet" — which is how a denial comes to read as a delay.
    """
    error = __import__("urllib.error", fromlist=["HTTPError"]).HTTPError(
        "https://vault.test", 403, "Forbidden", {}, None
    )
    submitter, _ = _submitter(monkeypatch, error)

    with pytest.raises(AuthorityChangeRefused):
        submitter.submit_change(_change())


def test_a_stale_cas_is_record_moved_not_a_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two administrators editing one record is neither a denial nor an outage (US5).

    **The status and the body are the ones the real Vault returns**, captured from the enclave
    rather than assumed. The first version of this row scripted a 409 — a conflict is a
    conflict — and passed, while the code checking for 409 would never have fired against the
    product: KV v2 answers a failed check-and-set with **400** and
    `"check-and-set parameter did not match the current version"`. A test that agrees with its
    author instead of with the product is the shape CL1 exists to catch.
    """

    class _CasMismatch(urllib.error.HTTPError):
        def __init__(self) -> None:
            super().__init__("https://vault.test", 400, "Bad Request", {}, None)  # type: ignore[arg-type]

        def read(self) -> bytes:  # type: ignore[override]
            return b'{"errors":["check-and-set parameter did not match the current version"]}'

    submitter, _ = _submitter(monkeypatch, _CasMismatch())

    with pytest.raises(RecordMoved) as raised:
        submitter.submit_change(_change(cas=3))

    assert raised.value.reason_code == "record_moved"


def test_an_ordinary_400_is_not_read_as_a_concurrent_edit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The discriminator is the message, and this is the direction it must fail in.

    A malformed request reported as "somebody else got there first" sends an administrator to
    look for a colleague who does not exist. An unrecognised message falls through to
    `AuthoritySubmitUnavailable` — loud, and they retry — rather than the reverse, which is
    quiet and ends in an overwrite.
    """

    class _Malformed(urllib.error.HTTPError):
        def __init__(self) -> None:
            super().__init__("https://vault.test", 400, "Bad Request", {}, None)  # type: ignore[arg-type]

        def read(self) -> bytes:  # type: ignore[override]
            return b'{"errors":["missing data"]}'

    submitter, _ = _submitter(monkeypatch, _Malformed())

    with pytest.raises(AuthoritySubmitUnavailable):
        submitter.submit_change(_change(cas=3))


def test_the_cas_guard_goes_in_options_not_in_the_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """KV v2 puts the guard in `options`. In `data` it is stored and guards nothing.

    A check-and-set that silently is not one is worse than none: the caller believes
    concurrent writes are handled, and the losing write leaves no trace.
    """
    submitter, seen = _submitter(monkeypatch, _Response({"wrap_info": None}))

    submitter.submit_change(_change(cas=7))

    body = json.loads(seen[-1].data)
    assert body["options"] == {"cas": 7}
    assert "cas" not in body["data"]


def test_the_requester_is_carried_into_the_record_as_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FR-019: 'last set by' is readable from the record, not from a second store.

    A separate provenance store is a second source of truth for the same fact, and the two
    would disagree exactly when somebody needed to know which writer was last.
    """
    submitter, seen = _submitter(monkeypatch, _Response({"wrap_info": None}))

    submitter.submit_change(_change())

    assert json.loads(seen[-1].data)["data"]["set_by"] == "console/alice"


def test_a_record_outside_the_closed_set_refuses_before_a_socket_opens() -> None:
    """The escalation this feature prevents at every other layer, prevented here too.

    An open-ended record argument would let a caller aim the submitter at `harness-ceilings`
    — what bounds every agent — and the grant, the Control Group and the route check would
    all be irrelevant because the request would never reach them.
    """
    with pytest.raises(AuthorityChangeRefused) as raised:
        _change(record="harness-ceilings").path_within("harness-authority")

    assert "not a record the console may change" in str(raised.value)


def test_a_claim_mapping_change_names_its_own_mapping() -> None:
    """007's finding: one path for every mapping meant one grant revoked another."""
    with pytest.raises(AuthorityChangeRefused):
        _change(record="claim-mappings").path_within("harness-authority")

    path = _change(record="claim-mappings", key="groups.platform").path_within("harness-authority")
    assert path == "harness-authority/data/claim-mappings/groups.platform"


def test_the_writable_set_is_exactly_what_the_grant_covers() -> None:
    """The code's closed set and the trust fabric's grant are two statements of one fact.

    `test_console_controlled_paths.py` asserts the grant against the Control Group's list;
    this asserts the code against the same records, so a widening needs several edits in
    several files rather than one that slips.

    045 added the fourth, `endorsed-sources`. That it had to be added *here* — as a
    deliberate edit to a literal, not as a set that grew on its own — is the row working.
    """
    assert CONSOLE_RECORDS == {
        "ask-bindings",
        "product-connections",
        "claim-mappings",
        "endorsed-sources",
    }
