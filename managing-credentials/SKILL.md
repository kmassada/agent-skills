---
name: managing-credentials
description: >-
  Configures, resolves, and injects credentials from upstream vaults (Bitwarden,
  Google Cloud Secret Manager, Doppler) directly into memory at runtime without
  saving unencrypted plaintext files to disk. Use when configuring secrets for
  agents, syncing vault tokens to local runtime, or injecting credentials into
  MCP servers. Don't use for unencrypted dot-env files or hardcoding secrets.
metadata:
  version: "0.2.0"
---

# Managing Credentials

Use this skill to configure and resolve credentials from upstream secure vaults
(**Bitwarden**, **Google Cloud Secret Manager**, or **Doppler**) and inject them
directly into process memory for AI agents, scripts, and MCP servers without
writing plaintext secret files to disk.

---

## 1. Architectural Philosophy: Zero Plaintext on Disk

1. **Upstream Sources of Truth**:
   * **Personal / Cross-Device**: **Bitwarden** (`bw` personal vault or `bws`
     Secrets Manager).
   * **Enterprise / Work**: **Google Cloud Secret Manager** (`gcloud secrets`).
   * **Local / Cloud Keyring**: **Doppler** (`doppler`).

2. **In-Memory Delivery**:
   * Never store unencrypted `.env` files or plaintext credentials in
     repositories or home directories.
   * Inject credentials directly into process memory at execution time.
   * Stdio MCP servers (`slack`, etc.) automatically inherit credentials from
     the parent agent process.

---

## 2. Upstream Vault Configuration

### Option A: Bitwarden (Personal & Cross-Device)

1. **Personal Vault CLI (`bw`)**:

   ```bash
   # Log in and unlock session
   bw login
   export BW_SESSION="$(bw unlock --raw)"

   # Verify access
   bw get item "SLACK_BOT_TOKEN"
   ```

2. **Bitwarden Secrets Manager (`bws`)**:

   ```bash
   # Set machine access token
   export BWS_ACCESS_TOKEN="<access_token>"

   # Verify access
   bws secret list
   ```

### Option B: Google Cloud Secret Manager (Enterprise & Work)

1. **Authenticate gcloud CLI**:

   ```bash
   gcloud auth login
   gcloud config set project YOUR_GCP_PROJECT_ID
   ```

2. **Access or create secret**:

   ```bash
   # Access latest version
   gcloud secrets versions access latest --secret="SLACK_BOT_TOKEN"

   # Create new secret
   echo -n "xoxb-..." | gcloud secrets create SLACK_BOT_TOKEN \
     --data-file=- --replication-policy="automatic"
   ```

### Option C: Doppler CLI (Local Buffer & Keyring)

1. **Initialize project**:

   ```bash
   doppler login
   doppler projects create ai-agents
   doppler setup --project ai-agents --config dev
   ```

2. **Set secrets**:

   ```bash
   doppler secrets set SLACK_BOT_TOKEN="xoxb-..." SLACK_TEAM_ID="T..."
   ```

---

## 3. Resolving and Injecting Credentials

Use the companion script [`scripts/get_credential.py`](./scripts/get_credential.py)
to fetch, run, or sync credentials dynamically:

### Retrieve a Single Secret

```bash
# Auto-resolve (checks Env -> Bitwarden -> GCP -> Doppler)
python3 scripts/get_credential.py get SLACK_BOT_TOKEN

# Explicit provider
python3 scripts/get_credential.py get SLACK_BOT_TOKEN --provider bitwarden
python3 scripts/get_credential.py get SLACK_BOT_TOKEN --provider gcp --project my-corp
```

### Launch Agent with Injected Secrets

```bash
python3 scripts/get_credential.py run --keys "SLACK_BOT_TOKEN,SLACK_TEAM_ID" -- agy
```

### Sync Upstream Vault to Doppler

```bash
# Pull from Bitwarden and cache into local Doppler keyring
python3 scripts/get_credential.py sync --upstream bitwarden --keys "SLACK_BOT_TOKEN,SLACK_TEAM_ID"

# Pull from Google Cloud Secret Manager into Doppler
python3 scripts/get_credential.py sync --upstream gcp --project my-corp --keys "SLACK_BOT_TOKEN,SLACK_TEAM_ID"
```

---

## 4. Running Agents with MCP Servers

Keep MCP server definitions in `mcp_config.json` clean, portable, and free of
credential wiring. Do not hardcode environment blocks or wrap individual MCP
server commands with Doppler in the JSON definition.

Launch the agent session with credentials injected into memory:

```bash
# Via Doppler
doppler run -- agy

# Or via get_credential.py
python3 scripts/get_credential.py run --keys "SLACK_BOT_TOKEN,SLACK_TEAM_ID" -- agy
```

When the agent session runs, all credentials exist purely in memory. Any child
stdio MCP servers spawned by the agent automatically inherit the environment
variables without touching disk.

---

## 5. Anti-Patterns & Guardrails

| Anti-Pattern | Why It Fails | Recommended Pattern |
| :--- | :--- | :--- |
| **Committed `.env` file** | Exposes plaintext tokens to git history. | Pull on-demand via `get_credential.py`. |
| **Plaintext disk storage** | Leaks tokens on unencrypted host disk. | Keep in Bitwarden/GCP; inject in memory. |
| **Echoing secrets to logs** | Leaks tokens into shell logs or CI. | Query directly via resolver script. |
| **Hardcoding in MCP configs** | Storing `xoxb-...` in JSON leaks tokens. | Inherit secrets from parent agent process. |
| **Baking Doppler into MCP** | Couples MCP tool configs to one vendor. | Keep MCP clean; inject in runtime session. |

---

## 6. Companion Scripts

* [`scripts/get_credential.py`](./scripts/get_credential.py): Multi-backend
  credential resolver and runtime injector.
* [`scripts/check_doppler.py`](./scripts/check_doppler.py): Doppler CLI and
  project status verification helper.
