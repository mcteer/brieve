# SPDX-License-Identifier: Apache-2.0
"""The client's writing half (042, T001).

**These cover the platform's FIRST writes to Vault through the workload identity.**
`surfaces.handlers.vault_write` has always been a stub — it validates arguments and returns
`written: True` without touching the product — and `agent_pack_secrets` carries no write
capability at all, with its own comment recording why. So none of this is a well-worn path
being reused, and these rows are what stand in for the wear.

The error contract is `read_path`'s, deliberately: absence is data, a refusal names what
Vault said, and a timeout stays distinguishable from an outage. A writing method that
collapsed them would send whoever investigates to the wrong system, which is the reasoning
`read_path`'s docstring already carries.
"""

from __future__ import annotations

import json
import urllib.error
from typing import Any

import pytest

from core.durability.credentials import VaultDatabaseCredentials, VaultReadFailed


class _Identity:
    def jwt(self) -> str:
        return "attested-identity-jwt"


class _Response:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_: object) -> None:
        return None


def _client(monkeypatch: pytest.MonkeyPatch, responses: list[Any]) -> tuple[Any, list[Any]]:
    """A client whose transport is scripted. Records every request it was asked to make."""
    seen: list[Any] = []
    queue = list(responses)

    def _urlopen(request: Any, **_: Any) -> Any:
        seen.append(request)
        nxt = queue.pop(0) if queue else _Response(b"")
        if isinstance(nxt, Exception):
            raise nxt
        return nxt

    monkeypatch.setattr("urllib.request.urlopen", _urlopen)
    client = VaultDatabaseCredentials(identity=_Identity(), vault_addr="https://vault.test")
    return client, seen


_LOGIN = _Response(json.dumps({"auth": {"client_token": "run-token"}}).encode())


def test_a_policy_write_sends_a_post_and_survives_an_empty_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """204 No Content is Vault's ordinary answer to a policy write.

    Parsing it as JSON raises, and treating that as failure would report every successful
    write as broken — while the caller's `finally` then tried to clean up after a write it
    believes did not happen.
    """
    client, seen = _client(monkeypatch, [_LOGIN, _Response(b"")])

    client.write_path("sys/policies/acl/scratch-agent-r1-proposed", {"policy": 'path "x" {}'})

    write = seen[-1]
    assert write.method == "POST"
    assert write.full_url.endswith("/v1/sys/policies/acl/scratch-agent-r1-proposed")
    assert json.loads(write.data)["policy"] == 'path "x" {}'


def test_a_delete_of_something_already_gone_is_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The row that keeps a `finally` block honest.

    042's impact check destroys its scratch policies on the way out of every path including
    the failing one. A delete that raised on already-absent would either mask the original
    exception or replace it with one about tidying up — and the operator would be sent to
    debug cleanup instead of the fault.
    """
    gone = urllib.error.HTTPError("https://vault.test", 404, "Not Found", {}, None)  # type: ignore[arg-type]
    client, _ = _client(monkeypatch, [_LOGIN, gone])

    client.delete_path("sys/policies/acl/scratch-agent-r1-proposed")  # must not raise


def test_a_refused_write_names_what_vault_said(monkeypatch: pytest.MonkeyPatch) -> None:
    """`read_path`'s contract, applied to writes: the body carries the reason."""

    class _Refused(urllib.error.HTTPError):
        def __init__(self) -> None:
            super().__init__("https://vault.test", 403, "Forbidden", {}, None)  # type: ignore[arg-type]

        def read(self) -> bytes:  # type: ignore[override]
            return b'{"errors":["1 error occurred: * permission denied"]}'

    client, _ = _client(monkeypatch, [_LOGIN, _Refused()])

    with pytest.raises(VaultReadFailed) as raised:
        client.write_path("sys/policies/acl/agent-ceiling", {"policy": "x"})

    assert raised.value.status == 403
    assert "permission denied" in str(raised.value), (
        "a refusal that does not carry Vault's own reason sends a reader to the wrong "
        "component — the same argument `fetch` already makes for its 403s"
    )


def test_a_slow_fabric_stays_distinguishable_from_an_absent_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Timeouts arrive wrapped in OSError from urllib, which is how the flag gets lost."""
    slow = OSError()
    slow.reason = TimeoutError()  # type: ignore[attr-defined]
    client, _ = _client(monkeypatch, [_LOGIN, slow])

    with pytest.raises(VaultReadFailed) as raised:
        client.write_path("sys/policies/acl/scratch-agent-r1-current", {"policy": "x"})

    assert raised.value.timed_out


def test_a_minted_token_goes_through_a_role_and_carries_no_default_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both halves are load-bearing, and for different reasons.

    The ROLE is what bounds the grant to `scratch-agent-*` at the product — a bare
    `auth/token/create` can only grant policies the parent holds, which would mean attaching
    the scratch policy to the run's own token: a run holding authority over what bounds it.

    `no_default_policy` is what makes "a token carrying only the proposed policy" true. With
    `default` attached the capability answers would describe the union, and would be wrong in
    the permissive direction — which is the direction that matters for a safety instrument.
    """
    minted = _Response(json.dumps({"auth": {"client_token": "scratch-token"}}).encode())
    client, seen = _client(monkeypatch, [_LOGIN, minted])

    token = client.create_token(role="scratch-check", policies=["scratch-agent-r1-proposed"])

    assert token == "scratch-token"
    request = seen[-1]
    assert request.full_url.endswith("/v1/auth/token/create/scratch-check")
    body = json.loads(request.data)
    assert body["no_default_policy"] is True
    assert body["policies"] == ["scratch-agent-r1-proposed"]
    assert body["ttl"] == "60s"


def test_a_mint_that_returns_no_token_refuses(monkeypatch: pytest.MonkeyPatch) -> None:
    """A check that cannot obtain its subject has not run, and must not read as one that did."""
    empty = _Response(json.dumps({"auth": {}}).encode())
    client, _ = _client(monkeypatch, [_LOGIN, empty])

    with pytest.raises(VaultReadFailed):
        client.create_token(role="scratch-check", policies=["scratch-agent-r1-proposed"])


def test_capabilities_asks_as_the_platform_with_the_subject_in_the_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`sys/capabilities`, not `capabilities-self` — and the reason is `no_default_policy`.

    `capabilities-self` lives in the `default` policy, which the scratch token deliberately
    does not carry. Restoring `default` to let the subject ask on its own behalf would mean
    the token no longer carries only the policy under measurement.
    """
    answer = _Response(json.dumps({"data": {"secret/data/app": ["read", "list"]}}).encode())
    client, seen = _client(monkeypatch, [_LOGIN, answer])

    result = client.capabilities(subject_token="scratch-token", paths=["secret/data/app"])

    assert result == {"secret/data/app": ["list", "read"]}
    request = seen[-1]
    assert request.full_url.endswith("/v1/sys/capabilities")
    assert json.loads(request.data)["token"] == "scratch-token"


def test_a_path_vault_did_not_answer_is_absent_not_denied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The distinction that decides whether a widening reads as a widening.

    Vault says `["deny"]` when it means deny. A path missing from its answer was not
    answered — and filling it with `[]` would make unanswered and denied identical. On the
    *proposed* side of an impact check that reports a widening as a narrowing, which is the
    one direction a safety instrument must never be wrong in.
    """
    partial = _Response(json.dumps({"data": {"secret/data/app": ["read"]}}).encode())
    client, _ = _client(monkeypatch, [_LOGIN, partial])

    result = client.capabilities(
        subject_token="scratch-token", paths=["secret/data/app", "secret/data/other"]
    )

    assert "secret/data/other" not in result, "unanswered is absent from the result, not empty"
    assert result["secret/data/app"] == ["read"]


def test_no_token_value_appears_in_any_refusal_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """[GATE:no-secret-leak] — a refusal carries the path and the role, never the credential.

    Every message these methods raise reaches a run record eventually, and ADR-0051's
    residual risk is that anything reaching a record is permanent. The login token and the
    minted scratch token are both credentials; neither belongs in an exception.
    """

    class _Refused(urllib.error.HTTPError):
        def __init__(self) -> None:
            super().__init__("https://vault.test", 403, "Forbidden", {}, None)  # type: ignore[arg-type]

        def read(self) -> bytes:  # type: ignore[override]
            return b'{"errors":["permission denied"]}'

    secret_login = _Response(json.dumps({"auth": {"client_token": "SUPER-SECRET-RUN"}}).encode())
    client, _ = _client(monkeypatch, [secret_login, _Refused()])

    with pytest.raises(VaultReadFailed) as raised:
        client.write_path("sys/policies/acl/scratch-agent-r1-proposed", {"policy": "x"})

    assert "SUPER-SECRET-RUN" not in str(raised.value)
    assert "SUPER-SECRET-RUN" not in repr(raised.value)
