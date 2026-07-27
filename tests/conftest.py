# SPDX-License-Identifier: Apache-2.0
"""Shared pytest fixtures."""

from __future__ import annotations

import os

import pytest

from core.identity.tenant import DEFAULT_TENANT_ENV

# Every audit entry carries a tenant, and these suites have no identity provider to draw a
# claim from — the same position the primary adapter is in. Set here rather than defaulted
# in core, because `resolve_tenant` refusing when nothing is configured is the behaviour
# under test elsewhere (tests/unit/test_tenant_resolution.py).
os.environ.setdefault(DEFAULT_TENANT_ENV, "tenant-test")
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

_EXPORTER = InMemorySpanExporter()
_PROVIDER = TracerProvider()
_PROVIDER.add_span_processor(SimpleSpanProcessor(_EXPORTER))
trace.set_tracer_provider(_PROVIDER)


@pytest.fixture
def span_exporter() -> InMemorySpanExporter:
    _EXPORTER.clear()
    return _EXPORTER
