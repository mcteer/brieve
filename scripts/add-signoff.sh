#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
#
# Add the DCO `Signed-off-by` trailer the CI gate requires (`.github/workflows/ci.yml`,
# step "DCO sign-off").
#
# **Why a hook rather than remembering `git commit -s`.** Six pull requests merged red on
# 2026-08-27 because the trailer was dropped partway through a session and nobody looked at
# CI. `-s` is a habit, and a habit is exactly what a long session loses. This is the same
# reasoning the repository applies to its gate rows: a rule somebody has to remember is not
# enforcement.
#
# **Idempotent by construction.** `--if-exists doNothing` means re-running on an amended or
# rebased message adds nothing, so a commit never collects two trailers.
#
# **The identity comes from git, not from this script.** `dco-check` requires the trailer to
# match the commit author, so deriving it any other way would produce a trailer that looks
# right and fails the gate.
set -euo pipefail

MESSAGE_FILE="${1:?usage: add-signoff.sh <commit-message-file>}"

# `git var` yields "Name <email> <timestamp> <tz>"; the trailer wants only the identity.
IDENT="$(git var GIT_AUTHOR_IDENT | sed 's/ [0-9]\{1,\} [-+][0-9]\{4\}$//')"

git interpret-trailers \
  --if-exists doNothing \
  --trailer "Signed-off-by: ${IDENT}" \
  --in-place "${MESSAGE_FILE}"
