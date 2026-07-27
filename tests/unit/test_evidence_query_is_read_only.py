# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — the read seam exposes no way to write (FR-009, defence #1).

Asserted by inspecting the protocol and the implementation rather than by trusting the
docstring. This is the defence a refactor removes silently; the database grant is the one
that holds regardless, and it is tested against a real Postgres in the enclave lane.
"""

from __future__ import annotations

import ast
import inspect

from core.audit.postgres_query import PostgresEvidenceQuery
from core.audit.query import EvidenceQuery

WRITE_NAMES = {
    "append",
    "append_event",
    "insert",
    "write",
    "update",
    "delete",
    "remove",
    "migrate",
    "execute",
}


def _public_callables(obj: type) -> set[str]:
    return {name for name, member in inspect.getmembers(obj, callable) if not name.startswith("_")}


def test_protocol_names_no_write_method() -> None:
    """Not 'append raises' — no append. There is nothing to call."""
    assert _public_callables(EvidenceQuery) & WRITE_NAMES == set()


def test_implementation_names_no_write_method() -> None:
    assert _public_callables(PostgresEvidenceQuery) & WRITE_NAMES == set()


def test_read_path_cannot_reach_the_sink() -> None:
    """The import graph enforces the separation, not a convention about being careful.

    Asserted against the module's parsed imports, **not** its text. The first version of
    this check searched the source for "postgres_sink" and failed on the docstring
    explaining why the separation exists — prose about the sink is not an import of it.
    That is the same mistake this repository has now made in 006's boundary checker and
    007's run-reference check, so it is worth the extra six lines to do properly.
    """
    module = inspect.getmodule(PostgresEvidenceQuery)
    assert module is not None
    tree = ast.parse(inspect.getsource(module))

    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.add(node.module)
            imported.update(alias.name for alias in node.names)

    assert not any("postgres_sink" in name for name in imported)
    assert "PostgresAuditSink" not in imported


def test_request_has_no_widening_parameter() -> None:
    """Every caller-supplied field narrows; the tenant comes from the subject.

    A tenant parameter reachable from a request body is what would make FR-011's
    cross-tenant case a permission check that could be written wrong, instead of a
    parameter that does not exist.
    """
    from core.audit.query import EvidenceQueryRequest

    fields = set(EvidenceQueryRequest.model_fields)
    assert fields == {
        "tenant_id",
        "correlation_id",
        "run_id",
        "start_time",
        "end_time",
        "event_types",
        "limit",
    }
