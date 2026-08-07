# SPDX-License-Identifier: Apache-2.0
"""V8, V9, V10 — reading policy structure, and the three states that are not two (042, US1).

**V9 is the row that keeps FR-002 and FR-013 structural.** A protected policy's body never
enters the run at all, so it cannot appear in a proposal — as opposed to being scrubbed at
composition, which depends on every future composition path remembering to scrub. 038's
containment module draws exactly that distinction between a structural claim and an inspected
one, and the structural one is the one that survives a refactor.

**Three states, not two.** `absent` and `protected` collapsed would make a denial read as a
gap — and an agent told "no such policy" about `agent-ceiling` would reasonably propose
creating one, which is the escalation dressed as helpfulness.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from surfaces import handlers

PROTECTED = frozenset({"agent-ceiling", "authoring-publisher"})

BODY = 'path "secret/data/payments/*" {\n  capabilities = ["read"]\n}\n'


class _Fabric:
    """A Vault that answers structure. Records every path it was asked for.

    The `reads` list is what makes V9's claim assertable: "no secret value appears" is weak if
    the tool could have read one and dropped it, and this shows the read never happened.
    """

    def __init__(self, *, policies: dict[str, str], roles: dict[str, list[str]] | None = None):
        self._policies = policies
        self._roles = roles or {}
        self.reads: list[str] = []

    def read_path(self, path: str, **_: Any) -> dict[str, Any] | None:
        self.reads.append(path)
        if path.startswith("sys/policies/acl/"):
            name = path.rsplit("/", 1)[-1]
            if name not in self._policies:
                return None
            return {"data": {"name": name, "policy": self._policies[name]}}
        for role, attached in self._roles.items():
            if path.endswith(f"/{role}"):
                return {"data": {"token_policies": attached}}
        return None

    def list_path(self, path: str, **_: Any) -> list[str] | None:
        if path == "auth/token/roles":
            return sorted(self._roles)
        return None


def _read(
    monkeypatch: pytest.MonkeyPatch,
    fabric: _Fabric,
    name: str,
    protected: frozenset[str] = PROTECTED,
) -> Mapping[str, Any]:
    """Drive the handler with a scripted Vault.

    `monkeypatch` rather than assigning the module attribute, so the restore is pytest's
    rather than a fixture this file has to keep correct — a hand-rolled teardown that misses
    one path leaks a fake fabric into every later row in the process.
    """
    monkeypatch.setattr(handlers, "_fabric", lambda: fabric)
    result: Mapping[str, Any] = handlers.vault_policy_read(
        {"policy_name": name, "_protected": protected}
    )
    return result


def test_row_v8_the_handler_is_the_one_the_manifest_names() -> None:
    """V8's registry half — a manifest may only name something already here.

    `PLATFORM_HANDLERS` is the structural half of "loading executes nothing from a pack":
    there is no field carrying a callable, so no arrangement of pack content reaches this
    module except by naming a function that already exists in it.
    """
    assert handlers.PLATFORM_HANDLERS["vault_policy_read"] is handlers.vault_policy_read


def test_row_v9_a_present_policy_carries_its_document(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without this the three states could all be refusals wearing different names."""
    result = _read(monkeypatch, _Fabric(policies={"payments-app-read": BODY}), "payments-app-read")

    assert result["state"] == "present"
    assert result["document"] == BODY


def test_row_v9_an_absent_policy_is_absent_not_protected(monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-003: a policy that is not there is distinguishable from one you may not see."""
    result = _read(monkeypatch, _Fabric(policies={}), "payments-app-read")

    assert result["state"] == "absent"
    assert result["document"] == ""


def test_row_v9_a_protected_policy_yields_no_body_and_is_never_even_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """V9 — the row that makes FR-013 structural (SC-006).

    The assertion that matters is the second one: the body is empty *because the read never
    happened*, not because it was filtered afterwards. A body that never enters the run cannot
    reach a proposal through any composition path, present or future.
    """
    fabric = _Fabric(policies={"agent-ceiling": 'path "sys/*" { capabilities = ["sudo"] }'})

    result = _read(monkeypatch, fabric, "agent-ceiling")

    assert result["state"] == "protected"
    assert result["document"] == ""
    assert not any(path.startswith("sys/policies/acl/") for path in fabric.reads), (
        "the protected body was READ and then dropped. Filtering after the fact depends on "
        "every future composition path remembering to filter; not reading it does not."
    )
    assert "bounds the agents" in str(result["note"]), (
        "the state names why, so an agent is not left inferring that the policy is missing"
    )


def test_row_v9_no_secret_path_is_ever_touched(monkeypatch: pytest.MonkeyPatch) -> None:
    """[GATE:no-secret-leak] FR-002, asserted over what the tool ASKED for.

    `vault_read`'s boundary — "the value belongs in the process that consumes it, not in the
    reasoning about it" — is inherited here by construction: this tool's whole surface is
    `sys/policies/acl` and attachment metadata, so there is no secret path for it to read.
    """
    fabric = _Fabric(policies={"payments-app-read": BODY}, roles={"agent-run": ["agent-ceiling"]})

    result = _read(monkeypatch, fabric, "payments-app-read")

    assert not any(path.startswith("secret/") for path in fabric.reads)
    assert "secret/" not in str(result.get("document", "")).replace('path "secret/data', "")


def test_row_v9_attachments_are_visible_even_for_a_protected_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Wiring is not content, and this is the line that keeps the tool useful.

    Knowing `agent-ceiling` is attached to the `agent-run` role lets an agent reason about the
    estate. Handing over the body would be handing it its own leash. Refusing both would make
    the estate unreadable in exactly the place understanding it matters most.
    """
    fabric = _Fabric(policies={}, roles={"agent-run": ["agent-ceiling", "harness-database"]})

    result = _read(monkeypatch, fabric, "agent-ceiling")

    assert result["state"] == "protected"
    assert [a["name"] for a in result["attachments"]] == ["agent-run"]
    assert result["attachments"][0]["kind"] == "token_role"


def test_row_v10_attachment_output_truncates_at_the_bound_and_says_so(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """V10 — FR-010, and 029's lesson is on the constant.

    A read bounded by the wrong thing once answered from 1,000 of 63,947 entries and said
    nothing about it. A silent truncation is worse than a small one: it reads as completeness.
    """
    roles = {f"role-{n:03d}": ["payments-app-read"] for n in range(handlers.ATTACHMENT_BUDGET + 10)}
    fabric = _Fabric(policies={"payments-app-read": BODY}, roles=roles)

    result = _read(monkeypatch, fabric, "payments-app-read")

    assert result["truncated"] is True
    assert len(result["attachments"]) == handlers.ATTACHMENT_BUDGET


def test_row_v10_an_untruncated_read_says_that_too(monkeypatch: pytest.MonkeyPatch) -> None:
    """The flag is a fact about the read, not a constant that is always True."""
    fabric = _Fabric(policies={"payments-app-read": BODY}, roles={"agent-run": ["other"]})

    assert _read(monkeypatch, fabric, "payments-app-read")["truncated"] is False


def test_a_missing_attachment_source_does_not_fail_the_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An estate with no identity engine mounted is an ordinary estate.

    Refusing the whole read because one of four optional locations is absent would make the
    tool unusable in exactly the deployments that have the least Vault configured.
    """

    class _Partial(_Fabric):
        def list_path(self, path: str, **_: Any) -> list[str] | None:
            if path.startswith("identity/"):
                raise RuntimeError("identity secrets engine is not mounted")
            return super().list_path(path)

    result = _read(monkeypatch, _Partial(policies={"payments-app-read": BODY}), "payments-app-read")

    assert result["state"] == "present"


def test_a_read_with_no_policy_name_refuses(monkeypatch: pytest.MonkeyPatch) -> None:
    """Required. Inferring which policy was meant is how a tool reads the wrong one."""
    with pytest.raises(ValueError, match="policy_name"):
        _read(monkeypatch, _Fabric(policies={}), "   ")
