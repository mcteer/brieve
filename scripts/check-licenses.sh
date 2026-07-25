#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ALLOWLIST="${ROOT}/licenses/allowlist.txt"

ALLOW_JOINED="$(
  grep -vE '^\s*(#|$)' "${ALLOWLIST}" | paste -sd ';' -
)"

uv run pip-licenses --from=mixed --format=plain --allow-only="${ALLOW_JOINED}"
