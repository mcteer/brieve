# SPDX-License-Identifier: Apache-2.0
"""Audit entry schema (sealed)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EvidenceDisposition(StrEnum):
    """Why an evidence read returned what it returned.

    Both values can accompany a zero-row result, which is the entire point: an
    investigator needs to distinguish "nothing happened" from "you may not see it", and
    the caller must not be able to tell the difference at all (FR-011).
    """

    #: The query ran within the caller's scope. Zero rows means zero rows.
    SCOPED = "scoped"
    #: The query reached beyond the caller's scope. Zero rows means "not for you".
    OUT_OF_SCOPE = "out_of_scope"


class AuditEventType(StrEnum):
    RUN_START = "run_start"
    PRE_DECISION = "pre_decision"
    TOOL_OUTCOME = "tool_outcome"
    POST_DECISION = "post_decision"
    ENFORCEMENT_ERROR = "enforcement_error"
    AUTHORITY_ISSUED = "authority_issued"
    AUTHORITY_REFUSED = "authority_refused"
    AUTHORITY_DENIED = "authority_denied"
    AUTHORITY_EXPIRED = "authority_expired"
    MIRRORING_DECISION = "mirroring_decision"
    EVIDENCE_READ = "evidence_read"
    EVIDENCE_READ_REFUSED = "evidence_read_refused"
    #: An authority change the harness observed the trust fabric decide (ADR-0016, 007).
    #: Added here rather than reusing AUTHORITY_ISSUED: a change that was *requested* and
    #: is awaiting quorum has not issued anything, and filing it as an issuance would make
    #: the trail claim authority was granted at the moment it was asked for.
    AUTHORITY_CHANGE_OBSERVED = "authority_change_observed"


class AuditEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    correlation_id: str
    #: The bounding dimension of every evidence read, and INSIDE the hash chain.
    #: A tenant column beside the chain would leave the field that decides who may see a
    #: record alterable without breaking it — the one place that must not be true.
    tenant_id: str
    seq: int = Field(ge=0)
    event_type: AuditEventType
    timestamp: datetime
    payload: dict[str, Any]
    prev_hash: str
    entry_hash: str
