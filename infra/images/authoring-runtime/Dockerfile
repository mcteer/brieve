# SPDX-License-Identifier: Apache-2.0
#
# Derived task image for authoring-tier (041 / ADR-0066, 047 / ADR-0047).
#
# The base `uv:python3.12-bookworm-slim` image has neither `git`, `gh`, nor `terraform`.
# Tasks verify their binaries at start and fail `tooling_missing` rather than installing
# at runtime — a runtime apt-get inside a tier that handles untrusted repository content
# is an unpinned network fetch the static-allowlist posture refuses. Pinning happens HERE.
#
# Analyzer and proposer share this image so Nomad does not need two local tags. The
# analyzer never invokes git/gh; it does invoke Terraform as the final plan oracle.

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ARG TARGETARCH
# Pinned release of GitHub CLI (linux_${TARGETARCH}). Bump deliberately; do not float.
ARG GH_VERSION=2.97.0
# Same Terraform the named-runner SC-006 lane uses. Bump deliberately; do not float.
ARG TERRAFORM_VERSION=1.15.8

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends ca-certificates curl git unzip; \
    arch="${TARGETARCH}"; \
    case "$arch" in \
      amd64) gh_arch=amd64; tf_arch=amd64 ;; \
      arm64) gh_arch=arm64; tf_arch=arm64 ;; \
      *) echo "unsupported TARGETARCH=$arch" >&2; exit 1 ;; \
    esac; \
    curl -fsSL \
      "https://github.com/cli/cli/releases/download/v${GH_VERSION}/gh_${GH_VERSION}_linux_${gh_arch}.tar.gz" \
      -o /tmp/gh.tgz; \
    tar -xzf /tmp/gh.tgz -C /tmp; \
    install -m 0755 "/tmp/gh_${GH_VERSION}_linux_${gh_arch}/bin/gh" /usr/local/bin/gh; \
    curl -fsSL \
      "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_${tf_arch}.zip" \
      -o /tmp/terraform.zip; \
    unzip -q /tmp/terraform.zip -d /tmp; \
    install -m 0755 /tmp/terraform /usr/local/bin/terraform; \
    rm -rf /tmp/gh.tgz "/tmp/gh_${GH_VERSION}_linux_${gh_arch}" /tmp/terraform.zip /tmp/terraform \
      /var/lib/apt/lists/*; \
    git --version; \
    gh --version; \
    terraform version
