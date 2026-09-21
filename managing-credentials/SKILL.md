---
name: managing-credentials
description: >-
  Configures and manages credentials locally using Doppler as the developer
  runtime engine, with optional upstream hydration from Bitwarden and Google
  Cloud Secret Manager. Use when installing Doppler, authenticating, setting
  local project scopes, injecting credentials at runtime with doppler run, or
  syncing upstream vaults. Don't use for unencrypted dot-env files.
metadata:
  version: "0.2.0"
---

# Managing Credentials

Use this skill to configure local credential management using **Doppler** as the
primary developer environment and runtime engine, ensuring sensitive tokens
(such as Slack, API keys, or database credentials) remain off disk and out of
git repositories.

---

## 1. Pre-Flight Verification

Verify that the Doppler CLI is installed on the host:

```bash
# macOS (Homebrew)
brew install dopplerhq/cli/doppler

# Linux / Debian / Ubuntu
curl -sLf --retry 3 --tlsv1.2 'https://packages.doppler.com/public/cli/gpg.key' | \
  sudo gpg --dearmor -o /usr/share/keyrings/doppler-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/doppler-archive-keyring.gpg] https://packages.doppler.com/public/cli/deb/debian any-version main" | \
  sudo tee /etc/apt/sources.list.d/doppler.list
sudo apt-get update && sudo apt-get install doppler
```

Log in to authenticate the CLI session:

```bash
doppler login
```

---

## 2. Local Project Setup

Set up a project scope for your agent workspace:

1. **Create the project in Doppler:**

   ```bash
   doppler projects create ai-agents
   ```

2. **Bind the local directory to the project:**

   ```bash
   doppler setup --project ai-agents --config dev
   ```

   This writes a repository-relative `.doppler.yaml` file mapping the directory
   to the chosen project and environment config without saving secrets.

3. **Verify directory configuration:**

   ```bash
   doppler configure get
   ```

---

## 3. Managing Secrets Locally

Set, inspect, or delete credentials directly through the Doppler CLI:

1. **Set a secret:**

   ```bash
   doppler secrets set SLACK_BOT_TOKEN="xoxb-..."
   doppler secrets set SLACK_TEAM_ID="T..."
   ```

2. **List stored secret names (without revealing values):**

   ```bash
   doppler secrets --names
   ```

3. **Retrieve a single secret value (stdout only):**

   ```bash
   doppler secrets get SLACK_BOT_TOKEN --plain
   ```

4. **Delete a secret:**

   ```bash
   doppler secrets delete SLACK_BOT_TOKEN
   ```

---

## 4. Storing and Updating Vault Secrets

Use [`scripts/get_credential.py`](./scripts/get_credential.py) to save or update
credentials in upstream vaults with automatic dot-path updates and zero-disk
plaintext file ingestion:

### A. Saving Structured Secrets and Subfield Updates

```bash
# Save a structured JSON secret into Bitwarden Secrets Manager
python3 scripts/get_credential.py set slack_agents \
  '{"bot_token": "xoxb-...", "team_id": "T..."}' \
  --note "Slack Bot Workspace Token"

# Atomically update a single subfield in existing JSON secret
python3 scripts/get_credential.py set slack_agents.bot_token "xoxb-new..."
```

### B. Ingesting OAuth / Env Files and Auto-Purging

Ingest downloaded client JSON or `.env` files and securely delete the plaintext
file immediately after ingestion:

```bash
# Ingest Google OAuth client JSON into bws and delete plaintext download
python3 scripts/get_credential.py set gws_auth \
  --from-file ~/Downloads/client_secret_*.json \
  --delete-after \
  --note "Google Workspace CLI OAuth Client"
```

---

## 5. Hydrating Doppler from Upstream Vaults

When bootstrapping a new machine or working across environments, hydrate your
local Doppler project directly from your upstream vault using
[`scripts/get_credential.py`](./scripts/get_credential.py):

### Option A: Google Cloud Secret Manager (Enterprise / Work)

Pull corporate credentials into your local Doppler project:

```bash
python3 scripts/get_credential.py sync \
  --upstream gcp \
  --project YOUR_GCP_PROJECT_ID \
  --keys "SLACK_BOT_TOKEN,SLACK_TEAM_ID"
```

### Option B: Bitwarden (Personal Vault / Cross-Device)

Pull credentials from Bitwarden Secrets Manager (`bws`) into Doppler, with
support for structured JSON unpacking and explicit destination mapping:

```bash
# Sync specific subfields with custom Doppler variable names
python3 scripts/get_credential.py sync \
  --upstream bitwarden \
  --keys "SLACK_BOT_TOKEN:slack_agents.bot_token,SLACK_TEAM_ID:slack_agents.team_id"

# Sync Google Workspace OAuth variables
python3 scripts/get_credential.py sync \
  --upstream bitwarden \
  --keys "GOOGLE_WORKSPACE_PROJECT_ID:gws_auth.project_id,GOOGLE_WORKSPACE_CLI_CLIENT_ID:gws_auth.client_id,GOOGLE_WORKSPACE_CLI_CLIENT_SECRET:gws_auth.client_secret"
```

---

## 6. Injecting Credentials at Runtime

Inject secrets directly into process memory at execution time with zero disk
plaintext files:

### Running with Bitwarden In-Memory Injection (Zero SaaS / 100% Local)

Run any agent or script with all project credentials resolved in memory:

```bash
# Automatically resolves and injects ALL project secrets into child process
python3 scripts/get_credential.py run -- agy

# Run a specific script
python3 scripts/get_credential.py run -- python3 my_script.py
```

### Running with Doppler (Optional Cloud / Team Workflow)

If using Doppler, launch commands via `doppler run`:

```bash
doppler run -- agy
```

When the agent session runs under `doppler run`, all credentials (such as
`SLACK_BOT_TOKEN` and `SLACK_TEAM_ID`) exist only in memory. Any child stdio
MCP servers spawned by the agent automatically inherit those environment
variables without touching disk.

---

## 7. Anti-Patterns & Guardrails

| Anti-Pattern | Why It Fails | Recommended Pattern |
| :--- | :--- | :--- |
| **Committed `.env` file** | Exposes plaintext tokens to git history. | Use `doppler run -- <command>`. |
| **Plaintext disk files** | Leaks unencrypted tokens on disk. | Keep in Doppler or upstream vault. |
| **Echoing secrets to logs** | Leaks tokens into shell logs or CI. | Use `doppler secrets --names`. |
| **Hardcoding in MCP configs** | Storing `xoxb-...` in JSON leaks tokens. | Launch agent session via `doppler run`. |
| **Baking Doppler into MCP configs** | Couples MCP tool configs to secret manager. | Inherit secrets from parent agent process. |

---

## 8. Companion Scripts

* [`scripts/check_doppler.py`](./scripts/check_doppler.py): Doppler CLI and
  project status verification helper.
* [`scripts/get_credential.py`](./scripts/get_credential.py): Upstream vault
  resolver, secret persistence engine, and Doppler synchronization helper.
