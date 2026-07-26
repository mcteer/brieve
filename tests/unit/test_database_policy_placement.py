# SPDX-License-Identifier: Apache-2.0
"""The database policy belongs to the workload, never to the agent — T018a.

Backwards, this is serious: database access inside a definition's ceiling would let a
model-chosen tool call reach the checkpoint store, which is the run's own record of
what it has done. An agent able to rewrite that could erase the evidence of a step it
took.
"""

from __future__ import annotations

import inspect

from tests.harness import DEFAULT_AGENT_DEFINITION_ID, fake_identity_fabric, frozen_clock

from core.authority.manufacture import manufacture_authority
from core.authority.types import AuthorityScope, TaskCredentialRef
from core.durability import credentials as credentials_module


def test_task_credential_cannot_carry_a_database_login() -> None:
    """Structural: per-step authority has no field a database credential fits in."""
    fields = set(TaskCredentialRef.model_fields)
    assert not fields & {"username", "password", "dsn", "connection", "lease_id"}


def test_manufactured_authority_yields_no_database_reach() -> None:
    clock = frozen_clock()
    result = manufacture_authority(
        subject_user_id="user-1",
        requested_scope=AuthorityScope(tool_names=frozenset({"read_tool"})),
        identity_fabric=fake_identity_fabric(tool_names={"read_tool"}),
        clock=clock,
        agent_definition_id=DEFAULT_AGENT_DEFINITION_ID,
    )
    dumped = str(result.credential.public_dict())
    for term in ("database", "postgres", "psycopg", "dsn"):
        assert term not in dumped.lower()


def test_credential_module_never_consults_agent_authority() -> None:
    """The exchange is keyed on workload identity alone.

    If this module ever imported task authority, the two credential paths — agent to
    tools, harness to its store — would have crossed, and the separation the whole
    design rests on would be a convention rather than a fact.
    """
    source = inspect.getsource(credentials_module)
    for forbidden in ("TaskCredentialRef", "AuthorityScope", "manufacture_authority"):
        assert forbidden not in source


def test_credential_module_accepts_no_static_dsn() -> None:
    """FR-017a: there is no path that takes a password from configuration."""
    source = inspect.getsource(credentials_module)
    for forbidden in ("PGPASSWORD", "DATABASE_URL", "dsn="):
        assert forbidden not in source
