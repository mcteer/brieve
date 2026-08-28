# SPDX-License-Identifier: Apache-2.0
"""V11-V14 — the instrument, and what it refuses to guess (042, US3).

**V12 is the row the feature is for.** A proposal whose "impact" is model prose is a review
that has been reassured rather than informed — 037's finding, in a new place. So the row is
written to fail if the evidence would read identically without the measurement: a widening
change must be *visibly* wider, in a field a reviewer can point at.

**V13 is the row that keeps V12 honest.** An instrument that degrades to "no capabilities
found" when it cannot run would report every unmeasurable change as a safe one, at exactly the
moment the platform is least able to tell.

The scratch lifecycle is asserted here against a scripted Vault; V15-V17 assert it against the
real one, because a fixture that reports its own cleanup is not evidence of cleanup.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from surfaces import handlers
from surfaces.handlers import ImpactUnavailable, PolicyInvalid

RUN = "corr-042"

#: 054, second move: the workspace is named by the SURFACE, per call.
#:
#: The measurement now runs on the long-lived surface and a dispatched run holds no
#: policy-write authority at all, so the name no longer has to be attacker-proof — nobody but
#: that process can write in the namespace. It is generated per call anyway, so two concurrent
#: measurements cannot collide.
CURRENT = 'path "secret/data/payments/*" {\n  capabilities = ["read"]\n}\n'
WIDER = 'path "secret/data/payments/*" {\n  capabilities = ["read", "create", "update"]\n}\n'


class _Vault:
    """A scripted Vault that answers capability questions from the policy it was handed.

    Deliberately literal: it maps each written document to the capabilities its stanza
    declares, so the row exercises the handler's *sequencing and arithmetic* rather than a
    canned answer. What it cannot prove is that the real product agrees — which is V15's job.
    """

    def __init__(self, *, refuse_write: bool = False, refuse_capabilities: bool = False) -> None:
        self.written: dict[str, str] = {}
        self.deleted: list[str] = []
        self.minted: list[dict[str, Any]] = []
        self._refuse_write = refuse_write
        self._refuse_capabilities = refuse_capabilities

    def write_path(self, path: str, payload: dict[str, Any], **_: Any) -> None:
        if self._refuse_write:
            raise RuntimeError("policy parse error")
        self.written[path.rsplit("/", 1)[-1]] = str(payload["policy"])

    def delete_path(self, path: str, **_: Any) -> None:
        self.deleted.append(path.rsplit("/", 1)[-1])

    def create_token(self, *, role: str, policies: list[str], ttl: str, **_: Any) -> str:
        self.minted.append({"role": role, "policies": list(policies), "ttl": ttl})
        return f"token-for-{policies[0]}"

    def capabilities(self, *, subject_token: str, paths: list[str]) -> dict[str, list[str]]:
        if self._refuse_capabilities:
            raise RuntimeError("vault unreachable")
        document = self.written.get(subject_token.removeprefix("token-for-"), "")
        caps = ["read", "create", "update"] if "create" in document else ["read"]
        return {path: caps for path in paths}


def _impact(monkeypatch: pytest.MonkeyPatch, vault: _Vault, **arguments: Any) -> Mapping[str, Any]:
    monkeypatch.setattr(handlers, "_fabric", lambda: vault)
    result: Mapping[str, Any] = handlers.measure_policy_impact({"run_id": RUN, **arguments})
    return result


def test_row_v11_the_scratch_names_are_derived_from_the_allocation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """V11 — FR-020, and 054 moved what they derive FROM.

    A model can request a measurement; it cannot request a policy name. Until 054 the name came
    from a caller-supplied `run_id`, which the hook had to police. It now comes from the
    allocation the code is running in, which no caller can influence at all.
    """
    vault = _Vault()

    _impact(monkeypatch, vault, current_document=CURRENT, proposed_document=WIDER)

    written = sorted(vault.written)
    assert len(written) == 2
    stems = {name.removeprefix("scratch-agent-").rsplit("-", 1)[0] for name in written}
    assert len(stems) == 1, f"the two sides must share one workspace stem: {written}"
    assert written[0].endswith("-current") and written[1].endswith("-proposed")
    assert all(name.startswith("scratch-agent-") for name in vault.written)


def test_row_v11_a_supplied_scratch_name_is_ignored_by_the_handler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Defence in depth: the hook refuses such a call, and the handler would not honour it.

    Two layers because they fail differently — the hook can be unregistered (V3 proves it),
    and a handler that trusted an argument would then be the whole of the protection.
    """
    vault = _Vault()

    _impact(
        monkeypatch,
        vault,
        current_document=CURRENT,
        proposed_document=WIDER,
        scratch_name="agent-ceiling",
    )

    assert "agent-ceiling" not in vault.written


def test_row_v12_a_widening_change_is_visibly_wider(monkeypatch: pytest.MonkeyPatch) -> None:
    """V12 — SC-009, and written so it fails if the impact section were dropped.

    The assertion is on `granted`, not on the documents: a row that compared the two policy
    texts would pass with the measurement removed entirely, which is the shape this feature
    exists to replace.
    """
    result = _impact(monkeypatch, _Vault(), current_document=CURRENT, proposed_document=WIDER)

    entry = result["results"][0]
    assert entry["path"] == "secret/data/payments/*"
    assert entry["granted"] == ["create", "update"], (
        "the evidence must state what the change ADDS. A reviewer inferring it from two "
        "policy bodies is doing the work the instrument exists to do"
    )
    assert entry["revoked"] == []
    assert result["measured_by"] == "vault"


def test_row_v12_a_narrowing_change_reports_what_it_removes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both directions, because a revocation is as reviewable as a grant — and more likely
    to break something a person cares about."""
    result = _impact(monkeypatch, _Vault(), current_document=WIDER, proposed_document=CURRENT)

    entry = result["results"][0]
    assert entry["revoked"] == ["create", "update"]
    assert entry["granted"] == []


def test_row_v12_a_new_policy_has_an_empty_current_side(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A policy that does not exist yet grants everything it declares, and says so.

    No special case in the handler: an empty current document writes no scratch policy and
    answers no capabilities, so the arithmetic falls out.
    """
    result = _impact(monkeypatch, _Vault(), current_document="", proposed_document=WIDER)

    entry = result["results"][0]
    assert entry["current"] == []
    assert entry["granted"] == ["create", "read", "update"]


def test_row_v13_an_unmeasurable_change_refuses_rather_than_reporting_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """V13 — FR-008, and the row that keeps V12 from being a lie under stress.

    An instrument that degraded to "no capabilities found" would report every unmeasurable
    change as safe, at the moment the platform is least able to tell.
    """
    with pytest.raises(ImpactUnavailable) as raised:
        _impact(
            monkeypatch,
            _Vault(refuse_capabilities=True),
            current_document=CURRENT,
            proposed_document=WIDER,
        )

    assert "without its evidence" in str(raised.value)


def test_row_v14_an_invalid_policy_is_a_policy_error_not_an_impact_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """V14 — Vault's parser is the authority, and its refusal keeps its own name.

    Reporting "no capabilities" for a document Vault could not read is true of a policy that
    does not exist and dangerously untrue of the one being proposed.
    """
    with pytest.raises(PolicyInvalid):
        _impact(
            monkeypatch,
            _Vault(refuse_write=True),
            current_document=CURRENT,
            proposed_document="this is not HCL",
        )


def test_the_scratch_policies_are_destroyed_on_the_way_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FR-022's ordinary path."""
    vault = _Vault()

    _impact(monkeypatch, vault, current_document=CURRENT, proposed_document=WIDER)

    assert sorted(vault.deleted) == sorted(vault.written)


def test_the_scratch_policies_are_destroyed_even_when_the_measurement_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FR-022's real requirement, and the reason the sequence is ONE tool call.

    Three tools would make this depend on a model choosing to call the third. Here the
    `finally` runs on the failing path, so the only orphan left is a process killed mid-call
    — which is what the sweep exists for and is why "always destroyed" is checkable rather
    than merely claimed.
    """
    vault = _Vault(refuse_capabilities=True)

    with pytest.raises(ImpactUnavailable):
        _impact(monkeypatch, vault, current_document=CURRENT, proposed_document=WIDER)

    # BOTH sides, though the failure came before the second was written. That is the claim:
    # the `finally` destroys the workspace it named, not merely the parts it reached.
    deleted = sorted(vault.deleted)
    assert len(deleted) == 2, f"both sides must be destroyed, got {deleted}"
    stems = {name.removeprefix("scratch-agent-").rsplit("-", 1)[0] for name in deleted}
    assert len(stems) == 1
    assert [n.rsplit("-", 1)[1] for n in deleted] == ["current", "proposed"]


def test_the_scratch_token_carries_only_the_policy_under_measurement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One policy per token, through the bounding role, at the short TTL.

    A token carrying both sides would answer for the union and report every change as
    granting nothing.
    """
    vault = _Vault()

    _impact(monkeypatch, vault, current_document=CURRENT, proposed_document=WIDER)

    assert [m["policies"] for m in vault.minted] == [[n] for n in sorted(vault.written)]
    assert {m["role"] for m in vault.minted} == {"scratch-check"}
    assert {m["ttl"] for m in vault.minted} == {"60s"}


def test_no_capability_is_invented_for_a_path_vault_did_not_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The client keeps unanswered distinct from denied; the handler must not undo that.

    Silently treating an unanswered proposed path as "no capabilities" would report a
    widening as a narrowing — the one direction a safety instrument must never be wrong in.
    """

    class _Partial(_Vault):
        def capabilities(self, *, subject_token: str, paths: list[str]) -> dict[str, list[str]]:
            return {}

    result = _impact(monkeypatch, _Partial(), current_document=CURRENT, proposed_document=WIDER)

    entry = result["results"][0]
    assert entry["unanswered"] is True, (
        "an unanswered path must be visible as unanswered; a reviewer reading `granted: []` "
        "with no flag would conclude the change grants nothing"
    )


def test_a_measurement_with_no_paths_refuses_rather_than_reporting_a_safe_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An empty measurement must not read as a change that grants nothing."""
    with pytest.raises(PolicyInvalid):
        _impact(monkeypatch, _Vault(), current_document="", proposed_document="# just a comment")


def test_the_path_budget_truncates_and_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-010 for the impact side. 029's lesson: a silent bound reads as completeness."""
    many = "".join(
        f'path "secret/data/app-{n:03d}" {{\n  capabilities = ["read"]\n}}\n'
        for n in range(handlers.IMPACT_PATH_BUDGET + 5)
    )
    result = _impact(monkeypatch, _Vault(), current_document="", proposed_document=many)

    assert result["truncated"] is True
    assert len(result["results"]) == handlers.IMPACT_PATH_BUDGET


def test_vaults_deny_marker_is_not_treated_as_a_capability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Found by the live probe (PL1), which is what the live probe is for.

    Vault answers `["deny"]` for a path a token cannot reach. The first version of the
    arithmetic took that literally and reported, for a change granting `list` on a previously
    unreachable path:

        granted: ["list"], revoked: ["deny"]

    "Revokes deny" is not a fact about the change — it is the absence of capabilities spelled
    as one, and a reviewer reading it counts the same grant twice. No hermetic row would have
    caught it, because the scripted Vault never returned Vault's actual marker.
    """

    class _Denying(_Vault):
        def capabilities(self, *, subject_token: str, paths: list[str]) -> dict[str, list[str]]:
            document = self.written.get(subject_token.removeprefix("token-for-"), "")
            return {path: (["list"] if "list" in document else ["deny"]) for path in paths}

    result = _impact(
        monkeypatch,
        _Denying(),
        current_document='path "secret/metadata/x" {\n  capabilities = ["read"]\n}\n',
        proposed_document='path "secret/metadata/x" {\n  capabilities = ["list"]\n}\n',
    )

    entry = result["results"][0]
    assert entry["granted"] == ["list"]
    assert entry["revoked"] == [], "`deny` is not a capability and must not read as one"
    assert entry["current"] == []


# ------------------------------------------------------------------ 054


def test_no_argument_can_move_the_workspace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """054's security property, which got simpler when the measurement moved.

    It was: the workspace is named by the allocation, so an argument cannot move it. It is now
    named by this process, per call, and a dispatched run cannot write in the namespace at all.

    Two calls claiming wildly different run ids write different workspaces — not the SAME one,
    which is what an earlier draft asserted. Uniqueness is the property now: a caller cannot
    steer the name anywhere, including onto somebody else's.
    """
    first = _Vault()
    _impact(monkeypatch, first, current_document=CURRENT, proposed_document=WIDER)

    second = _Vault()
    monkeypatch.setattr(handlers, "_fabric", lambda: second)
    handlers.measure_policy_impact(
        {
            "run_id": "some-other-runs-correlation-id",
            "current_document": CURRENT,
            "proposed_document": WIDER,
        }
    )

    assert sorted(second.written) != sorted(first.written), (
        "two measurements shared a workspace name. Concurrent measurements would then "
        "overwrite each other's scratch policies and report the wrong impact."
    )
    assert all("some-other-runs" not in name for name in second.written), (
        "an argument reached the workspace name. It is generated here for exactly this reason."
    )


def test_a_measurement_that_did_not_happen_is_not_a_measurement_that_found_nothing() -> None:
    """054 T037 — the distinction a reviewer's decision rests on.

    "The impact check did not run" and "the impact check found no change" lead a reviewer to
    opposite conclusions, and the second is the dangerous one to report by accident. They are
    different types by construction, and this asserts the construction rather than trusting it.

    `ImpactUnavailable` is a `RuntimeError` and `PolicyInvalid` a `ValueError`, so neither can
    be caught by a handler expecting the other, and neither is a dict a caller could mistake
    for a result. The client half raises the same two, so moving the measurement to the surface
    did not collapse them into one.
    """
    from surfaces.handlers import ImpactUnavailable, PolicyInvalid

    assert issubclass(ImpactUnavailable, RuntimeError)
    assert issubclass(PolicyInvalid, ValueError)
    assert not issubclass(ImpactUnavailable, PolicyInvalid)
    assert not issubclass(PolicyInvalid, ImpactUnavailable)

    # And the client raises them too — a run that cannot reach the surface must not report a
    # change as unmeasured-but-harmless.
    import inspect

    from surfaces import handlers

    client = inspect.getsource(handlers.vault_policy_impact)
    assert "ImpactUnavailable" in client, (
        "the client half no longer refuses when it cannot measure, so a Build could publish a "
        "proposal whose impact was never taken"
    )
