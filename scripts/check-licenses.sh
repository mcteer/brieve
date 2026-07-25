#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# License compliance gate (FR-006 / CONTRIBUTING): inventory with pip-licenses
# against an in-repo allowlist; fail closed on GPL/AGPL/BUSL/SSPL family and on
# any license not on the allowlist.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ALLOWLIST="${LICENSE_ALLOWLIST:-${ROOT}/licenses/allowlist.txt}"

if [[ ! -f "${ALLOWLIST}" ]]; then
  echo "check-licenses: missing allowlist ${ALLOWLIST}" >&2
  exit 1
fi

ALLOW_JOINED="$(
  grep -vE '^\s*(#|$)' "${ALLOWLIST}" | paste -sd ';' -
)"

if [[ -z "${ALLOW_JOINED}" ]]; then
  echo "check-licenses: allowlist is empty after filtering comments" >&2
  exit 1
fi

# Fail if any installed package reports a license outside the allowlist.
uv run pip-licenses --from=mixed --format=plain --allow-only="${ALLOW_JOINED}"

# Explicit second belt: copyleft / source-available families must never appear,
# even if an allowlist entry were mistyped to include them.
DISALLOWED_RE='GPL|AGPL|BUSL|SSPL'
if uv run pip-licenses --from=mixed --format=csv --with-system | \
  tail -n +2 | grep -iE "${DISALLOWED_RE}"; then
  echo "check-licenses: disallowed license family (GPL/AGPL/BUSL/SSPL) present" >&2
  exit 1
fi
