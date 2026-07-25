# SPDX-License-Identifier: Apache-2.0
"""Public test harness — fakes and governance assertion helpers (semver seam)."""

from tests.harness.assertions import (
    assert_audit_chain,
    assert_correlated,
    assert_denied_closed,
    assert_hook_order,
    assert_no_secret_values,
    assert_no_side_effect,
    assert_scope_narrowed,
)
from tests.harness.capture_audit import capture_audit
from tests.harness.fake_identity_fabric import (
    DEFAULT_AGENT_DEFINITION_ID,
    fake_identity_fabric,
)
from tests.harness.fake_product_api import fake_product_api
from tests.harness.frozen_clock import frozen_clock
from tests.harness.scripted_agent import scripted_agent
from tests.harness.secrets import (
    AUTHORITY_SECRET_MARKER,
    BROKERED_GRAIN_MARKER,
    SECRET_MARKER,
    SECRET_MARKERS,
)

__all__ = [
    "AUTHORITY_SECRET_MARKER",
    "BROKERED_GRAIN_MARKER",
    "DEFAULT_AGENT_DEFINITION_ID",
    "SECRET_MARKER",
    "SECRET_MARKERS",
    "assert_audit_chain",
    "assert_correlated",
    "assert_denied_closed",
    "assert_hook_order",  # SC-006
    "assert_no_secret_values",
    "assert_no_side_effect",
    "assert_scope_narrowed",
    "capture_audit",
    "fake_identity_fabric",
    "fake_product_api",
    "frozen_clock",
    "scripted_agent",
]
