# SPDX-License-Identifier: Apache-2.0
"""Contracted harness helpers import from tests.harness."""

from __future__ import annotations


def test_harness_exports() -> None:
    from tests.harness import (
        assert_audit_chain,
        assert_correlated,
        assert_denied_closed,
        assert_no_secret_values,
        assert_no_side_effect,
        assert_scope_narrowed,
        fake_identity_fabric,
        fake_product_api,
        frozen_clock,
    )

    assert callable(assert_denied_closed)
    assert callable(assert_correlated)
    assert callable(assert_audit_chain)
    assert callable(assert_no_secret_values)
    assert callable(assert_no_side_effect)
    assert callable(assert_scope_narrowed)
    assert callable(fake_identity_fabric)
    assert callable(fake_product_api)
    assert callable(frozen_clock)
