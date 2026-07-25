# SPDX-License-Identifier: Apache-2.0
"""Hook decision types and registration."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class HookPhase(StrEnum):
    PRE = "pre"
    POST = "post"


class CapabilityKind(StrEnum):
    GOVERNANCE = "governance"
    OTHER = "other"


class HookDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome: Literal["allow", "deny"]
    reason_code: str = ""
    message: str = ""
    phase: HookPhase | None = None
    hook_name: str = ""
    correlation_id: str = ""
    tool_name: str = ""


@dataclass
class HookContext:
    correlation_id: str
    tool_name: str
    arguments: Mapping[str, Any]
    phase: HookPhase
    executed: bool = False
    execution_error_code: str | None = None
    probe_log: list[str] = field(default_factory=list)
    # Populated for built-in governance hooks only. Third-party hooks must not depend on
    # this attribute; the hook context narrows further before the Hook SDK seam ships.
    run: Any = None  # GovernedRun; duck-typed to avoid import cycles


HookHandler = Callable[[HookContext], HookDecision]


@dataclass(frozen=True)
class HookRegistration:
    name: str
    phase: HookPhase
    capability_kind: CapabilityKind
    handler: HookHandler
