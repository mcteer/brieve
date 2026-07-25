# SPDX-License-Identifier: Apache-2.0
"""Audit entry schema (sealed)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AuditEventType(StrEnum):
    RUN_START = "run_start"
    PRE_DECISION = "pre_decision"
    TOOL_OUTCOME = "tool_outcome"
    POST_DECISION = "post_decision"
    ENFORCEMENT_ERROR = "enforcement_error"


class AuditEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    correlation_id: str
    seq: int = Field(ge=0)
    event_type: AuditEventType
    timestamp: datetime
    payload: dict[str, Any]
    prev_hash: str
    entry_hash: str
