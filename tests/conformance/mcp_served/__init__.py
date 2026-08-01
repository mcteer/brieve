# SPDX-License-Identifier: Apache-2.0
"""Rows driven through the SERVED MCP surface — 019, closing ROADMAP gap 0f.

Distinct from `tests/conformance/mcp/`, which exercises `McpTransport` the class and stays
exactly as it is. Fifty-six rows there are correct and narrower than they read: the class was
constructed nowhere in `src/` and no client could reach it.

**Every row here talks to a running process over a real socket.** That is the one path no unit
test covers and the reason this feature exists — so a row that constructed the transport in a
fixture would assert what the class rows already assert while looking like it asserted more.
`test_no_row_here_constructs_the_transport` forbids it.
"""
