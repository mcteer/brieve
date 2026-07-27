# SPDX-License-Identifier: Apache-2.0
"""Northbound API conformance rows (specs/008-northbound-api/contracts/conformance-api.md).

Rows marked ``enclave`` run against the real Vault and Postgres and **fail loudly when
those are absent rather than skipping**. A test that skips itself reports the same green
as one that ran.
"""
