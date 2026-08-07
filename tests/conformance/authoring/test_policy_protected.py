# SPDX-License-Identifier: Apache-2.0
"""V1, V5 — the protected set, and the refusal that arrives before anything is read (042).

**This is the feature's safety case at its cheapest layer**, and the file says so because the
cheapness is also the weakness: request validation binds on the policy a request *names*, and
a run that changes its mind mid-flight sails past it. The hook (V2) is what catches that, and
Vault's ACL (V16) is what catches a platform bug. Three layers, and this is the first.

**V5 is the row that decides what an outage means.** An unreadable fabric and an empty
protected set arrive identically — as no names — and treating them the same would let a run
author `agent-ceiling` during a Vault incident with every other row in this feature still
green, because they all supply a set.
"""

from __future__ import annotations

from typing import Any

import pytest

from core.authoring.request import AuthoringRequest, RequestRefused
from surfaces.dispatch.policy_authoring import (
    PROTECTED_POLICIES_PATH,
    PolicyAuthoringRequest,
    ProtectedSet,
    ProtectedSetUnavailable,
    read_protected_set,
)

TENANT = "tenant-test"
REPO = "acme/vault-policies"
PROTECTED = frozenset({"agent-ceiling", "authoring-publisher", "scratch-policy-check"})


def _record(**overrides: Any) -> dict[str, Any]:
    """The KV v2 shape the fabric returns: data wrapping data."""
    body = {"schema_version": 1, "names": sorted(PROTECTED), **overrides}
    return {"data": {"data": body, "metadata": {"version": 3}}}


def _request(target: str) -> PolicyAuthoringRequest:
    return PolicyAuthoringRequest(
        authoring=AuthoringRequest(
            correlation_id="corr-1",
            tenant_id=TENANT,
            requester="alice",
            target_repository=REPO,
            task="Grant the payments app read on its own KV prefix",
            pack="vault",
        ),
        target_policy=target,
    )


def _validate(request: PolicyAuthoringRequest, protected: ProtectedSet) -> None:
    request.validate(
        run_tenant_id=TENANT,
        owned_repositories=frozenset({REPO}),
        packs_declaring_authoring=frozenset({"vault"}),
        protected=protected,
    )


# ── V5: the set is read, and an unreadable one fails closed ────────────────────────────


def test_row_v5_a_published_set_is_read() -> None:
    """The ordinary case, without which every refusal below could be vacuous."""
    protected = read_protected_set(
        lambda path: _record() if path == PROTECTED_POLICIES_PATH else None
    )

    assert protected.names == PROTECTED
    assert protected.source == PROTECTED_POLICIES_PATH, (
        "the trail names WHICH list refused, so a reader is not left to find it"
    )


def test_row_v5_an_unreachable_fabric_refuses_rather_than_reading_as_unprotected() -> None:
    """V5 — the row this file exists for.

    A Vault outage that resolved to "nothing is protected" would permit exactly the write the
    feature prevents, and would do it at the moment nobody is watching the platform closely.
    """

    def _down(path: str) -> dict[str, Any]:
        raise ConnectionError("vault unreachable")

    with pytest.raises(ProtectedSetUnavailable) as raised:
        read_protected_set(_down)

    assert raised.value.reason_code == "protected_set_unavailable"
    assert "outage" in str(raised.value)


def test_row_v5_an_absent_record_refuses_as_an_incomplete_apply() -> None:
    """Absent is a fabric problem, not a statement that nothing needs protecting.

    The trust fabric publishes this record with the policies it declares, so the two cannot
    honestly disagree — and if they do, the apply is what is wrong.
    """
    with pytest.raises(ProtectedSetUnavailable) as raised:
        read_protected_set(lambda path: None)

    assert "apply is" in str(raised.value)


def test_row_v5_an_empty_published_set_refuses() -> None:
    """The subtle one. A record naming nothing is not a permissive estate.

    Nothing in this platform writes this record except the module that declares the policies,
    and that module always has some — so an empty list means something else wrote it.
    """
    with pytest.raises(ProtectedSetUnavailable):
        read_protected_set(lambda path: _record(names=[]))


def test_row_v5_an_unsupported_schema_refuses_rather_than_being_guessed_at() -> None:
    """The same posture `parse_matrix_record` takes, and for the same reason."""
    with pytest.raises(ProtectedSetUnavailable):
        read_protected_set(lambda path: _record(schema_version=99))


# ── V1: the refusal arrives before anything is read ────────────────────────────────────


def test_row_v1_a_request_naming_a_trust_fabric_policy_refuses() -> None:
    """V1 — the cheapest layer of the central refusal (FR-004)."""
    with pytest.raises(RequestRefused) as raised:
        _validate(_request("agent-ceiling"), ProtectedSet(names=PROTECTED))

    assert raised.value.reason_code == "policy_protected"
    assert "Principle IV" in str(raised.value), (
        "the refusal names the rule rather than only denying, because an operator who hits "
        "it needs to know it is a boundary and not a bug"
    )


def test_row_v1_the_refusal_precedes_every_041_check_it_does_not_replace() -> None:
    """041's `validate` runs first and unchanged (FR-014).

    Composition rather than inheritance is what makes this true: a subclass overriding
    `validate` is the easiest way to break "the tier is consumed unchanged" without touching
    a line of 041's code, so this row watches the ordering that proves it did not happen.
    """
    request = PolicyAuthoringRequest(
        authoring=AuthoringRequest(
            correlation_id="corr-1",
            tenant_id=TENANT,
            requester="alice",
            target_repository="someone-else/repo",  # 041 refuses this
            task="t",
            pack="vault",
        ),
        target_policy="agent-ceiling",  # 042 would refuse this
    )

    with pytest.raises(RequestRefused) as raised:
        _validate(request, ProtectedSet(names=PROTECTED))

    assert raised.value.reason_code == "repository_not_owned", (
        "041's ownership check must still fire first; this feature adds a refusal rather "
        "than reordering the ones that were already there"
    )


def test_row_v1_the_measurement_namespace_cannot_be_requested_as_a_target() -> None:
    """FR-020 from the request side: scratch names belong to the impact check alone."""
    with pytest.raises(RequestRefused) as raised:
        _validate(_request("scratch-agent-run-1-proposed"), ProtectedSet(names=PROTECTED))

    assert raised.value.reason_code == "scratch_name_forged"


def test_row_v1_an_unprotected_policy_is_permitted() -> None:
    """The row without which every refusal above could be a gate that cannot pass.

    A safety case satisfied by refusing everything is not a safety case — it is the feature
    being unusable, which is exactly what the rejected runtime derivation would have caused
    (research R4).
    """
    _validate(_request("payments-app-read"), ProtectedSet(names=PROTECTED))  # must not raise


def test_row_v1_protection_is_an_exact_match_not_a_prefix() -> None:
    """Over-refusal is the mirror-image failure, and it reads as strength.

    `agent-ceiling-demo` is not `agent-ceiling`. A prefix rule would forbid authoring for
    anything whose name merely starts like a platform record, which makes the safety case
    look stronger while quietly removing the capability.
    """
    _validate(_request("agent-ceiling-demo"), ProtectedSet(names=PROTECTED))  # must not raise


def test_row_v1_a_request_naming_no_policy_refuses() -> None:
    """What is being changed is not something to infer from the task text."""
    with pytest.raises(RequestRefused) as raised:
        _validate(_request("   "), ProtectedSet(names=PROTECTED))

    assert raised.value.reason_code == "target_policy_required"
