# SPDX-License-Identifier: Apache-2.0
"""Public test harness — fakes and governance assertion helpers (semver seam)."""

from tests.harness.assertions import (
    assert_audit_chain,
    assert_correlated,
    assert_denied_closed,
    assert_hook_order,
    assert_no_secret_values,
    assert_no_side_effect,
)
from tests.harness.capture_audit import capture_audit
from tests.harness.scripted_agent import scripted_agent
from tests.harness.secrets import SECRET_MARKER, SECRET_MARKERS

__all__ = [
    "SECRET_MARKER",
    "SECRET_MARKERS",
    "assert_audit_chain",
    "assert_correlated",
    "assert_denied_closed",
    "assert_hook_order",  # SC-006
    "assert_no_secret_values",
    "assert_no_side_effect",
    "capture_audit",
    "scripted_agent",
]
