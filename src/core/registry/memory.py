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

#: How dangerous a tool is. In the glossary since the beginning and in no code until 013
#: (research.md F2), which was harmless while every registered tool was `echo` and stops
#: being harmless the moment a pack declares a tool that deletes infrastructure — the first
#: thing a Terraform or Vault pack does.
#:
#: **Nothing here enforces anything.** Principle II provides that registry review MAY
#: require process isolation for `secret_touching` and `destructive` tools; that provision
#: has never been actionable because the platform could not tell those tools from any
#: other. This makes the classification *knowable*. What is done with it is a separate
#: decision and deliberately not made here — a field that silently changed execution would
#: be an enforcement point nobody declared.
RiskClass = Literal["read", "write", "destructive", "secret_touching"]


@dataclass(frozen=True)
class ToolRegistration:
    name: str
    handler: ToolHandler
    #: Additive and defaulted to the safest value, so every pre-013 caller is unchanged.
    #: `read` rather than a nullable "unclassified": a tool nobody classified is not a tool
    #: with no risk, and defaulting to the narrowest claim means an unclassified
    #: `destructive` tool reads as under-declared rather than as unknown.
    risk_class: RiskClass = "read"
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
        risk_class: RiskClass = "read",
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
            risk_class=risk_class,
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

    def product_actions(self) -> list[str]:
        """Distinct product actions the registered tools perform.

        The other half of "what this platform can do", and the reason it exists is
        FR-005a: a ceiling naming an action no tool performs is a configuration error that
        must refuse rather than be silently dropped, and refusing requires knowing what is
        real. `products()` answered the 009 question — what does this estate touch — and
        could not answer this one.
        """
        return sorted({reg.product_action for reg in self._tools.values() if reg.product_action})

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
