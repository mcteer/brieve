# SPDX-License-Identifier: Apache-2.0
"""Primary adapter: Pydantic AI bound to the governed core (sealed).

Contents are limited to the four mappings of ADR-0001 and FR-002:

1. tools -> hook-wrapped governed tool calls (:mod:`~adapters.pydantic_ai.tools`)
2. state -> the durability seam (:mod:`~adapters.pydantic_ai.durability`)
3. interrupts -> approval hooks (:mod:`~adapters.pydantic_ai.approvals`)
4. run context -> identity and correlation (:mod:`~adapters.pydantic_ai.run_context`)

Anything beyond that mapping belongs in ``core``. No authority manufacture, audit
schema, or registry lifecycle lives here.
"""

from adapters.pydantic_ai.agent import build_governed_agent, start_adapter_run
from adapters.pydantic_ai.approvals import request_approval
from adapters.pydantic_ai.durability import (
    CredentialInCheckpointError,
    load_state,
    save_state,
)
from adapters.pydantic_ai.governance import GovernanceCapability
from adapters.pydantic_ai.run_context import AdapterRunContext
from adapters.pydantic_ai.tools import GovernedToolError, GovernedToolset

__all__ = [
    "AdapterRunContext",
    "CredentialInCheckpointError",
    "GovernanceCapability",
    "GovernedToolError",
    "GovernedToolset",
    "build_governed_agent",
    "load_state",
    "request_approval",
    "save_state",
    "start_adapter_run",
]
