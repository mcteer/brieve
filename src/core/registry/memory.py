# SPDX-License-Identifier: Apache-2.0
"""In-process tool registry (registered vs unregistered only)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from core.errors import RegistryError, ToolNotRegisteredError

ToolHandler = Callable[[Mapping[str, Any]], Any]


@dataclass(frozen=True)
class ToolRegistration:
    name: str
    handler: ToolHandler


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolRegistration] = {}

    def register(self, name: str, handler: ToolHandler) -> None:
        if not name.strip():
            raise ValueError("tool name must be non-empty")
        self._tools[name] = ToolRegistration(name=name, handler=handler)

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
