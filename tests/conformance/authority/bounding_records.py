# SPDX-License-Identifier: Apache-2.0
"""Which records bound a run, and what happens when a run tries to move one (018).

The constitution's Quality Gates names *"registry isolation (agent-credential control-plane
writes observed denied)"* as blocking. Nothing implemented it and no ADR deferred it — 004
recorded the situation and declined to invent a citation to satisfy the clause.

The mechanism already holds: every policy grants read and list and nothing more, and the
records are written by a reviewed, separate path. What has never happened is the
**observation**. Until this module, the guarantee rested on someone having read the
configuration and concluded no write was granted, which is an argument. R4 is evidence over
claims, and that was a claim.

**Two halves, and the second is not a special case.**

A run's limits are stated twice: as records the platform consults, and as the grant the
control plane enforces. The first can be derived from what a run may read — every readable
path in that jurisdiction is a bound it must not write. The second cannot: a run holds no
read access to its own grant, so nothing built from its read grants can reach it, and
rewriting the grant moves the bound without touching any record.

Six analysis passes to get that right, four of which found a bound that would have gone
entirely unchecked. The pattern was always the same — every coverage mechanism anchored on
what a run can see, blind to every bound it cannot.

**What is NOT in scope**: the things a run writes as its work. Secrets in its own space,
configuration, product state — the `vault` pack ships a write tool for exactly that. A run may
spend the budget; it may not edit the budget. A check that drifted across that line would
forbid the platform's purpose while looking stricter.
"""

from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

#: The policy a run carries in the authority jurisdiction. Its read grants ARE the derived
#: half: every path a run may read here is a record it must not be able to write.
AUTHORITY_POLICY = "harness-authority-read"

#: Every policy a dispatched run's token actually carries, as deployed.
#:
#: All of them, not one. The claim is that a RUN cannot write its own bounds — stripping its
#: authority to a single grant would prove something narrower and leave open whether some
#: combination permits the write. An earlier draft required the opposite and was corrected
#: during planning.
RUN_POLICIES = ("harness-authority-read", "agent-pack-secrets", "harness-database")

#: Bounds a run cannot read, and which bind it anyway.
#:
#: **The half that matters, and the half three analysis passes missed.** A run's ceiling is
#: stated twice — as a record the platform consults, and as the grant the control plane
#: enforces. Writing the grant widens authority directly, bypassing every record the derived
#: rows check, and no derivation from a run's read grants can reach it because a run holds no
#: read access to any of these.
#:
#: `auth/nomad/config` is the sharpest of them and was missing until analysis pass 4: write it
#: and the control plane starts trusting key material somebody else holds, after which any
#: identity can be minted and no record in any jurisdiction has to change.
NAMED_BOUNDS: dict[str, str] = {
    "sys/policies/acl/agent-ceiling-planner": (
        "the grant itself — a run's ceiling stated as the capability the control plane "
        "enforces, rather than as the record the platform reads"
    ),
    "auth/nomad/role/agent-run": "decides which grants a run receives when it authenticates",
    "auth/nomad/config": (
        "decides whose identities are trusted at all. Write it and the control plane believes "
        "identities minted elsewhere; no record anywhere needs to change"
    ),
    "identity/entity": "attaches grants to an identity",
    "identity/group": "attaches grants to a group of identities",
    "sys/auth/probe-018": "creates an auth method — a new way for identities to be issued",
    "sys/mounts/probe-018": "creates a mount — changes what a path resolves to",
    # The version-control App key (ADR-0062, Principle IV's third named exception). Read by
    # the PUBLISHING task alone, through `authoring-publisher` bound to `nomad_task =
    # "proposer"`; `harness-authority-read` never names it, so no derivation from a run's read
    # grants can reach it. Write it and a run substitutes the credential every proposal is
    # opened with — authorship the forge attributes to this platform, under a key the run
    # chose.
    #
    # PROBE-SUFFIXED, unlike the real paths above. A write to `authoring/vcs-app` that
    # unexpectedly SUCCEEDED would clobber the operator-seeded key, and the failure would
    # present as an authentication outage — the shape `infra/modules/trust-fabric/authoring.tf`
    # already guards with `ignore_changes`. Same jurisdiction, name nothing owns.
    "harness-authority/data/authoring/probe-018": (
        "the version-control App key's jurisdiction — write here and a run supplies the "
        "credential its own pull requests are opened with"
    ),
}

#: The four kinds the control plane genuinely enumerates.
#:
#: Not "everything policy-affecting", which sounds total and is undecidable — a control plane
#: enumerates what it HAS, not what bounds a run, and the system-administration tree alone
#: exposes dozens of write paths. Naming four that can actually be listed is what makes the
#: completeness check a mechanism rather than a restatement of the list it checks.
ENUMERABLE_KINDS = ("mounts", "auth", "auth-roles", "policies")

#: Derived paths deliberately outside the subject set, and why.
#:
#: Checked against reality on every run: an exclusion naming something absent fails rather
#: than hides. That asymmetry is why an exclusion list is acceptable where a subject list is
#: not — 017 established it, and 018 spent an analysis pass rediscovering it.
EXCLUDED_PREFIXES: dict[str, str] = {}


class Outcome(Enum):
    """What happened when a run attempted a write. Three of four look alike from outside."""

    REFUSED = "refused"
    UNATTRIBUTABLE = "unattributable"
    PERMITTED = "permitted"
    UNREACHABLE = "unreachable"


class BoundingSetError(AssertionError):
    """The set could not be established. Never a skip."""


@dataclass(frozen=True)
class Attempt:
    """One write attempt, and what the control plane did with it."""

    path: str
    outcome: Outcome
    detail: str

    @property
    def is_evidence(self) -> bool:
        return self.outcome is Outcome.REFUSED


def _addr() -> str:
    return (os.environ.get("VAULT_ADDR") or "https://127.0.0.1:8200").rstrip("/")


def _ctx() -> ssl.SSLContext | None:
    ca = os.environ.get("VAULT_CACERT")
    return ssl.create_default_context(cafile=ca) if ca else None


def _request(
    path: str, token: str, *, method: str = "GET", body: dict[str, object] | None = None
) -> tuple[int, str]:
    """One control-plane request. Returns (status, detail) and never raises on 4xx."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(  # noqa: S310 — fixed scheme, operator-supplied addr
        f"{_addr()}/v1/{path}",
        data=data,
        headers={"X-Vault-Token": token, "Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=15, context=_ctx()) as response:  # noqa: S310
            return response.status, ""
    except urllib.error.HTTPError as exc:
        try:
            detail = (json.loads(exc.read() or b"{}").get("errors") or [""])[0]
        except Exception:  # noqa: BLE001 — the status is what matters
            detail = ""
        return exc.code, str(detail)
    except Exception as exc:  # noqa: BLE001 — unreachable is its own outcome
        return 0, f"{type(exc).__name__}: {exc}"


def admin_token() -> str:
    """Administrator authority, for ENUMERATION ONLY.

    Legal for coverage acts and forbidden for refusal assertions: a denial to an
    administrator proves nothing, because an administrator is not what the claim is about.
    Two kinds of act, two authorities, and mixing them would destroy the feature.
    """
    token = os.environ.get("VAULT_TOKEN", "").strip()
    if not token:
        raise BoundingSetError(
            "no administrator token available. The coverage checks enumerate what the "
            "control plane holds; they never assert a denial with it."
        )
    return token


def run_authority() -> str:
    """A token carrying everything a run carries, and nothing more.

    Minted rather than borrowed so the rows do not depend on a live allocation, and carrying
    all three policies because the claim is about the authority a run actually holds.
    """
    status, detail = _request(
        "auth/token/create",
        admin_token(),
        method="POST",
        body={"policies": list(RUN_POLICIES), "ttl": "10m", "no_parent": True},
    )
    if status != 200:
        raise BoundingSetError(f"could not mint a run-shaped authority: HTTP {status} {detail}")
    # Re-request to read the body; `_request` discards it on success by design.
    req = urllib.request.Request(  # noqa: S310
        f"{_addr()}/v1/auth/token/create",
        data=json.dumps({"policies": list(RUN_POLICIES), "ttl": "10m", "no_parent": True}).encode(),
        headers={"X-Vault-Token": admin_token(), "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15, context=_ctx()) as response:  # noqa: S310
        return str(json.loads(response.read())["auth"]["client_token"])


def _policy_text(name: str) -> str:
    req = urllib.request.Request(  # noqa: S310
        f"{_addr()}/v1/sys/policies/acl/{name}", headers={"X-Vault-Token": admin_token()}
    )
    try:
        with urllib.request.urlopen(req, timeout=15, context=_ctx()) as response:  # noqa: S310
            return str(json.loads(response.read())["data"]["policy"])
    except Exception as exc:  # noqa: BLE001
        raise BoundingSetError(f"could not read the policy {name!r}: {exc}") from exc


def bounding_paths() -> list[str]:
    """The derived half: every path a run may READ in the authority jurisdiction.

    Read from the **deployed** policy, not from configuration source. Reading the source is
    the argument this feature exists to replace with evidence, and a literal list in this
    module was already two entries stale on the day the spec was written.
    """
    import re

    text = _policy_text(AUTHORITY_POLICY)
    paths = sorted(
        {
            m.group(1)
            for m in re.finditer(r'path\s+"([^"]+)"', text)
            if not m.group(1).endswith("/metadata")
        }
    )
    return [p for p in paths if not any(p.startswith(x) for x in EXCLUDED_PREFIXES)]


def covered_prefixes() -> set[str]:
    """Every prefix something in this module accounts for — granted, or named.

    **Derived from the GRANTS, not from the probes**, and the difference is a defect this
    function exists to remove. `probe_targets()` deliberately skips a grant written as an
    exact path, because probing one would attempt to overwrite a real record. Coverage asking
    the same function was therefore asking *what do we write to* when the question is *what is
    accounted for* — so a record whose grant carries no glob read as uncovered.

    `protected-policies` is exactly that case, and the policy's own comment says why it has no
    glob: it is one record with no subpath, and a Vault glob does not match the empty
    remainder. `ask-bindings` and `model-matrix` escaped only because each also carries a glob
    sibling. `product-connections` and `endorsed-sources` are exact-only too, and would have
    joined the failure the moment anybody wrote one.

    Named bounds count as covering. A path the derivation cannot reach is not uncovered when
    this module names it and attempts a write against it.
    """
    covered: set[str] = set()
    for path in bounding_paths():
        # `harness-authority/data/harness-ceilings/*` accounts for that folder; the exact
        # `harness-authority/data/protected-policies` accounts for itself.
        covered.add(path[:-2] if path.endswith("/*") else path.rstrip("*").rstrip("/"))
    for path in NAMED_BOUNDS:
        covered.add(path.rsplit("/", 1)[0])
    return covered


#: What a probe writes into a bounding path. Never a real name — the write is expected to be
#: refused, and if it ever is not, `undo()` removes exactly this.
PROBE = "probe-018"


def probe_targets() -> list[str]:
    """Concrete paths to attempt, derived from the policy's patterns.

    A grant is written as a pattern; a write needs a path. `harness-ceilings/*` becomes
    `harness-ceilings/probe-018` — a name nothing owns, so a write that unexpectedly succeeds
    creates a record rather than overwriting somebody's.

    Listing paths are dropped: `metadata/claim-mappings` grants the ability to enumerate keys,
    not to hold a record, and attempting a write there would assert something about a
    capability nobody claims a run should have differently.
    """
    targets = []
    for path in bounding_paths():
        if "/metadata/" in path or path.endswith("/metadata"):
            continue
        if path.endswith("/*"):
            targets.append(path[:-1] + PROBE)
        elif path.endswith("*"):
            targets.append(path[:-1] + PROBE)
        else:
            # A grant on an exact path. Probing it would attempt to overwrite a real record,
            # so the pattern siblings above cover the jurisdiction and this one is skipped
            # deliberately rather than silently.
            continue
    return sorted(set(targets))


def jurisdictions() -> list[str]:
    """The mounts the derived paths occupy — derived, never named.

    Two at the time of writing. A bounding record placed in a third extends the coverage
    check without anyone editing it, which is the whole point: analysis pass 2 found the
    first version of this check covering the mount you would think of first and not the
    second, and the second held the record deciding whether a definition exists at all.
    """
    return sorted({p.split("/", 1)[0] for p in bounding_paths()})


def existing_prefixes() -> dict[str, list[str]]:
    """What actually exists in each jurisdiction, under administrator authority.

    A COVERAGE act. The derivation is blind to anything outside a run's read grants, and this
    is the only direction that blindness can be seen from.
    """
    found: dict[str, list[str]] = {}
    for mount in jurisdictions():
        for listing in (f"{mount}/metadata", mount):
            req = urllib.request.Request(  # noqa: S310
                f"{_addr()}/v1/{listing}?list=true", headers={"X-Vault-Token": admin_token()}
            )
            try:
                with urllib.request.urlopen(req, timeout=15, context=_ctx()) as response:  # noqa: S310
                    keys = json.loads(response.read())["data"]["keys"]
                    found[mount] = sorted(str(k).rstrip("/") for k in keys)
                    break
            except Exception:  # noqa: BLE001 — try the next listing shape
                continue
    return found


def enumerate_configuration_surfaces() -> dict[str, list[str]]:
    """The four kinds the control plane genuinely enumerates.

    Its mounts, its auth methods, the roles those methods issue, and the grants it holds.
    Every member must be a named bound or excluded with a reason — which is what stops
    `NAMED_BOUNDS` being a subject list that goes stale in silence.
    """
    out: dict[str, list[str]] = {}

    def _list(path: str, *, listing: bool = False) -> list[str]:
        url = f"{_addr()}/v1/{path}" + ("?list=true" if listing else "")
        req = urllib.request.Request(url, headers={"X-Vault-Token": admin_token()})  # noqa: S310
        try:
            with urllib.request.urlopen(req, timeout=15, context=_ctx()) as response:  # noqa: S310
                payload = json.loads(response.read())["data"]
                return sorted(str(k).rstrip("/") for k in (payload.get("keys") or payload))
        except Exception:  # noqa: BLE001 — an absent surface is an empty one here
            return []

    out["mounts"] = _list("sys/mounts")
    out["auth"] = _list("sys/auth")
    out["policies"] = _list("sys/policies/acl", listing=True)
    out["auth-roles"] = sorted(
        f"{method}/{role}"
        for method in out["auth"]
        for role in _list(f"auth/{method}/role", listing=True)
    )
    return out


def attempt_write(path: str, token: str, *, readable_check: bool = True) -> Attempt:
    """Try to write a bounding path, and say honestly what happened.

    **A refusal counts only when the same authority can READ the path.** Verified against the
    running control plane: a mount that does not exist is denied in words identical to a real
    bounding record. The control plane will not distinguish *forbidden* from *absent* —
    correctly, since disclosing which leaks the shape of the tree — and that is fatal to a row
    reading 403 as proof. One letter wrong in a path would pass forever, asserting nothing.

    `readable_check=False` for the named bounds: a run cannot read those either, so the
    discriminator does not apply and existence is confirmed with administrator authority
    instead.
    """
    status, detail = _request(path, token, method="POST", body={"data": {"probe-018": "x"}})

    if status == 0:
        return Attempt(path, Outcome.UNREACHABLE, detail)
    if 200 <= status < 300:
        return Attempt(path, Outcome.PERMITTED, f"HTTP {status} — the write took effect")
    if status != 403:
        return Attempt(path, Outcome.UNATTRIBUTABLE, f"HTTP {status} {detail}")

    if not readable_check:
        return Attempt(path, Outcome.REFUSED, detail)

    read_status, read_detail = _request(path, token)
    # The agent registry speaks a different dialect for absence, and `core/authority/
    # vault_fabric.py` already documents it: **it answers 400, not 404**, with "does not
    # exist" in the body — "found against the live enclave and not derivable from anywhere
    # else". A reader that generalised from KV reports an unregistered definition as an
    # outage; here it would report a genuine refusal as unattributable. Same trap, one
    # jurisdiction over, and the note that recorded it is what made this five minutes
    # instead of an afternoon.
    if read_status == 400 and "does not exist" in read_detail:
        return Attempt(path, Outcome.REFUSED, detail)
    # 200 and 404 both prove the path is INSIDE the grant: one found a record, the other
    # looked and found none. Only 403 means the authority cannot see the path at all, which
    # is the case that makes a write-denial meaningless.
    #
    # Requiring 200 was this module's own first bug, and the discriminator caught it: every
    # probe writes to a key that deliberately does not exist, so every read returned 404 and
    # every genuine refusal was reported as unattributable. A guard that failed closed on its
    # author's mistake is the guard working.
    if read_status == 403:
        return Attempt(
            path,
            Outcome.UNATTRIBUTABLE,
            f"refused, but the same authority cannot read the path either (HTTP "
            f"{read_status}) — the path may be misspelled or outside the grant, and a "
            f"denial says nothing on its own",
        )
    if read_status not in (200, 404):
        return Attempt(path, Outcome.UNATTRIBUTABLE, f"unexpected read status {read_status}")
    return Attempt(path, Outcome.REFUSED, detail)


def undo(path: str, token: str) -> str:
    """Remove what a PERMITTED write left behind.

    A red test is something someone re-runs; a widened bound is a live condition the check
    itself created. Walking away from it would make this gate the thing that moved a ceiling.
    """
    status, detail = _request(path, token, method="DELETE")
    if 200 <= status < 300 or status == 404:
        return "removed"
    return f"COULD NOT REMOVE: HTTP {status} {detail}"


__all__ = [
    "AUTHORITY_POLICY",
    "covered_prefixes",
    "ENUMERABLE_KINDS",
    "EXCLUDED_PREFIXES",
    "NAMED_BOUNDS",
    "RUN_POLICIES",
    "Attempt",
    "BoundingSetError",
    "Outcome",
    "admin_token",
    "attempt_write",
    "bounding_paths",
    "probe_targets",
    "enumerate_configuration_surfaces",
    "existing_prefixes",
    "jurisdictions",
    "run_authority",
    "undo",
]
