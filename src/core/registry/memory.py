# SPDX-License-Identifier: Apache-2.0
"""In-process tool registry (registered vs unregistered only)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

from core.errors import RegistryError, ToolNotRegisteredError

ToolHandler = Callable[[Mapping[str, Any]], Any]
ProductMode = Literal["none", "federate", "broker"]


@dataclass(frozen=True)
class ToolRegistration:
    name: str
    handler: ToolHandler
    product_mode: ProductMode = "none"
    product: str | None = None
    product_action: str | None = None


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
        )

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
