#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Fail if any specs/** file under review still contains unresolved clarification markers.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

if [[ $# -gt 0 ]]; then
  files=("$@")
else
  files=()
  while IFS= read -r line; do
    files+=("${line}")
  done < <(find specs -type f -name 'spec.md' 2>/dev/null || true)
fi

if [[ ${#files[@]} -eq 0 ]]; then
  echo "check-specs: no spec files to check"
  exit 0
fi

status=0
for f in "${files[@]}"; do
  if [[ ! -f "${f}" ]]; then
    continue
  fi
  if grep -nF '[NEEDS CLARIFICATION' "${f}"; then
    echo "check-specs: unresolved clarification markers in ${f}" >&2
    status=1
  fi
  dir="$(dirname "${f}")"
  if [[ ! -f "${dir}/spec.md" ]]; then
    echo "check-specs: missing spec.md in ${dir}" >&2
    status=1
  fi
done

exit "${status}"
