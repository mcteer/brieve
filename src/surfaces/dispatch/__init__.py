# SPDX-License-Identifier: Apache-2.0
"""Run dispatch seam. Beside the transports, not inside one — MCP and the portal need the
same seam, and putting it under `api/` would make the second transport import the first.

Written when a CLI was still enumerated (ADR-0033) and it was named here as one of the
callers; ADR-0060 withdrew that transport. The seam's reason for existing is unchanged —
more than one transport dispatches runs, so the seam cannot live inside any of them.
"""
