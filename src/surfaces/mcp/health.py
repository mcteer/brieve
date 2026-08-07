# SPDX-License-Identifier: Apache-2.0
"""The dependency health checker — the single owner of "reachable".

Everything else reads what this records (FR-006a). Two components deciding what healthy
means will drift, and a run resumed against a dependency the other believes is down is
precisely the failure suspension exists to prevent.

**What it watches** is the distinct ``product`` values in the registry it is given, not a
separate configuration list. A monitor whose subject set can drift from the registry
eventually watches the wrong things — and, worse, a newly registered product would go
unmonitored while the mechanism reported healthy for everything it knew about.

**Granularity is a product**, as the registry names it. Per-workspace or per-endpoint
health would mean enumerating a customer's estate, which is a far larger claim on their
environment than asking whether a product answers at all.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from core.dependencies.store import PostgresDependencyStore
from core.dependencies.types import DependencyHealth
from core.registry.memory import ToolRegistry

#: How a product is probed. Returns (reachable, detail). Supplied rather than built in:
#: what "reachable" means is product-specific, and a checker that guessed would be
#: asserting something about systems it does not own.
Probe = Callable[[str], tuple[bool, str]]


@dataclass
class HealthChecker:
    """Probes each known product and records what it found."""

    registry: ToolRegistry
    store: PostgresDependencyStore
    probe: Probe

    def products(self) -> list[str]:
        """The distinct products the registry's tools reach.

        Derived, never configured. This is the whole reason the MCP service's registry is
        the estate's registry of record: before it, `ToolRegistry` was per-process and
        in-memory, so there was no instance a persistent service could read — the subject
        set had no source at all.
        """
        return self.registry.products()

    def sweep(self, products: Iterable[str] | None = None) -> list[DependencyHealth]:
        """Probe every product once and record each result.

        Failures probing one product do not stop the others: a checker that gave up on the
        first unreachable thing would leave the rest unknown, and unknown is unhealthy — so
        one outage would suspend runs against every product in the estate.
        """
        results: list[DependencyHealth] = []
        for product in products if products is not None else self.products():
            try:
                reachable, detail = self.probe(product)
            except Exception as exc:  # noqa: BLE001 — a probe raising IS an unreachable result
                reachable, detail = False, f"{type(exc).__name__}: {exc}"
            results.append(
                self.store.record_probe(product=product, reachable=reachable, detail=detail)
            )
        return results


@dataclass(frozen=True)
class DriftFlag:
    """An endorsed source has moved upstream. **Noticing changes nothing** (FR-017a).

    A notification, not an adoption. The console renders it; what answers rest on moves only
    when an administrator reviews and adopts. That separation is what makes the detection safe
    to run automatically at all — the cheap frequent operation cannot alter behaviour, and the
    operation that alters behaviour is a person's act with a name against it.
    """

    source: str
    upstream_tip: str
    adopted_tip: str
    detected_at: str
    #: Why detection could not answer, when it could not. A source that cannot be reached is
    #: **not** a source that has not moved, and reporting it as unchanged would tell an
    #: administrator their content is current when the platform has no idea.
    error: str = ""

    @property
    def moved(self) -> bool:
        return bool(self.upstream_tip) and self.upstream_tip != self.adopted_tip


@dataclass
class DriftChecker:
    """Whether each endorsed source still matches the version answers rest on (045, T013).

    **Rides the existing checker rather than a schedule of its own** (research R5, Principle
    VI). The persistent MCP service already hosts the dependency health checker, the resume
    sweeper and 042's scratch sweep for the same reason: they need a long-lived home. A second
    periodic mechanism would be the thousand-optional-dependencies death by another name.

    **A refs listing, never a clone.** Detection transfers no content, which is what makes it
    cheap enough to ride somebody else's cadence — and what keeps ADR-0070's egress bound to
    "did it move" rather than "give us everything".
    """

    #: Reads the endorsement record. A callable so this module depends on no fabric, matching
    #: every other reader in this tree.
    read_sources: Callable[[], dict[str, object]]
    #: `adopted_tip(tenant_id=..., source=...)` — what the adopted version recorded.
    store: object
    #: Lists the upstream tip. Injected so a row can exercise the comparison without a network.
    list_tip: Callable[[str], str]
    tenant_id: str = ""
    #: Supplies the timestamp. Injected rather than called, so a row asserts what was recorded
    #: rather than that something was.
    now: Callable[[], str] | None = None

    def sweep(self) -> list[DriftFlag]:
        """One comparison per endorsed source. Records nothing about content.

        A source that cannot be reached produces a flag carrying the error and **no claim
        either way** — `moved` is false because nothing was learned, and the error is what the
        console renders. Silently reporting "unchanged" would be the failure with the worst
        consequence here: an administrator told their material is current when the platform
        could not look.
        """
        from datetime import UTC, datetime

        from core.authority.endorsed_sources import citable_sources

        stamp = self.now() if self.now is not None else datetime.now(UTC).isoformat()
        flags: list[DriftFlag] = []

        try:
            record = self.read_sources()
        except Exception:  # noqa: BLE001 — an unreadable record means nothing is checked, and
            # saying nothing is the honest answer: inventing flags from a record we could not
            # read would report drift on sources that may not even be endorsed any more.
            return flags

        for name, source in citable_sources(record).items():
            adopted = ""
            try:
                adopted = str(
                    self.store.adopted_tip(tenant_id=self.tenant_id, source=name)  # type: ignore[attr-defined]
                    or ""
                )
            except Exception as exc:  # noqa: BLE001
                flags.append(
                    DriftFlag(
                        source=name,
                        upstream_tip="",
                        adopted_tip="",
                        detected_at=stamp,
                        error=f"{type(exc).__name__}",
                    )
                )
                continue

            try:
                upstream = self.list_tip(source.location)
            except Exception as exc:  # noqa: BLE001 — an unreachable source is not an unchanged
                # one, and the flag says so rather than reporting currency nobody verified.
                flags.append(
                    DriftFlag(
                        source=name,
                        upstream_tip="",
                        adopted_tip=adopted,
                        detected_at=stamp,
                        error=f"{type(exc).__name__}",
                    )
                )
                continue

            flags.append(
                DriftFlag(
                    source=name,
                    upstream_tip=upstream,
                    adopted_tip=adopted,
                    detected_at=stamp,
                )
            )
        return flags


__all__ = ["DriftChecker", "DriftFlag", "HealthChecker", "Probe"]
