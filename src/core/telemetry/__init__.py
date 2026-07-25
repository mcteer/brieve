# SPDX-License-Identifier: Apache-2.0
"""OTel-only telemetry emission (ADR-0020)."""

from core.telemetry.spans import emit_hook_decision_span

__all__ = ["emit_hook_decision_span"]
