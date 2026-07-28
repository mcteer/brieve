# SPDX-License-Identifier: Apache-2.0
"""Dependency health — what the platform believes about the products agents operate.

A platform mechanism rather than a surface one, and the placement is deliberate: the
refusal is consulted by every run regardless of which transport started it. Under
`src/surfaces/mcp/` a run started through some later transport would ignore a dependency
the platform knows is down, which is the same mistake as putting authorization in a
transport.

The MCP service *hosts* the checker, because it is the thing that runs continuously. It
does not own the decision.
"""
