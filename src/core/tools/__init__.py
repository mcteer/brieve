# SPDX-License-Identifier: Apache-2.0
"""Public tool invocation entry (sole path to tool bodies)."""

from core.tools.invoke import InvokeResult, invoke_tool

__all__ = ["InvokeResult", "invoke_tool"]
