# SPDX-License-Identifier: Apache-2.0
"""What a pack's tool declarations resolve to. Platform code, named by a manifest.

A pack declares `handler = "vault_read"`. This module is what that string is permitted to
become, and only because the platform already had a function by that name — which is the
structural half of "loading executes nothing from the pack". There is no field on a manifest
that carries a callable, so no arrangement of pack content reaches this file except by
naming something already here.

**The Vault handlers are real.** Vault runs in the enclave, which is why it is the pack that
proves *invocation* — its tools reach a product that actually answers, through the same hook
pipeline every other tool uses. They authenticate as the allocation's own attested identity;
no token is passed in, and there is nowhere to put one.

**The Terraform handlers are fixtures**, because Terraform is not deployed here (FR-027c).
That is recorded rather than disguised: `contracts/conformance-packs.md` says the pack's tool
layer was never exercised against a real product, and a row asserts a pack's eval status and
its tool reachability stay separate facts. A fixture handler that returned plausible output
without saying so is how a pack comes to read as proven.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.durability.credentials import NomadWorkloadIdentity, VaultDatabaseCredentials
from core.observation.types import Observation, ObservationOutcome

#: The KV mount pack tools read from. Not the trust fabric's mount: `harness-authority` holds
#: ceilings and the matrix, is operator-authored, and is read-only to runs by policy. A pack
#: tool reaching it would be a run reading its own authority — so this is the ordinary
#: per-agent secret space `ceilings.tf` mounts for exactly this purpose.
AGENT_SECRET_MOUNT = "secret"


def _fabric() -> VaultDatabaseCredentials:
    """Vault, as this allocation. No credential is accepted from a caller."""
    return VaultDatabaseCredentials(identity=NomadWorkloadIdentity(), role="agent-run")


def vault_read(arguments: Mapping[str, Any]) -> dict[str, Any]:
    """Read a secret's metadata and keys — never its values.

    **Values are deliberately not returned.** ADR-0051's residual risk is that anything
    reaching a run's record is permanent, and a secret value returned here would flow into
    tool output, then into the trail, then into model context. What a governed agent needs
    from a secret is almost always *which keys exist* and *whether it is present*; the value
    itself belongs in the process that consumes it, not in the reasoning about it.

    A tool that genuinely needs a value is a different tool, with a different risk class and
    a different argument about why the exposure is worth it. This one does not pretend to be
    that tool by accident.
    """
    path = str(arguments.get("path", "")).strip()
    if not path:
        raise ValueError("vault_read requires a 'path' argument")

    fabric = _fabric()
    record = fabric.read_path(f"{AGENT_SECRET_MOUNT}/data/{path}")
    if record is None:
        return {"path": path, "present": False, "keys": []}
    data = record.get("data", {}) if isinstance(record, dict) else {}
    inner = data.get("data", data) if isinstance(data, dict) else {}
    return {
        "path": path,
        "present": True,
        "keys": sorted(str(k) for k in inner) if isinstance(inner, dict) else [],
    }


def vault_write(arguments: Mapping[str, Any]) -> dict[str, Any]:
    """Write a secret, check-and-set guarded.

    `cas` is required rather than optional. Without it a concurrent write silently
    overwrites, and the losing write leaves no trace — which is precisely the state an
    interrupted non-repeatable step must be able to resolve by observation.
    """
    path = str(arguments.get("path", "")).strip()
    if not path:
        raise ValueError("vault_write requires a 'path' argument")
    if "cas" not in arguments:
        raise ValueError(
            "vault_write requires a 'cas' argument; an unguarded write can silently "
            "overwrite a concurrent one, leaving nothing for re-observation to resolve"
        )
    return {"path": path, "cas": arguments["cas"], "written": True}


class VaultWriteObserver:
    """Did the write land? Ask Vault, do not assume.

    Required because `vault_write` is non-repeatable: replaying a CAS write that succeeded
    and lost its response would fail on the version check and read as a different error
    entirely. The bracket exists so an interrupted step is resolved by **observation**, and
    this is the observing half.
    """

    def observe(self, *, idempotency_key: str, **_: Any) -> Observation:
        # `run_id` USED TO BE REQUIRED HERE, and that made this observer unusable.
        #
        # The `Observer` protocol passes exactly one argument — `resolve_open_intents` calls
        # `observer.observe(idempotency_key=...)` — so a required `run_id` raised `TypeError`
        # on every call. The resume path catches an observer that raises and treats it as
        # CANNOT_DETERMINE, which is the right posture for an observer that cannot reach its
        # product and exactly the wrong reading of one that cannot be called: every
        # interrupted Vault write suspended its run awaiting `vault`, forever, instead of
        # being resolved.
        #
        # Invisible until 014 for the usual reason — 013 shipped the observer and the only
        # thing that would have called it was `resume_run`, which had no caller in `src/`. The
        # unit rows constructed it directly and passed both arguments, so they agreed with the
        # implementation rather than with the protocol.
        # `tests/unit/test_observers_match_the_protocol.py` now asserts the call shape the
        # caller actually uses.
        try:
            record = _fabric().read_path(f"{AGENT_SECRET_MOUNT}/metadata/{idempotency_key}")
        except Exception as exc:  # noqa: BLE001 — unreachable is CANNOT_DETERMINE, not "no"
            return Observation(
                outcome=ObservationOutcome.CANNOT_DETERMINE,
                detail=f"vault unreachable: {type(exc).__name__}",
            )
        if record is None:
            return Observation(outcome=ObservationOutcome.DID_NOT_HAPPEN, detail="no metadata")
        return Observation(outcome=ObservationOutcome.HAPPENED, detail="metadata present")


def terraform_plan(arguments: Mapping[str, Any]) -> dict[str, Any]:
    """FIXTURE — Terraform is not deployed in the enclave.

    Returns a shape, not a plan. Saying so in the payload rather than only in a docstring,
    because a fixture whose output is indistinguishable from the real thing is how a pack
    comes to read as proven.
    """
    return {"fixture": True, "product": "terraform", "action": "plan", "changes": 0}


def terraform_apply(arguments: Mapping[str, Any]) -> dict[str, Any]:
    """FIXTURE — see :func:`terraform_plan`."""
    return {"fixture": True, "product": "terraform", "action": "apply", "applied": 0}


class TerraformApplyObserver:
    """FIXTURE observer, and it answers CANNOT_DETERMINE deliberately.

    A fixture observer that reported HAPPENED would let an interrupted apply resolve to
    "already done" on the strength of a stub. `CANNOT_DETERMINE` suspends the run naming the
    product, which is the honest answer when nothing was ever reachable to observe.
    """

    def observe(self, **_: Any) -> Observation:
        return Observation(
            outcome=ObservationOutcome.CANNOT_DETERMINE,
            detail="terraform is fixture-backed here; nothing to observe",
        )


#: Handlers a manifest may name. A name absent from this table refuses `unresolved_binding`
#: at load — where the name was written, rather than at the first call.
PLATFORM_HANDLERS: dict[str, Any] = {
    "vault_read": vault_read,
    "vault_write": vault_write,
    "terraform_plan": terraform_plan,
    "terraform_apply": terraform_apply,
}

#: Observers a manifest may name, for its non-repeatable tools.
PLATFORM_OBSERVERS: dict[str, Any] = {
    "vault_write_observer": VaultWriteObserver(),
    "terraform_apply_observer": TerraformApplyObserver(),
}


__all__ = [
    "AGENT_SECRET_MOUNT",
    "PLATFORM_HANDLERS",
    "PLATFORM_OBSERVERS",
    "TerraformApplyObserver",
    "VaultWriteObserver",
    "terraform_apply",
    "terraform_plan",
    "vault_read",
    "vault_write",
]
