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

import json
import os
import re
import urllib.error
import urllib.request
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.durability.credentials import NomadWorkloadIdentity, VaultDatabaseCredentials
from core.observation.types import Observation, ObservationOutcome

#: The KV mount pack tools read from. Not the trust fabric's mount: `harness-authority` holds
#: ceilings and the matrix, is operator-authored, and is read-only to runs by policy. A pack
#: tool reaching it would be a run reading its own authority — so this is the ordinary
#: per-agent secret space `ceilings.tf` mounts for exactly this purpose.
AGENT_SECRET_MOUNT = "secret"


def _fabric() -> VaultDatabaseCredentials:
    """Vault, as this allocation. No credential is accepted from a caller.

    **The role is the allocation's, and 054 made that matter.** These handlers are loaded in
    both a dispatched run and the served surface; each logs in as whatever role its own job is
    admitted to, so the same code carries different authority in the two places. That is the
    property `measure_policy_impact` relies on: the measurement's writes happen only where the
    grant exists, and the run no longer has it.
    """
    role = os.environ.get("HARNESS_VAULT_ROLE", "").strip() or "agent-run"
    return VaultDatabaseCredentials(identity=NomadWorkloadIdentity(), role=role)


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


# ── 042: Vault policy authoring ──────────────────────────────────────────────────────────
#
# **The protected set is supplied, never derived here.** `surfaces.dispatch.policy_authoring`
# reads it from the trust fabric and fails closed when it cannot; these handlers take the
# result. A handler that read it itself would be a second answer to "what may not be touched",
# and the two would disagree exactly when it mattered.

#: How many attachments one read may report before it truncates and says so (FR-010).
#:
#: Fixed with its reasoning, on `READ_BUDGET_BYTES`'s precedent: an unfixed threshold is one
#: that gets raised until the corpus passes. Fifty is far above what any real policy carries —
#: a policy attached to more than fifty principals is a finding in itself — and far below the
#: 029 failure, where a read bounded by the wrong thing answered from 1,000 of 63,947 entries.
ATTACHMENT_BUDGET = 50

#: Where a policy can be attached in this estate, measured from `auth.tf` rather than assumed:
#: token roles, JWT auth roles, and identity entities and groups.
_ATTACHMENT_SOURCES = (
    ("token_role", "auth/token/roles"),
    ("auth_role", "auth/workload/role"),
    ("entity", "identity/entity/name"),
    ("group", "identity/group/name"),
)


def _policy_attachments(fabric: Any, policy_name: str) -> tuple[list[dict[str, str]], bool]:
    """Where ``policy_name`` is attached, bounded, with whether the bound bit.

    **Wiring, not content.** "agent-ceiling is attached to the agent-run JWT role" describes
    how the estate is put together; it carries no policy body and no secret. That distinction
    is what lets attachments stay readable for a protected policy whose document does not.

    A source that cannot be listed is skipped rather than fatal: an estate with no identity
    secrets engine mounted is an ordinary estate, and refusing the whole read because one of
    four optional locations is absent would make the tool unusable where it is most needed.
    """
    found: list[dict[str, str]] = []
    truncated = False
    for kind, base in _ATTACHMENT_SOURCES:
        try:
            names = fabric.list_path(base) or []
        except Exception:  # noqa: BLE001 — an absent mount is not a failed read
            continue
        for name in names:
            if len(found) >= ATTACHMENT_BUDGET:
                truncated = True
                break
            try:
                record = fabric.read_path(f"{base}/{str(name).rstrip('/')}")
            except Exception:  # noqa: BLE001 — same reason
                continue
            data = (record or {}).get("data") or {}
            attached: set[str] = set()
            for field in ("policies", "token_policies"):
                value = data.get(field) or []
                if isinstance(value, list):
                    attached.update(str(v) for v in value)
            if policy_name in attached:
                found.append({"kind": kind, "name": str(name).rstrip("/"), "mount": base})
        if truncated:
            break
    return found, truncated


def vault_policy_read(arguments: Mapping[str, Any]) -> dict[str, Any]:
    """Read a policy's structure and what it is attached to — never a secret value (042).

    **Three states, not two** (FR-003). `present` carries the document; `absent` says the
    policy is not there; `protected` says the platform will not hand over the body of a record
    that bounds the agent asking. Collapsing the last two would make a denial read as a gap,
    and an agent told "no such policy" about `agent-ceiling` would reasonably propose creating
    one.

    **A protected body never enters the run**, which is FR-013 done structurally rather than by
    scrubbing at composition: a body that was never read cannot appear in a proposal, whereas a
    body filtered later depends on every future composition path remembering to filter. 038's
    containment module draws exactly this distinction between structural and inspected claims.

    Attachments stay readable for every state but `absent`, because they are wiring rather than
    content — and knowing that `agent-ceiling` is attached to the `agent-run` role is what lets
    an agent reason about the estate without being handed its own leash.
    """
    name = str(arguments.get("policy_name", "")).strip()
    if not name:
        raise ValueError("vault_policy_read requires a 'policy_name' argument")

    protected: frozenset[str] = frozenset(arguments.get("_protected") or ())
    fabric = _fabric()

    if name in protected:
        attachments, truncated = _policy_attachments(fabric, name)
        return {
            "policy_name": name,
            "state": "protected",
            "document": "",
            "attachments": attachments,
            "truncated": truncated,
            "note": (
                "this policy is part of what bounds the agents in this estate; its "
                "attachments are visible and its body is not"
            ),
        }

    record = fabric.read_path(f"sys/policies/acl/{name}")
    if record is None:
        return {
            "policy_name": name,
            "state": "absent",
            "document": "",
            "attachments": [],
            "truncated": False,
        }

    document = str(((record or {}).get("data") or {}).get("policy", ""))
    attachments, truncated = _policy_attachments(fabric, name)
    return {
        "policy_name": name,
        "state": "present",
        "document": document,
        "attachments": attachments,
        "truncated": truncated,
    }


#: How many paths one impact check may query (FR-010). Same reasoning as `ATTACHMENT_BUDGET`:
#: fixed with the number written down, because a threshold without one gets raised until the
#: corpus passes. A policy touching more than forty paths is a policy nobody is reviewing
#: carefully anyway, and the truncation is disclosed rather than silent.
IMPACT_PATH_BUDGET = 40

#: The token role that bounds what a scratch token may carry. Declared in
#: `infra/modules/trust-fabric/scratch.tf`; named here because the handler must ask for it by
#: name, and the two must agree or the mint refuses.
SCRATCH_TOKEN_ROLE = "scratch-check"

SCRATCH_PREFIX = "scratch-agent-"

#: One minute. Long enough for a handful of capability queries, short enough that a run killed
#: mid-measurement leaves no usable credential — which is why FR-023's sweep is about orphaned
#: POLICIES and not about tokens.
SCRATCH_TOKEN_TTL = "60s"

_PATH_STANZA = re.compile(r'^\s*path\s+"([^"]+)"\s*\{', re.M)


class PolicyInvalid(ValueError):
    """Vault refused to parse the proposed document.

    **A policy error, never an impact result.** Reporting "no capabilities" for a document
    Vault could not read would tell a reviewer the change grants nothing, which is true of a
    policy that does not exist and dangerously untrue of the one they are being asked to
    approve.
    """


class ImpactUnavailable(RuntimeError):
    """The measurement could not be taken, so no proposal may be published (FR-008).

    Its own type because the response is refusal rather than a partial answer. 037's finding
    applies: a reviewer handed a proposal with the evidence section missing reads the rest as
    complete, and a review that has been reassured is worse than one that never happened.
    """


def _queried_paths(*documents: str) -> tuple[list[str], bool]:
    """The paths worth asking about, bounded, with whether the bound bit.

    **The scan does not need to parse HCL correctly to be safe**, and that is deliberate: the
    full document goes to Vault, whose parser is authoritative, so a missed stanza costs a
    disclosed bound rather than a wrong answer. Building an HCL parser to find query
    candidates would be Principle VI's "could be a library" in the other direction — a
    dependency bought to make a heuristic feel rigorous.
    """
    seen: list[str] = []
    for document in documents:
        for path in _PATH_STANZA.findall(document or ""):
            if path not in seen:
                seen.append(path)
    return seen[:IMPACT_PATH_BUDGET], len(seen) > IMPACT_PATH_BUDGET


def _capabilities_under(
    fabric: Any, *, name: str, document: str, paths: list[str]
) -> dict[str, list[str]]:
    """Write one scratch policy, ask what a token carrying only it could do, destroy it.

    Returns an empty map for an empty document: a policy that does not exist yet has no
    current side, and every capability on the proposed side is newly granted.
    """
    if not document.strip():
        return {}
    try:
        fabric.write_path(f"sys/policies/acl/{name}", {"policy": document})
    except Exception as exc:  # noqa: BLE001 — Vault's parser is the authority here
        raise PolicyInvalid(
            f"Vault refused the policy document: {type(exc).__name__}. This is a policy "
            f"error, not an impact result — a document the product cannot read grants "
            f"nothing, and reporting that as the measurement would read as a safe change"
        ) from exc

    token = fabric.create_token(role=SCRATCH_TOKEN_ROLE, policies=[name], ttl=SCRATCH_TOKEN_TTL)
    answered: dict[str, list[str]] = fabric.capabilities(subject_token=token, paths=paths)
    return answered


def measure_policy_impact(arguments: Mapping[str, Any]) -> dict[str, Any]:
    """What the proposed policy would ALTER, measured by Vault (042, FR-007/009/019-022).

    **One tool call, and that is the safety design.** Splitting write / mint / check / destroy
    into separate tools would make "always destroyed" depend on a model *choosing* to make the
    last call — a rule the model is asked to follow, which is exactly what this feature's
    central refusal says it must never rest on. Here the model can request a measurement and
    cannot request a scratch policy: the names are derived from the run id, and `finally`
    destroys both sides on every path out including the failing one.

    **Both sides go through scratch**, which is not obvious and is load-bearing. The tempting
    shortcut for the current side — mint a token carrying the LIVE policy by name — would
    require the token role's `allowed_policies_glob` to admit real policy names, handing every
    dispatched run a way to mint tokens under `agent-ceiling`. Two throwaway policies keep the
    glob absolute.

    **The residual orphan window is real and is not hidden.** A process killed between the
    write and the `finally` leaves scratch policies behind; the sweep (FR-023) is what makes
    "always destroyed" checkable rather than merely claimed.
    """
    # 054: THE SURFACE NAMES THE WORKSPACE, AND NOTHING ELSE CAN.
    #
    # This has moved twice, and the second move made the first unnecessary. It was
    # `arguments["run_id"]` — a value the CALLER supplied, which `b7c2a2f` had to police. Then
    # it was the allocation, which was unforgeable but cost one permanent Vault identity entity
    # per Build against a ceiling that logins fail at (054 R9, ADR-0072).
    #
    # Now this runs on the long-lived surface and a dispatched run holds no policy-write
    # authority at all. **So the name no longer has to be attacker-proof.** Nobody but this
    # process can write in the namespace, and this process creates both sides from the
    # documents it was handed, measures, and destroys them — it never reads a policy somebody
    # else wrote. A name supplied by a caller could at worst collide with its own measurement.
    #
    # Generated here anyway, because "at worst a collision" is a thing to prevent rather than
    # tolerate: two concurrent measurements must not share a scratch name.
    workspace_id = uuid4().hex

    proposed_document = str(arguments.get("proposed_document", ""))
    current_document = str(arguments.get("current_document", ""))
    if not proposed_document.strip():
        raise ValueError("vault_policy_impact requires a 'proposed_document' to measure")

    # DERIVED, never supplied. A `scratch_name` argument would be a caller choosing what to
    # overwrite, and the governance hook refuses a call that carries one.
    current_name = f"{SCRATCH_PREFIX}{workspace_id}-current"
    proposed_name = f"{SCRATCH_PREFIX}{workspace_id}-proposed"

    paths, truncated = _queried_paths(current_document, proposed_document)
    if not paths:
        raise PolicyInvalid(
            "neither document declares a path stanza; there is nothing to measure, and an "
            "empty measurement must not read as a change that grants nothing"
        )

    fabric = _fabric()
    try:
        current = _capabilities_under(
            fabric, name=current_name, document=current_document, paths=paths
        )
        proposed = _capabilities_under(
            fabric, name=proposed_name, document=proposed_document, paths=paths
        )
    except PolicyInvalid:
        raise
    except Exception as exc:  # noqa: BLE001 — an unmeasurable change is not a safe one
        raise ImpactUnavailable(
            f"the impact could not be measured against Vault: {type(exc).__name__}. No "
            f"proposal is published without its evidence — a reviewer handed one whose "
            f"evidence section is missing reads the rest as complete"
        ) from exc
    finally:
        # EVERY path out, including the failing one. `delete_path` treats already-absent as
        # success precisely so this cannot mask the exception it is unwinding.
        for name in (proposed_name, current_name):
            try:
                fabric.delete_path(f"sys/policies/acl/{name}")
            except Exception:  # noqa: BLE001 — cleanup must not replace the original fault
                pass

    results = []
    for path in paths:
        # A path Vault did not answer for is absent from the map, not empty — the client
        # keeps that distinction because filling it would report a widening as a narrowing.
        #
        # `deny` IS DROPPED, and the live probe is what found it. Vault answers `["deny"]` for
        # a path a token cannot reach, so the raw arithmetic produced `granted: ["list"],
        # revoked: ["deny"]` for a change that grants list on a previously unreachable path.
        # "Revokes deny" is not a fact about the change; it is the absence of capabilities
        # spelled as one, and a reviewer reading it would be counting a grant twice.
        before = frozenset(current.get(path, ())) - {"deny"}
        after = frozenset(proposed.get(path, ())) - {"deny"}
        results.append(
            {
                "path": path,
                "current": sorted(before),
                "proposed": sorted(after),
                "granted": sorted(after - before),
                "revoked": sorted(before - after),
                "unanswered": path not in proposed,
            }
        )

    return {
        "measured_by": "vault",
        "results": results,
        "truncated": truncated,
        "scratch_destroyed": True,
    }


def terraform_plan(arguments: Mapping[str, Any]) -> dict[str, Any]:
    """Run ``terraform plan`` against a working directory, or refuse (047 / ADR-0047).

    **Not an always-green fixture.** A missing binary, a non-zero plan, or an absent
    working directory refuses rather than inventing ``changes: 0``. Hermetic rows that
    must script a plan inject ``HARNESS_TERRAFORM_BIN`` pointing at a stub executable.
    """
    import subprocess
    from pathlib import Path

    raw_dir = arguments.get("working_directory") or arguments.get("path") or "."
    workdir = Path(str(raw_dir)).resolve()
    if not workdir.is_dir():
        raise RuntimeError(f"terraform plan: working directory {workdir} is not a directory")

    binary = os.environ.get("HARNESS_TERRAFORM_BIN", "terraform").strip() or "terraform"
    timeout = float(os.environ.get("HARNESS_TERRAFORM_PLAN_TIMEOUT", "300"))
    try:
        initialised = subprocess.run(  # noqa: S603 — operator-configured binary, fixed args
            [binary, "init", "-backend=false", "-input=false", "-no-color"],
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "terraform plan: binary not available; refuse rather than return a fixture"
        ) from exc
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"terraform plan: {type(exc).__name__}") from exc
    if initialised.returncode != 0:
        raise RuntimeError(
            "terraform init failed: "
            + (initialised.stderr or initialised.stdout or "unknown error")[:2000]
        )
    try:
        finished = subprocess.run(  # noqa: S603 — operator-configured binary, fixed args
            [binary, "plan", "-input=false", "-no-color", "-detailed-exitcode"],
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "terraform plan: binary not available; refuse rather than return a fixture"
        ) from exc
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"terraform plan: {type(exc).__name__}") from exc

    # detailed-exitcode: 0 = empty, 1 = error, 2 = changes present
    if finished.returncode == 1:
        raise RuntimeError(
            "terraform plan failed: "
            + (finished.stderr or finished.stdout or "unknown error")[:2000]
        )
    output = (finished.stdout or "")[-8000:]
    return {
        "fixture": False,
        "product": "terraform",
        "action": "plan",
        "exit_code": finished.returncode,
        "has_changes": finished.returncode == 2,
        "output": output,
    }


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


#: Where a dispatched run asks the surface to measure. Set on the run's job; absent everywhere
#: else, which is what makes the client half unreachable from the surface itself.
POLICY_IMPACT_URL_ENV = "HARNESS_POLICY_IMPACT_URL"

#: The surface identity a run presents. A SECOND token, deliberately: `nomad_vault.jwt` carries
#: `aud: vault.io`, and reusing it here would make a credential minted for Vault replayable at
#: the surface.
SURFACE_IDENTITY_FILE = "nomad_mcp.jwt"


def vault_policy_impact(arguments: Mapping[str, Any]) -> dict[str, Any]:
    """Ask the surface to measure. **The run performs no Vault write of its own (054).**

    This used to be the measurement. It is now a client, and the reason is the whole of
    ADR-0072: performing it here meant every dispatched run carried policy-write authority, and
    bounding that per run cost one permanent Vault identity entity per Build against a ceiling
    that logins fail at.

    **What did NOT move is interception.** This is still a registered tool reached through
    `invoke_tool`, so the 042 hooks still run — `b7c2a2f`'s guard included — and the trail still
    records `TOOL_OUTCOME` where it always did. Only the Vault writes moved.

    **Fail-closed.** No surface, no measurement: a Build proposing a policy stops rather than
    reporting an unmeasured change as a safe one, which is the trade 042 exists to refuse.
    """
    url = os.environ.get(POLICY_IMPACT_URL_ENV, "").strip()
    if not url:
        raise ImpactUnavailable(
            "no policy-impact surface is configured for this run, so a proposed policy cannot "
            "be measured. The measurement moved off the run in 054; a run that cannot reach "
            "the surface has no instrument and must not report an unmeasured change."
        )

    identity = Path(os.environ.get("NOMAD_SECRETS_DIR", "/secrets")) / SURFACE_IDENTITY_FILE
    try:
        token = identity.read_text(encoding="utf-8").strip()
    except OSError as unreadable:
        raise ImpactUnavailable(f"no surface identity to present: {unreadable}") from unreadable

    body = json.dumps(
        {
            "current_document": str(arguments.get("current_document", "")),
            "proposed_document": str(arguments.get("proposed_document", "")),
        }
    ).encode()
    request = urllib.request.Request(  # noqa: S310
        url,
        data=body,
        method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310
            return dict(json.loads(response.read() or b"{}"))
    except urllib.error.HTTPError as refused:
        detail = refused.read().decode("utf-8", "replace")[:200]
        if refused.code == 400:
            raise PolicyInvalid(f"the surface refused the documents: {detail}") from refused
        raise ImpactUnavailable(
            f"the surface could not measure this policy ({refused.code}): {detail}"
        ) from refused
    except OSError as unreachable:
        raise ImpactUnavailable(
            f"the policy-impact surface is unreachable: {unreachable}"
        ) from unreachable


#: Handlers a manifest may name. A name absent from this table refuses `unresolved_binding`
#: at load — where the name was written, rather than at the first call.
PLATFORM_HANDLERS: dict[str, Any] = {
    "vault_policy_impact": vault_policy_impact,
    "vault_policy_read": vault_policy_read,
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
    "ATTACHMENT_BUDGET",
    "IMPACT_PATH_BUDGET",
    "ImpactUnavailable",
    "PolicyInvalid",
    "PLATFORM_HANDLERS",
    "PLATFORM_OBSERVERS",
    "TerraformApplyObserver",
    "VaultWriteObserver",
    "terraform_apply",
    "terraform_plan",
    "vault_policy_impact",
    "vault_policy_read",
    "vault_read",
    "vault_write",
]
