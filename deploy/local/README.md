<!-- SPDX-License-Identifier: Apache-2.0 -->
# Local stack

The one-command bring-up for a laptop (OrbStack or Docker Desktop):

```bash
bash deploy/local/stack.sh up
```

Human guide, including tools, `.env`, and how to open the portal:

**[Run Brieve on your computer](../../docs/development/local-stack.md)**

```bash
bash deploy/local/stack.sh down     # stop, keep data
bash deploy/local/stack.sh reset    # destroy local Vault/Postgres state
bash deploy/local/stack.sh status
```

Do not start `brieve-demo` as a local application from this repository. Build still
needs a GitHub repository (often `brieve-demo`) with the Brieve GitHub App installed —
see [Test Build all the way to a pull request](../../docs/development/local-stack.md#test-build-all-the-way-to-a-pull-request).
