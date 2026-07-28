# SPDX-License-Identifier: Apache-2.0
"""The machine-readable operation description (FR-012).

Generated from the implementation rather than maintained beside it — FastAPI derives the
OpenAPI document from the same signatures and Pydantic models that validate requests, so
there is one thing to maintain and it cannot drift from the surface.

**Generation alone does not satisfy SC-010.** Every route appears automatically, so a new
operation would simply show up, silently. Detection has to be against a recorded baseline:
`operation_summary` produces a stable, diffable digest of the operation set, and a
committed snapshot is compared against it. Adding an operation without updating the
snapshot then fails, which makes the addition a visible diff in review.

That snapshot is also what makes the parity row *satisfiable* when a second transport
lands — it compares against something recorded rather than against whatever this surface
happens to do by then. It is not parity itself, and this feature does not claim it.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI

from surfaces.api.app import registered_routes

#: Framework-provided documentation endpoints. Excluded because they describe the surface
#: rather than being part of it, and a second transport has no equivalent to compare.
_FRAMEWORK_PATHS = {"/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"}


def operation_summary(app: FastAPI) -> list[dict[str, Any]]:
    """A stable, diffable list of the operations this surface exposes."""
    operations = []
    for route in registered_routes(app):
        if route["path"] in _FRAMEWORK_PATHS:
            continue
        for method in route["methods"]:
            operations.append({"method": method, "path": route["path"], "name": route["name"]})
    return sorted(operations, key=lambda o: (o["path"], o["method"]))


def operation_snapshot(app: FastAPI) -> str:
    """The committed form. Sorted and indented so a diff reads as one added line."""
    return json.dumps(operation_summary(app), indent=2, sort_keys=True) + "\n"


__all__ = ["operation_snapshot", "operation_summary"]
