---
name: managing-credentials
description: >-
  Configures and manages credentials locally using standard Unix pass (GPG)
  and Bitwarden Secrets Manager as local developer runtime engines, with zero
  plaintext disk footprint and silent in-memory process injection. Use when
  storing credentials, ingesting OAuth JSON or dot-env files, listing secret
  trees safely, or running agent processes with cred run. Don't use for
  unencrypted dot-env files.
metadata:
  version: "0.3.0"
---

# Managing Credentials

Use this skill to configure local credential management using **standard Unix
`pass` (GPG)** and **Bitwarden Secrets Manager** as local developer environment
and runtime engines, ensuring sensitive tokens (such as Slack, API keys, or
Google Workspace OAuth credentials) remain off disk and out of git repositories.

---

## 1. Quick Start: Local Credential CLI (`cred`)

The `cred` CLI provides a unified, 100% local interface for storing, inspecting,
and injecting secrets into child processes:

```bash
# 1. Safely list stored secrets (never leaks secret values)
cred list

# 2. Store a structured secret or individual field
cred set slack/bot_token "xoxb-..."
cred set slack/team_id "T..."

# 3. Ingest OAuth JSON or .env file and automatically wipe source file
cred set gws --from-file ~/Downloads/client_secret_*.json --delete-after

# 4. Launch agy or any tool with all secrets injected strictly into memory
cred run -- agy
```

---

## 2. Setting Up Local `pass` (Standard Unix Password Manager)

`pass` uses standard GPG encryption and Git version control inside
`~/.password-store/`:

### A. Installation (macOS Homebrew)

```bash
brew install pass gnupg pinentry-mac
```

### B. Configure GPG Agent for Silent Keychain Unlock

Configure `~/.gnupg/gpg-agent.conf` so macOS Keychain caches credentials
without blocking background agents:

```conf
pinentry-program /opt/homebrew/bin/pinentry-mac
default-cache-ttl 86400
max-cache-ttl 604800
```

Restart the GPG agent:

```bash
gpgconf --kill gpg-agent
```

---

## 3. Managing Secrets Locally with `pass`

### A. Storing Structured Secrets

```bash
# Ingest Google Workspace OAuth JSON and auto-purge download
python3 scripts/get_credential.py set gws \
  --from-file ~/Downloads/client_secret_*.json \
  --delete-after

# Insert or update individual field
python3 scripts/get_credential.py set slack/bot_token "xoxb-..."
```

### B. Safely Inspecting Secrets

```bash
# List stored secret hierarchy without revealing plaintext values
python3 scripts/get_credential.py list

# Explicitly retrieve a single secret value
python3 scripts/get_credential.py get slack/bot_token
```

---

## 4. Hydrating Local `pass` from Upstream Vaults

When bootstrapping a new machine or syncing from your personal Bitwarden vault
into local `pass`:

```bash
# Sync all project secrets from Bitwarden into local pass store
python3 scripts/get_credential.py sync \
  --upstream bitwarden \
  --dest pass
```

---

## 5. Injecting Credentials at Runtime

Inject secrets directly into process memory at execution time with zero disk
plaintext files:

### Running with Silent In-Memory Injection

```bash
# Automatically resolves and injects ALL local secrets into child process
cred run -- agy

# Run a specific Python script or command
cred run -- python3 my_script.py
```

When the agent session runs under `cred run`, all credentials (such as
`SLACK_BOT_TOKEN`, `GOOGLE_WORKSPACE_CLI_CLIENT_ID`, and `GWS_CLIENT_SECRET`)
exist only in memory. Any child stdio MCP servers spawned by the agent
automatically inherit those environment variables without touching disk.

---

## 6. Anti-Patterns & Guardrails

| Anti-Pattern | Why It Fails | Recommended Pattern |
| :--- | :--- | :--- |
| **Committed `.env` file** | Exposes plaintext tokens to git history. | Use `cred run -- <command>`. |
| **Plaintext disk files** | Leaks unencrypted tokens on disk. | Keep in `pass` or Bitwarden. |
| **Echoing secrets to logs** | Leaks tokens into shell logs or CI. | Use `cred list`. |
| **Hardcoding in MCP configs** | Storing `xoxb-...` in JSON leaks tokens. | Launch agent session via `cred run`. |
| **Unprotected GPG key** | GPG agent blocks background scripts. | Configure `pinentry-mac` Keychain. |

---

## 7. Companion Scripts & References

* [`scripts/get_credential.py`](./scripts/get_credential.py): Local `pass` and
  multi-backend resolver, runtime injector, and secret synchronization engine.
* [`references/ARCHITECTURE.md`](./references/ARCHITECTURE.md): Deep
  architecture guide, macOS/Linux keyring setups, and disaster recovery.
