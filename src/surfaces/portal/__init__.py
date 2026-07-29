# SPDX-License-Identifier: Apache-2.0
"""The conversational portal (ADR-0034): a thin client of the northbound API.

Nothing in this package makes an authorization decision or holds a credential. `relay.py`
is the only module with an HTTP client, which is what makes the containment claim
checkable by reading rather than by auditing.
"""
