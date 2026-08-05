# SPDX-License-Identifier: Apache-2.0
"""Northbound surfaces / transports (sealed).

Exactly three — MCP, API, portal — over one authorization core. ADR-0033 enumerated a fourth,
a CLI, which was never built; ADR-0060 withdrew it rather than leave this package describing a
surface that is not coming. Adding a fourth requires an ADR: three is a ceiling, not a floor.

The API lands first because the other two consume it: a transport reaching the authorization
core directly would be a second authorization path wearing a different name, and the parity
guarantee would then compare things that do not share an implementation.
"""

__all__: list[str] = []
