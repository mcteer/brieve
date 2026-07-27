# SPDX-License-Identifier: Apache-2.0
"""Run dispatch seam. Beside the transports, not inside one — the CLI and portal need
the same seam, and putting it under `api/` would make the second transport import the
first.
"""
