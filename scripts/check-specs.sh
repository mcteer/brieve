#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Spec-artifact lint (FR-006):
# - Resolve affected feature directories under specs/<nnn-name>/
# - Require each to contain spec.md
# - Fail only on unresolved Spec Kit markers in spec.md: [NEEDS CLARIFICATION: ...]
#   (prose mentions of the marker string in checklists/tasks/research are ignored)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

inputs=()
if [[ $# -gt 0 ]]; then
  inputs=("$@")
else
  while IFS= read -r line; do
    [[ -n "${line}" ]] && inputs+=("${line}")
  done < <(find specs -type f -name 'spec.md' 2>/dev/null || true)
fi

if [[ ${#inputs[@]} -eq 0 ]]; then
  echo "check-specs: no inputs; nothing to check"
  exit 0
fi

# Collect unique feature directories (specs/<nnn-name>/) from inputs
feat_list=""
for path in "${inputs[@]}"; do
  case "${path}" in
    specs/*/*|specs/*)
      feat="specs/$(printf '%s' "${path}" | cut -d/ -f2)"
      if [[ -n "${feat#specs/}" && "${feat}" != "specs/" ]]; then
        case " ${feat_list} " in
          *" ${feat} "*) ;;
          *) feat_list="${feat_list} ${feat}" ;;
        esac
      fi
      ;;
  esac
done

feat_list="${feat_list# }"
if [[ -z "${feat_list}" ]]; then
  echo "check-specs: no feature directories resolved from inputs; nothing to check"
  exit 0
fi

status=0
for feat in ${feat_list}; do
  spec="${feat}/spec.md"
  if [[ ! -f "${spec}" ]]; then
    echo "check-specs: missing ${spec}" >&2
    status=1
    continue
  fi
  # Real Spec Kit markers use a colon after CLARIFICATION
  if grep -nE '\[NEEDS CLARIFICATION:' "${spec}"; then
    echo "check-specs: unresolved clarification markers in ${spec}" >&2
    status=1
  else
    echo "check-specs: ok ${spec}"
  fi
done

exit "${status}"
