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

After `git pull`, run `up` again — a stack that has been running for days still has
yesterday’s Vault role bindings. Build that dies immediately with
`task scope exceeds user or ceiling` is that gap, not a missing model key.
`up` also recreates the development sign-in helper; **Sign out** and **Sign in**
again. “Could not be reached” on the build list after `up` is that dead session,
not lost runs.

Do not start `brieve-demo` as a local application from this repository. Build still
needs a GitHub repository (often `brieve-demo`) with the Brieve GitHub App installed —
see [Test Build all the way to a pull request](../../docs/development/local-stack.md#test-build-all-the-way-to-a-pull-request).
`ASK_MODEL` drives Ask and, on the laptop, Build’s write cell (`laptop.auto.tfvars`,
gitignored; CI stays on the fixture). After `up`, `seed-laptop-operator` writes the
vendor key and GitHub App key into Vault when those `.env` lines are present.
