# Local Credential Architecture & Operations Guide

This document details the mental model, security invariants, synchronization
pipeline, and disaster recovery workflows for local credential management.

---

## 1. Core Mental Model: Upstream vs. Ephemeral Local Cache

```text
┌─────────────────────────────────────────────────────────────┐
│                   Upstream Source of Truth                  │
│               Bitwarden Secrets Manager (BWS)               │
│               (Durable, Cloud, Multi-Device)                │
└──────────────────────────────┬──────────────────────────────┘
                               │
            cred sync --upstream bitwarden --dest pass
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                 Disposable Local Cache                      │
│               Standard Unix pass (GPG Store)                │
│                 ~/.password-store/ai-agents/                │
└──────────────────────────────┬──────────────────────────────┘
                               │
                        cred run -- agy
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                   Child Process Memory                      │
│            Injected directly into Process RAM               │
│          Zero Disk Plaintext | Zero .env Files              │
└─────────────────────────────────────────────────────────────┘
```

### Why This Separation Exists

* **Upstream (Bitwarden):** Your primary vault. If your laptop falls into the
  ocean, all credentials remain safe and backed up in your cloud Bitwarden
  account.
* **Local Cache (`pass`):** An encrypted, offline mirror. All AI agents, MCP
  servers, and shell scripts read from this local cache. They execute instantly
  with zero cloud API latency and work offline.
* **Disposable Nature:** If your local machine GPG keys or keychain are ever
  corrupted, you can delete `~/.password-store` with zero data loss and
  re-hydrate from Bitwarden in 5 seconds.

---

## 2. Vault Structure & Mapping Conventions

### A. Bitwarden Secrets Manager (`ai-agents` Project)

In Bitwarden, secrets are organized as structured JSON under clean service
names:

* **Secret: `slack`**
  ```json
  {
    "bot_token": "xoxb-...",
    "team_id": "T0BV7THPDEH",
    "workspace_url": "https://ai-agentsworkspace.slack.com",
    "workspace_name": "ai-agents",
    "bot_name": "antigravity"
  }
  ```
* **Secret: `gws`**
  ```json
  {
    "client_id": "....apps.googleusercontent.com",
    "client_secret": "GOCSPX-...",
    "project_id": "kmassada-gws"
  }
  ```

### B. Local `pass` Tree (`cred list`)

When synced, `pass` organizes secrets into hierarchical folders matching the
service names:

```text
ai-agents/
├── bitwarden/
│   ├── access_token
│   └── project_id
├── gws/
│   ├── client_id
│   ├── client_secret
│   └── project_id
└── slack/
    ├── bot_name
    ├── bot_token
    ├── team_id
    ├── workspace_name
    └── workspace_url
```

### C. Automatic Environment Variable Injection

When `cred run -- <command>` is executed:
* `ai-agents/slack/bot_token` $\to$ `SLACK_BOT_TOKEN`
* `ai-agents/slack/team_id` $\to$ `SLACK_TEAM_ID`
* `ai-agents/gws/client_id` $\to$ `GWS_CLIENT_ID` and `GOOGLE_WORKSPACE_CLI_CLIENT_ID`
* `ai-agents/gws/client_secret` $\to$ `GWS_CLIENT_SECRET` and `GOOGLE_WORKSPACE_CLI_CLIENT_SECRET`
* `ai-agents/gws/project_id` $\to$ `GWS_PROJECT_ID` and `GOOGLE_WORKSPACE_PROJECT_ID`

---

## 3. macOS Keychain & GPG-Agent Bridge

To prevent background AI agents from being blocked by GUI password prompts,
`pinentry-mac` integrates with the macOS Login Keychain:

1. **GPG Key Protection:** The local GPG private key is protected with a
   passphrase stored in macOS Keychain (`~/Library/Keychains/login.keychain-db`).
2. **Access Control:** The `GnuPG` keychain entry is set to
   `Allow all applications to access this item`.
3. **Session Caching:** `gpg-agent` maintains an in-memory cache
   (`default-cache-ttl 86400` / 24 hours), enabling silent, friction-free
   execution for all sub-agents and child processes.

---

## 4. Disaster Recovery & Fresh Machine Bootstrapping

If setting up a brand new computer or recovering from a wiped drive:

### Step 1: Install Prerequisites

```bash
brew install pass gnupg pinentry-mac bws
```

### Step 2: Configure GPG Agent for macOS

Create `~/.gnupg/gpg-agent.conf`:

```conf
pinentry-program /opt/homebrew/bin/pinentry-mac
default-cache-ttl 86400
max-cache-ttl 604800
```

Restart agent:

```bash
gpgconf --kill gpg-agent
```

### Step 3: Initialize Local Password Store

```bash
# Generate local GPG key for pass
gpg --batch --gen-key <<EOF
Key-Type: EDDSA
Key-Curve: ed25519
Subkey-Type: ECDH
Subkey-Curve: cv25519
Name-Real: kmassada
Name-Email: kmassada@local
Expire-Date: 0
%no-protection
%commit
EOF

# Initialize pass repository
pass init kmassada@local
```

### Step 4: Hydrate from Bitwarden

1. Copy your `BWS_ACCESS_TOKEN` once from your Bitwarden Vault app or browser.
2. Store the token into `pass`:
   ```bash
   cred set bitwarden/access_token "0.xxxx..."
   cred set bitwarden/project_id "your-bws-project-id"
   ```
3. Sync all secrets into `pass`:
   ```bash
   cred sync --upstream bitwarden --dest pass
   ```

All secrets are now hydrated locally, encrypted, and ready for agents.

---

## 5. Day-to-Day Operations Cheat Sheet

```bash
# List all secret paths without leaking values
cred list

# Launch AI agent with all secrets injected into memory
cred run -- agy

# Sync any updates made in Bitwarden into local pass
cred sync --upstream bitwarden --dest pass

# Add or update a local secret manually
cred set slack/bot_token "xoxb-new-token"

# Ingest an OAuth client JSON file and automatically wipe the source download
cred set gws --from-file ~/Downloads/client_secret_*.json --delete-after
```
