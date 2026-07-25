# Test harness (`tests/harness`)

**Reserved.** This package will hold shared fakes and governance assertion helpers
(`stub_model`, `scripted_agent`, `assert_denied_closed`, and related utilities).

Until helpers land here, treat the directory as a layout reservation only — no
product behavior.

When populated, the harness helpers are **public API under the semver seam
promise** (see `docs/development/testing.md`). Breaking changes require a
deprecation window consistent with other versioned seams.
