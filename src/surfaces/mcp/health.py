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


__all__ = ["HealthChecker", "Probe"]
