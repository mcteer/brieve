# SPDX-License-Identifier: Apache-2.0
"""How each product is checked for reachability, resolved by name from a manifest.

**Why this exists at all**, and it is the sharpest trap 013 had (analyze pass 12):

`HealthChecker.products()` derives its subject set from `registry.products()` — "derived,
never configured", so a loaded pack's product is monitored the moment its tools register.
That half is right and needs nothing. But the **probe** is supplied, and the only one wired
was `unconfigured_probe`, which returns `(False, "no probe configured for this product")`.

Follow that through with a real pack loaded:

    pack registers `vault_read` with product "vault"
      → checker starts watching "vault"
      → unconfigured_probe says unreachable
      → store records UNHEALTHY
      → dependency_pre_hook denies EVERY vault tool call
      → the agent is told "vault is not reachable"

while Vault is running perfectly. The message names the product, so whoever investigates
goes and checks Vault. 009's docstring states the assumption that made this safe — *"this
platform fakes product APIs by constitutional decision, so there is nothing here to reach
yet"* — and FR-027b is precisely the requirement that stops it being true.

**A probe is platform code, never pack code.** A pack names one; this module provides it.
The health checker is the single owner of "reachable" (FR-006a), and a pack supplying its
own reachability check would be the second opinion that rule exists to prevent — a pack
declaring its own product healthy is a pack marking its own homework.
"""

from __future__ import annotations

import os
import ssl
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping

from core.packs.registration import LoadedPack

Probe = Callable[[str], tuple[bool, str]]

#: How long a probe waits before calling a product unreachable. Short: this runs on a
#: supervisory pass, and a probe that blocks holds up every other product's check.
PROBE_TIMEOUT_SECONDS = 3.0


def vault_probe(product: str) -> tuple[bool, str]:
    """Vault's health endpoint, unauthenticated by design.

    `sys/health` needs no token — which is what makes it a *reachability* check rather than
    a permission check. A probe that authenticated would report a product down whenever a
    credential lapsed, and every run against it would suspend for a reason that had nothing
    to do with the product.
    """
    address = os.environ.get("VAULT_ADDR", "").strip()
    if not address:
        return False, "VAULT_ADDR is not set"
    # The enclave's Vault serves TLS under its own CA (VAULT_CACERT), and a probe that
    # ignored it would report "certificate verify failed" as unreachability — the probe
    # inventing an outage for a product that is up, which is the exact failure this module
    # exists to prevent. The first live conformance run failed on precisely this line.
    cacert = os.environ.get("VAULT_CACERT", "").strip()
    context = ssl.create_default_context(cafile=cacert) if cacert else None
    try:
        with urllib.request.urlopen(  # noqa: S310 — operator-supplied address, not user input
            f"{address.rstrip('/')}/v1/sys/health",
            timeout=PROBE_TIMEOUT_SECONDS,
            context=context,
        ) as response:
            # 200 initialized+unsealed+active, 429 standby, 473 performance standby. All
            # three answer, which is what reachability asks. Sealed (503) is not reachable:
            # a sealed Vault serves nothing, so calling it healthy would send every run into
            # a failure the platform could have predicted.
            return response.status in (200, 429, 473), f"sys/health {response.status}"
    except urllib.error.HTTPError as exc:
        return exc.code in (429, 473), f"sys/health {exc.code}"
    except Exception as exc:  # noqa: BLE001 — a probe raising IS an unreachable result
        return False, f"{type(exc).__name__}: {exc}"


def fixture_probe(product: str) -> tuple[bool, str]:
    """Reachable, because this product's tool layer is a fixture.

    For a pack whose product is **not deployed here** — Terraform, in this repository. Its
    tools are fixture-backed by decision (FR-027c), so there is nothing to reach and nothing
    that can be down.

    **This does not make the pack proven.** `contracts/conformance-packs.md` records that
    Terraform's tool layer was never exercised against a real product, and a row asserts that
    a pack's eval status and its tool reachability stay separate facts. A green probe here
    means "no product to be unreachable", not "the tools work".
    """
    return True, f"{product} is fixture-backed; no live product to reach"


def github_probe(product: str) -> tuple[bool, str]:
    """Whether the forge answers, for the product `open_proposal` reaches (041, FR-029).

    **Unauthenticated on purpose.** `/rate_limit` answers without a credential, and asking
    reachability is not asking permission — a probe that authenticated would report an outage
    when a token expired, sending an operator to the wrong incident. It would also need a
    credential in the health checker, which runs outside the publishing task and holds none.
    """
    root = (os.environ.get("GITHUB_API_URL") or "https://api.github.com").rstrip("/")
    try:
        with urllib.request.urlopen(  # noqa: S310 — operator-supplied root, not user input
            f"{root}/rate_limit", timeout=PROBE_TIMEOUT_SECONDS
        ) as response:
            return response.status == 200, f"rate_limit {response.status}"
    except urllib.error.HTTPError as exc:
        # 401/403 mean the forge is up and declined to answer this caller, which is
        # reachability. Only a transport failure is an outage.
        return exc.code in (401, 403), f"rate_limit {exc.code}"
    except Exception as exc:  # noqa: BLE001 — a probe raising IS an unreachable result
        return False, f"{type(exc).__name__}: {exc}"


#: Probes the platform provides, by the name a manifest may use.
#:
#: A manifest naming something absent from this table refuses `unresolved_binding` at load —
#: the same rule as a tool handler, and for the same reason: a name that resolves to nothing
#: must fail where the name was written.
PLATFORM_PROBES: dict[str, Probe] = {
    "vault_probe": vault_probe,
    "terraform_probe": fixture_probe,
    "github_probe": github_probe,
}

#: Product → probe for products the **platform** owns, which no pack manifest declares.
#:
#: This table exists because of a defect found while planning 041 (analysis C3). Adding a probe
#: to `PLATFORM_PROBES` alone does nothing: that table is consumed only by pack loading, which
#: resolves `manifest.probe` by name. A platform tool has no manifest, so its product would
#: reach `probes_for` never — and `dispatching_probe` falls through to "no probe configured",
#: which the health checker treats as unhealthy. `open_proposal` would have been denied while
#: GitHub was up, and a run suspended on it would have waited for a recovery signal that no
#: pack could ever produce.
#: `workspace` is the fixture toolset's product (`plan`, `apply`). Fixture-backed, so
#: `fixture_probe` is the honest answer: nothing live to reach, therefore nothing to be down.
PLATFORM_PRODUCT_PROBES: dict[str, Probe] = {
    "github": github_probe,
    "workspace": fixture_probe,
}


def probes_for(loaded: Mapping[str, LoadedPack]) -> dict[str, Probe]:
    """Product → probe, for the health checker.

    Keyed by **product** rather than by pack because that is what the checker probes and
    what the sweeper matches on. Two packs for one product would supply one probe between
    them, which is correct: reachability is a property of the product, not of who declared it.

    Platform products are merged in **first**, so a pack declaring a probe for the same
    product still wins. That ordering is deliberate: a pack that ships a better probe for a
    product the platform also touches should not be overridden by the platform's default.
    """
    table: dict[str, Probe] = dict(PLATFORM_PRODUCT_PROBES)
    table.update({pack.product: pack.probe for pack in loaded.values() if pack.probe is not None})
    return table


def dispatching_probe(loaded: Mapping[str, LoadedPack]) -> Probe:
    """One `Probe` over every loaded pack, falling through to unreachable.

    The fall-through is deliberate and must stay: a product with no probe is exactly the "we
    do not know" case, and `HealthState.UNKNOWN` is treated as unhealthy. The loader's
    `probe_required` refusal is what keeps that branch unreachable in practice — this is the
    backstop for a product that arrived some other way, not a second chance for a pack that
    declared none.
    """
    table = probes_for(loaded)

    def _probe(product: str) -> tuple[bool, str]:
        probe = table.get(product)
        if probe is None:
            return False, f"no probe configured for {product}"
        return probe(product)

    return _probe


__all__ = [
    "PLATFORM_PRODUCT_PROBES",
    "PLATFORM_PROBES",
    "github_probe",
    "PROBE_TIMEOUT_SECONDS",
    "Probe",
    "dispatching_probe",
    "fixture_probe",
    "probes_for",
    "vault_probe",
]
