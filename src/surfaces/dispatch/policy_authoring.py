# SPDX-License-Identifier: Apache-2.0
"""Vault policy authoring's product-aware half (042).

**Everything Vault-specific about this feature lives here or in `surfaces.handlers`.** 041's
authoring tier is product-blind on purpose — a Terraform module and a Vault policy are
written identically — and `test_core_is_product_blind` refuses otherwise. It caught 041 doing
exactly this, which is why the boundary is worth naming rather than assuming.

**The central refusal, three independent layers.** The enclave's Vault holds the policies that
bound the agents running in it, so this is the first feature that could be asked — by a
prompt, by a mistake, or by an instruction planted in a subject — to author the records that
bound the run doing the authoring. Principle IV is unambiguous, and a rule the model is asked
to follow is not a structure:

1. **request validation**, here — a protected `target_policy` refuses before anything is read
2. **a GOVERNANCE pre-hook**, here — the model tried anyway; the act refuses and is recorded
3. **Vault's own ACL**, in `infra/modules/trust-fabric/scratch.tf` — nothing outside
   `scratch-agent-*` is writable at all, which is the only layer that survives a platform bug

Layer 2 is the one V3 deletes to prove the safety case can lose.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from core.authoring.request import AuthoringRequest, RequestRefused

#: Where the trust fabric publishes what it declares. Read-only to runs by policy, on the
#: same mount and the same posture as ceilings and the matrix.
PROTECTED_POLICIES_PATH = "harness-authority/data/protected-policies"

#: The reserved measurement namespace (FR-020). Named here and in `scratch.tf`, and a unit
#: row asserts no trust-fabric policy occupies it.
SCRATCH_PREFIX = "scratch-agent-"

SUPPORTED_SCHEMA_VERSION = 1


class ProtectedSetUnavailable(RequestRefused):
    """The protected set could not be read, so nothing may be authored.

    **Its own type because the response is its own.** An unreadable fabric is an outage; a
    policy that is in the set is a governance decision. Collapsing them would send an
    operator to argue with the protected list during an incident.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message, reason_code="protected_set_unavailable")


@dataclass(frozen=True)
class ProtectedSet:
    """The trust-fabric policies no authoring run may touch."""

    names: frozenset[str]
    #: Which record refused, so the trail names the list rather than leaving it to be found.
    source: str = PROTECTED_POLICIES_PATH

    def protects(self, policy_name: str) -> bool:
        """Whether ``policy_name`` is out of bounds, on an exact match.

        **Exact, not prefix.** A prefix rule would make `agent-ceiling-demo` protected
        because `agent-ceiling` is, which quietly forbids authoring for anything whose name
        starts like a platform record — the over-refusal that makes a safety case look
        strong while making the feature unusable.
        """
        return policy_name.strip() in self.names

    def is_scratch(self, policy_name: str) -> bool:
        """Whether the name belongs to the measurement namespace, which nobody may request."""
        return policy_name.strip().startswith(SCRATCH_PREFIX)


def read_protected_set(read_versioned: Any) -> ProtectedSet:
    """Read the published set, or refuse (FR-006, V5).

    **Fail-closed, and the distinction is the point.** An absent record and an unreachable
    fabric both arrive here as "no names", and treating either as an empty set would mean a
    run authoring `agent-ceiling` during a Vault outage — with every row in this feature
    still green, because they all supply a set. `MatrixSource` already draws exactly this
    line for the same reason; this is that reasoning one record over.

    An empty published list is also refused. The trust fabric declares its own policies, so a
    set with nothing in it means the record was written by something that is not that module.
    """
    try:
        record = read_versioned(PROTECTED_POLICIES_PATH)
    except Exception as exc:  # noqa: BLE001 — any read fault is a read fault
        raise ProtectedSetUnavailable(
            f"the protected-policy set could not be read from {PROTECTED_POLICIES_PATH!r}: "
            f"{type(exc).__name__}. Nothing is authored against an unknown protected set — "
            f"an outage that read as 'nothing is protected' would permit exactly the write "
            f"this feature exists to prevent"
        ) from exc

    if record is None:
        raise ProtectedSetUnavailable(
            f"no protected-policy record at {PROTECTED_POLICIES_PATH!r}; the trust fabric "
            f"publishes it with the policies it declares, so its absence means the apply is "
            f"incomplete rather than that nothing needs protecting"
        )

    data = record.get("data", record) if isinstance(record, Mapping) else {}
    inner = data.get("data", data) if isinstance(data, Mapping) else {}
    version = inner.get("schema_version")
    if version != SUPPORTED_SCHEMA_VERSION:
        raise ProtectedSetUnavailable(
            f"protected-policy record carries schema_version {version!r}, not "
            f"{SUPPORTED_SCHEMA_VERSION}; guessing at a record this decides authority from "
            f"is how a set gets misread"
        )

    names = frozenset(str(name).strip() for name in inner.get("names") or () if str(name).strip())
    if not names:
        raise ProtectedSetUnavailable(
            "the protected-policy record names nothing. The trust fabric declares its own "
            "policies and publishes them together, so an empty set means the record was "
            "written by something other than that module"
        )
    return ProtectedSet(names=names)


@dataclass(frozen=True)
class PolicyAuthoringRequest:
    """041's request plus the policy it is about (FR-004).

    **Composition rather than inheritance**, so `AuthoringRequest.validate` runs exactly as
    041 wrote it and this adds a check rather than replacing a set of them. FR-014 says the
    tier is consumed unchanged, and a subclass overriding `validate` is the easiest way to
    break that without touching a line of 041's code.
    """

    authoring: AuthoringRequest
    target_policy: str

    def validate(
        self,
        *,
        run_tenant_id: str,
        owned_repositories: frozenset[str],
        packs_declaring_authoring: frozenset[str],
        protected: ProtectedSet,
    ) -> None:
        """Refuse before anything is read, or return (V1).

        **Layer 1 of three.** This is the cheapest refusal and the least trustworthy: it
        binds on the policy the request NAMES, and a run that changed its mind mid-flight
        would sail past it. That is what the hook is for. Both exist because a refusal that
        arrives after a subject has been cloned and read has already done the work it was
        supposed to prevent — 041's request module makes the same argument about producing
        files.
        """
        self.authoring.validate(
            run_tenant_id=run_tenant_id,
            owned_repositories=owned_repositories,
            packs_declaring_authoring=packs_declaring_authoring,
        )

        target = self.target_policy.strip()
        if not target:
            raise RequestRefused(
                "a policy-authoring request names no target policy; what is being changed "
                "is not something to infer from the task text",
                reason_code="target_policy_required",
            )
        if protected.is_scratch(target):
            raise RequestRefused(
                f"{target!r} is in the measurement namespace {SCRATCH_PREFIX!r}, which "
                f"belongs to the impact check. A request naming one is either confused or "
                f"trying to have a throwaway policy published as a real one",
                reason_code="scratch_name_forged",
            )
        if protected.protects(target):
            raise RequestRefused(
                f"{target!r} is a trust-fabric policy: it is part of what bounds the agents "
                f"in this estate, including the one that would be authoring it. Agents are "
                f"structurally excluded from managing their own platform (Principle IV), and "
                f"this refusal arrives before anything is read or authored",
                reason_code="policy_protected",
            )


__all__ = [
    "PROTECTED_POLICIES_PATH",
    "SCRATCH_PREFIX",
    "PolicyAuthoringRequest",
    "ProtectedSet",
    "ProtectedSetUnavailable",
    "read_protected_set",
]
