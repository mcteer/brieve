# SPDX-License-Identifier: Apache-2.0
"""Identity flows (sealed core, Principle V).

Who the caller is, which tenant they belong to, and what roles their claims map to.
Core defines these; each transport produces them. A type this central defined inside the
first transport would make the second import it or duplicate it.
"""
