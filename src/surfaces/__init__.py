# SPDX-License-Identifier: Apache-2.0
"""Northbound surfaces / transports (sealed).

ADR-0033 names exactly four — MCP, API, CLI, portal — over one authorization core. The API
lands first because the other three consume it: a transport reaching the authorization core
directly would be a second authorization path wearing a different name, and the parity
guarantee would then compare things that do not share an implementation.
"""

__all__: list[str] = []
