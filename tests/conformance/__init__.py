# SPDX-License-Identifier: Apache-2.0
"""Conformance suite — merge-blocking gates for adapters and providers.

Run with ``make conformance``, not ``make check``: the inner loop is unit +
component, and this lane is invoked separately so a gate failure is
distinguishable from a unit regression.
"""
