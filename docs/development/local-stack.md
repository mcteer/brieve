<!-- SPDX-License-Identifier: Apache-2.0 -->
# Run Brieve on your computer

This is the guide for standing up a **local Brieve stack**: the website (the portal),
the sign-in helper, and the platform behind them. When you finish, you can open Brieve
in a browser on your machine, sign in, **Ask**, and **Build** through to a GitHub
pull request — if you set the model and GitHub App lines below. Bring-up itself
does not need those; without them Ask and Build refuse honestly instead of
pretending to work.

You do **not** run a demo application on your laptop. `stack.sh` starts Brieve
only. Do not look for a second compose project or a command that starts `brieve-demo`
as a local app.

**Build’s finished result is a GitHub pull request** on some other repository —
the application you want changed. That repository must already exist on GitHub, and
the **Brieve GitHub App** must be installed on it. The usual subject is `brieve-demo`
(a sample app repo). You present its GitHub URL in the portal; you still do not
start it as a program on your machine.
See [Test Build all the way to a pull request](#test-build-all-the-way-to-a-pull-request).

You will need a **Vault Enterprise licence** from your team. Bring-up cannot start
without it. Treat that licence like a password: never put it in email, chat, tickets,
or git.

First-time bring-up usually takes **10–20 minutes**, mostly downloading container
images. Later starts are faster.

---

## What you will have

| You open this | What it is |
| --- | --- |
| https://127.0.0.1:8082/ | The Brieve portal (the website) |
| http://127.0.0.1:8090 | Development sign-in (used automatically; you rarely visit it) |
| http://127.0.0.1:8083/mcp | MCP connection URL for an editor, if you want one later |
| http://127.0.0.1:4646/ui/ | Nomad, the job scheduler — useful if something will not start |

`127.0.0.1` means “this computer.” Other people on the internet cannot reach these
addresses.

---

## What you need beforehand

Tick these off before you type any commands:

- [ ] A Mac or a Linux computer. Windows is via WSL2, which is a larger setup; prefer
      Mac or Linux if you can.
- [ ] Administrator permission to install apps.
- [ ] [OrbStack](https://orbstack.dev) on a Mac (or Docker Desktop). Open it once and
      leave it running. The menu icon should show Docker as running.
- [ ] A Vault Enterprise licence string from whoever handles HashiCorp licensing on
      your team.
- [ ] A terminal app (on a Mac: **Terminal** or **iTerm**). You will paste commands
      there, one block at a time, and press Return.

For a **full** laptop (Ask answers, Build opens a pull request), also:

- [ ] An Anthropic API key in `.env` as `ANTHROPIC_API_KEY`, plus
      `ASK_MODEL=anthropic/claude-sonnet@5` and
      `RELEVANCE_MODEL=anthropic/claude-opus@5` (the judge must not be the writer).
- [ ] A GitHub repository with the Brieve GitHub App installed (often `brieve-demo`).
- [ ] `AUTHORING_APP_ID`, `AUTHORING_INSTALLATION_ID`,
      `PROPOSE_OWNED_REPOSITORIES=owner/repo`, and `AUTHORING_APP_KEY_FILE` pointing at
      the App’s `.pem` **on disk** (never paste the key into `.env` or chat).

`stack.sh up` writes the model key and App key into Vault after the enclave is up.
Without those lines, bring-up still succeeds; Ask/Build then refuse instead of
calling a vendor or opening a PR.

---

## 1. Install the command-line tools

These are small programs the start script looks for by name. If a command says
`command not found`, that tool is missing.

### Git and uv

**macOS with Homebrew** (if `brew` works in your terminal):

```bash
brew install git uv python@3.12
```

**Without Homebrew**, install [uv](https://docs.astral.sh/uv/getting-started/installation/)
from Astral’s instructions, and confirm you have Git (Xcode Command Line Tools on a Mac:
`xcode-select --install`).

Check:

```bash
git --version
uv --version
python3 --version
```

Python must be **3.12 or newer**.

### Nomad, Vault, and Terraform

Brieve uses HashiCorp’s own installers, not Homebrew, so versions stay pinned. These
versions are known to work on an Apple Silicon Mac. Put the files in `~/.local/bin`
and put that folder on your PATH.

Paste this **once**. It creates the folder, downloads three programs, checks their
checksums, and installs them:

```bash
mkdir -p "$HOME/.local/bin"
export PATH="$HOME/.local/bin:$PATH"

# Terraform
VER=1.15.8
cd /tmp
curl -fsSLO "https://releases.hashicorp.com/terraform/${VER}/terraform_${VER}_darwin_arm64.zip"
curl -fsSLO "https://releases.hashicorp.com/terraform/${VER}/terraform_${VER}_SHA256SUMS"
shasum -a 256 -c --ignore-missing "terraform_${VER}_SHA256SUMS"
unzip -o "terraform_${VER}_darwin_arm64.zip" -d "$HOME/.local/bin"
chmod +x "$HOME/.local/bin/terraform"

# Nomad
VER=2.0.4
curl -fsSLO "https://releases.hashicorp.com/nomad/${VER}/nomad_${VER}_darwin_arm64.zip"
curl -fsSLO "https://releases.hashicorp.com/nomad/${VER}/nomad_${VER}_SHA256SUMS"
shasum -a 256 -c --ignore-missing "nomad_${VER}_SHA256SUMS"
unzip -o "nomad_${VER}_darwin_arm64.zip" -d "$HOME/.local/bin"
chmod +x "$HOME/.local/bin/nomad"

# Vault CLI — the *server* is an Enterprise container the stack starts for you.
# An ordinary Vault CLI is enough to unseal it. This version is current on the
# HashiCorp releases site; pick another 1.20.x if you already have one.
VER=1.20.4
curl -fsSLO "https://releases.hashicorp.com/vault/${VER}/vault_${VER}_darwin_arm64.zip"
curl -fsSLO "https://releases.hashicorp.com/vault/${VER}/vault_${VER}_SHA256SUMS"
shasum -a 256 -c --ignore-missing "vault_${VER}_SHA256SUMS"
unzip -o "vault_${VER}_darwin_arm64.zip" -d "$HOME/.local/bin"
chmod +x "$HOME/.local/bin/vault"
```

Intel Mac: replace `darwin_arm64` with `darwin_amd64`. Linux: use `linux_amd64` or
`linux_arm64`. Always run the `shasum` line so you do not install a corrupt download.

Make PATH survive a new terminal window (zsh, the Mac default):

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.zprofile"
export PATH="$HOME/.local/bin:$PATH"
```

Check:

```bash
nomad version
vault version
terraform version
docker info
```

`docker info` must succeed. If it cannot talk to Docker, open OrbStack and wait until
it is fully started, then try again.

---

## 2. Get the code

```bash
git clone https://github.com/mcteer/brieve.git
cd brieve
```

Stay in this folder for every later command. `ls` should show `Makefile`, `deploy`,
and `src`.

---

## 3. Create your secrets file

The stack reads a file named `.env` in the **repository root** (the `brieve` folder).
That file is gitignored. Never commit it.

Create it in a text editor, or from the terminal:

```bash
cat > .env <<'EOF'
VAULT_ENT_LICENSE="PASTE_YOUR_LICENCE_HERE"
HARNESS_DEFAULT_TENANT=tenant-local
EOF
```

Then open `.env` and replace `PASTE_YOUR_LICENCE_HERE` with the real licence. Keep the
quotes around it. Do not add spaces around the `=`.

`HARNESS_DEFAULT_TENANT=tenant-local` is required. The platform files every record under
a tenant name; it will not invent one.

You do **not** copy Vault unseal keys or root tokens into this file yourself. The first
successful start writes those for you.

---

## 4. Start the stack

One command. It starts the enclave (Vault, Nomad, Postgres), the development sign-in
service, the API, the MCP surface, and the portal.

```bash
cd /path/to/brieve
bash deploy/local/stack.sh up
```

Leave the window alone until it prints `stack up` and a list of URLs. The first run
installs Python packages and builds a couple of container images; that is expected.
Do not start a local `brieve-demo` application from this repository — Brieve is what
you just started. You will only need the **GitHub** copy of a subject repo later, if
you test Build.

If it stops with `missing prerequisite:`, read the line. It names the missing tool or
file. Fix that one thing and run the same command again. Re-running is safe.

When it succeeds you should see, among other lines:

```text
stack up (compose project: brieve-local):
  portal         https://127.0.0.1:8082/
  MCP surface    http://127.0.0.1:8083/mcp
```

You can close the terminal after that. The scheduler keeps running in the
background.

---

## 5. Check that it worked

```bash
bash deploy/local/stack.sh status
```

You want Nomad, Vault (unsealed), and Postgres **up**, and `health portal` / `health
dev-idp` / `health mcp-surface` not `UNREACHABLE`.

If the website loads but Nomad is **down**, do not treat that as success. Leftover
containers can still answer for a while after the scheduler has quit.

A shorter glance:

```bash
make dev-status
```

---

## 6. Open the portal

1. In your browser, go to **https://127.0.0.1:8082/**
2. The site uses a certificate your computer did not buy from a public issuer. The
   browser will warn that the connection is not trusted. That is expected on a laptop
   stack.
   - Chrome / Edge: **Advanced** → proceed to `127.0.0.1`.
   - Safari: **Show Details** → visit this website.
3. Click **Sign in**. The development sign-in helper does **not** check a password. It
   exists so you can use the portal without connecting a company identity provider. You
   should land on Build or Ask.
4. Use the left-hand icons to switch **Build** and **Ask**.

If sign-in returns immediately to a “signed out” page, the stack is probably still
settling. Wait a minute, run `bash deploy/local/stack.sh status`, then try again.

---

## 7. Stop, start again, or wipe

| Goal | Command |
| --- | --- |
| Stop everything, **keep** your data | `bash deploy/local/stack.sh down` |
| Start again later | `bash deploy/local/stack.sh up` |
| After `git pull` (new role bindings, jobspecs, or portal code) | `bash deploy/local/stack.sh up` again. A stack that has been running for days is still yesterday’s configuration. |
| Destroy the local stack and start from empty | `bash deploy/local/stack.sh reset` |

After **reset**, delete these lines from `.env` if they are present, or the next start
will try to unseal a store that no longer exists:

- `VAULT_UNSEAL_KEY`
- `VAULT_ROOT_TOKEN`
- `VAULT_ADDR`
- `VAULT_CACERT`

Leave `VAULT_ENT_LICENSE` and `HARNESS_DEFAULT_TENANT` in place.

Do not run `reset` unless you mean to throw the local Vault and database away.

`stack.sh up` is safe to run while the stack is already up. That is how a laptop picks
up new role bindings and jobspecs after `git pull`. Leaving it running is not the same
as being current.

`up` often recreates the development sign-in helper. That process mints a new signing
key, so a browser tab that was already signed in is no longer verifiable. The portal
is up; the list of builds is hidden because **you need to Sign in again**, not because
the builds were lost. Use **Sign out** if the page still looks signed in, then
**Sign in**.

---

## If something goes wrong

| What you see | What to do |
| --- | --- |
| `Docker is not running` | Open OrbStack (or Docker Desktop) and wait until it is running. |
| `VAULT_ENT_LICENSE is absent` | The `.env` file is missing, in the wrong folder, or the licence line is misspelled. |
| `HARNESS_DEFAULT_TENANT is not set` | Add `HARNESS_DEFAULT_TENANT=tenant-local` to `.env`. |
| `unseal failed` / sealed Vault after a wipe | You still have old `VAULT_UNSEAL_KEY` / `VAULT_ROOT_TOKEN` lines. Remove them (see above) and run `stack.sh up` again. |
| `something is already listening on :5432` | Another local database is using Postgres’s port. Stop that other stack, then retry. |
| Portal still loads, but `stack.sh status` says Nomad **down** | The website container is leftover after the scheduler process quit. Stop leftovers (`docker ps` — names like `server-…`, `postgres-…`, `brieve-dev-vault`), then run `bash deploy/local/stack.sh up` again. Do not delete other apps’ containers. |
| Browser warning on https://127.0.0.1:8082/ | Expected. Proceed to the site as in step 6. |
| Ask refuses before answering | Bring-up succeeded. Ask needs `ASK_MODEL` / `ANTHROPIC_API_KEY` in `.env` (next section). Then run `stack.sh up` again so Vault gets the key. |
| Build fails immediately (`task scope exceeds user or ceiling`) | The running Vault still has the old operator role (no authoring tools). You pulled newer code but did not re-apply. Run `bash deploy/local/stack.sh up`, then retry. |
| Build starts, then the button becomes **New build** and sits on the left | Expected. An in-flight Build cannot post again. That control is a link back to empty Build, not a second submit. |
| Research fails in seconds: `the model could not name a permitted tool after 3 attempt(s)` | `ASK_MODEL` is unset, so Build is still on the fixture write cell. That fixture names `read_subject` with no path. Set the Ask model lines, run `stack.sh up` again, Sign in, retry. |
| “The platform could not be reached, so this list is not showing your builds” | After `stack.sh up` the sign-in helper often gets a new key. Your previous Sign in is then unverifiable — the platform *did* answer. **Sign out**, then **Sign in**. The builds are still there. |
| Build refuses the repository URL | The `owner/repo` is missing from `PROPOSE_OWNED_REPOSITORIES`, or you started the stack before adding it. Add the line and run `stack.sh up` again. |
| Build runs but Judge fails (reason under the phase table) | Setup worked. The writer’s files did not hang together (duplicates, missing resources, unused variables). Ask for a smaller first slice. `.env` / `.env.example` files are refused on purpose. |
| Build runs, Propose fails, no pull request | The Brieve GitHub App is not installed on that repo, `AUTHORING_APP_KEY_FILE` is missing, or the App key was never seeded into Vault. `stack.sh up` seeds it when those `.env` lines are present. The local demo app being stopped is not the cause. |
| `host.docker.internal does not resolve` | On Linux Docker, add it once: `echo '127.0.0.1 host.docker.internal' \| sudo tee -a /etc/hosts`. OrbStack and Docker Desktop provide this name for you. |

Do not paste licence text, unseal keys, root tokens, or API keys into chat or tickets
when you ask for help. Say which **name** is missing (`VAULT_ENT_LICENSE`, and so on).

---

## Optional: let Ask (and laptop Build) call a model

The stack starts without talking to a vendor. **Ask** then refuses honestly until you set
a model. On the laptop, the same `ASK_MODEL` line is also what Build uses: `stack.sh up`
writes a gitignored Terraform override that binds `authoring-agent`’s **write** cell to
that model. CI does not get that file, so the merge lane stays on the fixture cell.

`RELEVANCE_MODEL` must be a **different** model (Opus if Ask is Sonnet). It judges
relevance for Ask and authored work for Build. A model does not judge its own output.

In `.env` (still never committed):

```bash
ASK_MODEL=anthropic/claude-sonnet@5
RELEVANCE_MODEL=anthropic/claude-opus@5
ANTHROPIC_API_KEY=your-key-here
```

Then run `bash deploy/local/stack.sh up` again. That re-applies the write binding and
puts the vendor key in Vault (`model-credentials/anthropic`). Restarting only the API
job is enough for Ask; Build needs the write-cell apply.

---

## Test Build all the way to a pull request

The portal can open without any of this. **Ask** needs the model lines above.
**Build** that produces a pull request also needs a GitHub App: the agent clones a
real Git repository and pushes a branch. There is no substitute subject on your laptop.

On the laptop, `ASK_MODEL` **does** choose Build’s writer (see the previous section).
The GitHub App is the other half. After you pull new Brieve code, run
`bash deploy/local/stack.sh up` again or Vault still has yesterday’s operator role and
Build dies immediately with `task scope exceeds user or ceiling`.

Think of two different things that share a name:

| | What it is | Do you need it? |
| --- | --- | --- |
| Brieve (this repo, `stack.sh`) | The product you just started | Yes, to use the portal |
| A **subject** GitHub repo (often `brieve-demo`) | The application the agent will change | Yes, to see a pull request |
| `brieve-demo` running as a local app | A second compose stack / database | No. Do not start it |

### 1. Have a GitHub repository the agent may change

You need a repository **on GitHub**, not a folder on disk. Ask your team which one to
use. Here it is usually:

`https://github.com/mcteer/brieve-demo`

Create a fork or a new empty repo only if they tell you to. Note the `owner/repo`
form (`mcteer/brieve-demo`) — that is what Brieve’s allow-list uses.

### 2. Install the Brieve GitHub App on that repository

Open the repository on GitHub → **Settings** → **GitHub Apps** (sometimes under
**Integrations**). You should see **Brieve** (or the App name your team uses for this
estate) listed as installed, with permission to read contents and open pull requests.

If it is not installed, do not invent an App. Ask whoever owns the Brieve GitHub App
to install it on this repository. Until that is done, Build can research and still
end without a pull request.

### 3. Tell your local stack which repos are allowed

Add these lines to the **same** `.env` in the `brieve` folder (never commit this file).
Replace the numbers and `owner/repo` with the values your team gives you. Do not put
the App’s private key in `.env`.

```bash
AUTHORING_APP_ID=<numeric App ID>
AUTHORING_INSTALLATION_ID=<installation id>
PROPOSE_OWNED_REPOSITORIES=mcteer/brieve-demo
AUTHORING_APP_KEY_FILE=/absolute/path/to/the-app.pem
```

`PROPOSE_OWNED_REPOSITORIES` is a comma-separated list of `owner/repo` names. A URL
you paste in the portal that is **not** on this list is refused on purpose.

Then start (or re-start) the stack so the API picks the new settings up:

```bash
bash deploy/local/stack.sh up
```

### 4. The App private key goes in Vault, not in `.env`

The machine that opens the pull request is a container. Your personal `gh auth` login
does not reach it. The App private key lives in Vault only.

`AUTHORING_APP_KEY_FILE` is a **path** to the `.pem` on your computer. `stack.sh up`
copies that file into Vault after the enclave is up (`infra/bin/seed-laptop-operator`).
Do not put the key bytes in `.env`.

If you already brought the stack up before adding those lines, run `up` again. To seed
by hand instead:

```bash
set -a && source .env && set +a
vault kv put -mount=harness-authority authoring/vcs-app \
  app_id="$AUTHORING_APP_ID" \
  installation_id="$AUTHORING_INSTALLATION_ID" \
  private_key=@"$AUTHORING_APP_KEY_FILE"
```

If `vault` asks you to log in, the stack is not up or `.env` is missing
`VAULT_ADDR` / `VAULT_CACERT` from a successful start. Run `stack.sh status` first.

Never paste the licence, unseal key, root token, App private key, or model key into
email, tickets, or chat.

### 5. Run Build in the portal

1. Open **https://127.0.0.1:8082/**, sign in, stay on **Build**.
2. Describe a **small first slice** and include the repository URL, for example:
   `Add an S3 bucket module for https://github.com/mcteer/brieve-demo`
   Write is capped to six files. A whole platform (VPC + ECS + ALB + …) in one
   Build often fails Judge even when the stack is fine. One working piece is the
   intended first pull request.
3. Submit. The **Build** button is replaced by **New build** on the left of the dock.
   That is a link to start a *different* Build, not a renamed submit. The current run
   continues on this page.
4. Wait. A pull request link means publish succeeded. If Judge refuses, the phase
   table shows `failed` and the full reason is **under** the table — that is the
   product working, not a missing App key. Research failing in a few seconds still
   means the fixture writer (no `ASK_MODEL`).

If Build stops without a pull request, read the reason **under** the phase table (not
inside a row). Judge refusing a messy slice is not a missing App key. Propose-stage
failures are usually: the URL is not on `PROPOSE_OWNED_REPOSITORIES`, the App is not
installed on that repo, `AUTHORING_APP_KEY_FILE` was missing so Vault still has the
placeholder, or the stack was not re-applied after a `git pull`. A missing `ASK_MODEL`
fails **Research** in seconds, not at publish.

---

## Optional: connect an editor over MCP

Same stack. In the editor’s MCP config, use only the URL — no token in the file:

```json
{
  "mcpServers": {
    "brieve": { "url": "http://127.0.0.1:8083/mcp" }
  }
}
```

Details: [Connecting a client](connecting-a-client.md).

---

## What this guide is not

- Not a production deployment. This is a laptop enclave: one Vault, one Nomad, a
  development sign-in that authenticates nobody.
- Not a command to run `brieve-demo` as a local application. The GitHub repository of
  that name is the usual **subject** for Build, not a second stack to start.
- Not a substitute for [CONTRIBUTING.md](../../CONTRIBUTING.md) if you are changing
  the product.
