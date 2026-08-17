# SPDX-License-Identifier: Apache-2.0
#
# Derived task image for authoring-tier (041 / ADR-0066).
#
# The base `uv:python3.12-bookworm-slim` image has neither `git` nor `gh`. The proposer
# verifies both at start and fails `tooling_missing` rather than installing at runtime —
# a runtime apt-get inside a tier that handles untrusted repository content is an unpinned
# network fetch the static-allowlist posture refuses. Pinning happens HERE, at image build.
#
# Analyzer and proposer share this image so Nomad does not need two local tags; analyzer
# simply never invokes the CLIs.

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ARG TARGETARCH
# Pinned release of GitHub CLI (linux_${TARGETARCH}). Bump deliberately; do not float.
ARG GH_VERSION=2.97.0

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends ca-certificates curl git; \
    arch="${TARGETARCH}"; \
    case "$arch" in \
      amd64) gh_arch=amd64 ;; \
      arm64) gh_arch=arm64 ;; \
      *) echo "unsupported TARGETARCH=$arch" >&2; exit 1 ;; \
    esac; \
    curl -fsSL \
      "https://github.com/cli/cli/releases/download/v${GH_VERSION}/gh_${GH_VERSION}_linux_${gh_arch}.tar.gz" \
      -o /tmp/gh.tgz; \
    tar -xzf /tmp/gh.tgz -C /tmp; \
    install -m 0755 "/tmp/gh_${GH_VERSION}_linux_${gh_arch}/bin/gh" /usr/local/bin/gh; \
    rm -rf /tmp/gh.tgz "/tmp/gh_${GH_VERSION}_linux_${gh_arch}" /var/lib/apt/lists/*; \
    git --version; \
    gh --version
