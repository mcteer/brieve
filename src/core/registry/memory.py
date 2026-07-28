# SPDX-License-Identifier: Apache-2.0
"""In-process tool registry (registered vs unregistered only)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

from core.errors import RegistryError, ToolNotRegisteredError
from core.observation.types import Observer

ToolHandler = Callable[[Mapping[str, Any]], Any]
ProductMode = Literal["none", "federate", "broker"]


@dataclass(frozen=True)
class ToolRegistration:
    name: str
    handler: ToolHandler
    product_mode: ProductMode = "none"
    product: str | None = None
    product_action: str | None = None
    #: False when repeating the call could duplicate an external effect. Declared by
    #: the tool author — only they know — and deliberately NOT inferred from
    #: ``product_mode``, which is orthogonal: a federated call can be non-repeatable
    #: and a brokered one idempotent.
    repeatable: bool = True
    #: How to find out what actually happened, for a call interrupted mid-flight.
    #: Required in practice for a non-repeatable tool: without one, an interrupted
    #: step resolves to CANNOT_DETERMINE and parks the run.
    observer: Observer | None = None


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolRegistration] = {}

    def register(
        self,
        name: str,
        handler: ToolHandler,
        *,
        product_mode: ProductMode = "none",
        product: str | None = None,
        product_action: str | None = None,
        repeatable: bool = True,
        observer: Observer | None = None,
    ) -> None:
        if not name.strip():
            raise ValueError("tool name must be non-empty")
        if product_mode != "none" and (not product or not product_action):
            raise ValueError("product and product_action required when product_mode != none")
        self._tools[name] = ToolRegistration(
            name=name,
            handler=handler,
            product_mode=product_mode,
            product=product,
            product_action=product_action,
            repeatable=repeatable,
            observer=observer,
        )

    def observers(self) -> dict[str, Observer]:
        """Observers by tool name, for resolving open intents on resume."""
        return {name: reg.observer for name, reg in self._tools.items() if reg.observer is not None}

    def tool_names(self) -> list[str]:
        """Every registered tool name.

        Read-only, and added by 009 because the health checker needs to know which
        products the estate's tools reach. The registry could resolve a name and could not
        be enumerated — built for one caller that always knew what it was asking for,
        which is the shape of most of this feature's findings.
        """
        return sorted(self._tools)

    def products(self) -> list[str]:
        """Distinct products the registered tools reach.

        Here rather than in the checker so there is one answer to "what does this estate
        touch". A second implementation would drift, and the drift would show up as a
        product nobody was monitoring.
        """
        return sorted({reg.product for reg in self._tools.values() if reg.product})

    def resolve(self, name: str) -> ToolRegistration:
        """Resolve a tool by name.

        Raises:
            ToolNotRegisteredError: name unknown
            RegistryError: resolution infrastructure failed
        """
        try:
            tool = self._tools.get(name)
        except Exception as exc:  # noqa: BLE001 — fail closed on unexpected lookup errors
            raise RegistryError(f"registry resolution failed: {type(exc).__name__}") from exc
        if tool is None:
            raise ToolNotRegisteredError(f"tool not registered: {name}")
        return tool
