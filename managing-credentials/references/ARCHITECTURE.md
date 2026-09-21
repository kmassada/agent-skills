# Local Credential Architecture & Operations Guide

This document details the mental model, security invariants, synchronization
pipeline, cross-platform keyring configurations, and disaster recovery
workflows for local credential management across macOS and Linux.

---

## 1. Core Mental Model: Upstream vs. Ephemeral Local Cache

```text
+-------------------------------------------------------------+
|                   Upstream Source of Truth                  |
|               Bitwarden Secrets Manager (BWS)               |
|               (Durable, Cloud, Multi-Device)                |
+------------------------------+------------------------------+
                               |
            cred sync --upstream bitwarden --dest pass
                               |
                               v
+-------------------------------------------------------------+
|                 Disposable Local Cache                      |
|               Standard Unix pass (GPG Store)                |
|                 ~/.password-store/ai-agents/                |
+------------------------------+------------------------------+
                               |
                        cred run -- agy
                               |
                               v
+-------------------------------------------------------------+
|                   Child Process Memory                      |
|            Injected directly into Process RAM               |
|          Zero Disk Plaintext | Zero .env Files              |
+-------------------------------------------------------------+
```

### Why This Separation Exists

* **Upstream (Bitwarden):** Your primary vault. If your laptop falls into the
  ocean, all credentials remain safe and backed up in your cloud Bitwarden
  account.

* **Local Cache (`pass`):** An encrypted, offline mirror. All AI agents, MCP
  servers, and shell scripts read from this local cache. They execute instantly
  with zero cloud API latency and work offline.

* **Disposable Nature:** If your local machine GPG keys or keyring are ever
  corrupted, you can delete `~/.password-store` with zero data loss and
  re-hydrate from Bitwarden in 5 seconds.

---

## 2. Vault Structure & Mapping Conventions

### A. Bitwarden Secrets Manager

In Bitwarden, secrets are stored as structured JSON or individual key-value pairs
under service names:

```json
{
  "api_key": "...",
  "service_token": "..."
}
```

### B. Local `pass` Hierarchy (`cred list`)

When synced, `pass` organizes secrets into hierarchical folders:

```text
ai-agents/
├── <service>/
│   ├── <field_1>
│   └── <field_2>
```

### C. Automatic Environment Variable Injection

When `cred run -- <command>` is executed, directory paths are automatically
transformed into uppercase environment variables for child processes:

* `ai-agents/<service>/<field>` -> `<SERVICE>_<FIELD>`
* Standard aliases (e.g., `GWS_*` -> `GOOGLE_WORKSPACE_CLI_*`) are mapped
  automatically.

---

## 3. OS Keyring & GPG-Agent Bridge (macOS & Linux)

To prevent background AI agents from being blocked by GUI password prompts,
the GPG agent bridges to native operating system keyrings:

### A. macOS (Apple Login Keychain)

* **Keyring Engine:** Apple Login Keychain (`login.keychain-db`).
* **Pinentry Program:** `pinentry-mac`.
* **Access Control:** Set the `GnuPG` keychain entry to
  `Allow all applications to access this item`.
* **Behavior:** Unlocks automatically when you log into your Mac. Subsequent
  agent operations run with **zero prompts**.

### B. Linux Desktop (GNOME Keyring / KWallet)

* **Keyring Engine:** GNOME Keyring / KWallet via Secret Service API.
* **Pinentry Program:** `pinentry-gnome3` or `pinentry-qt`.
* **Behavior:** PAM unlocks the keyring on desktop login. On first prompt,
  check "Automatically unlock this key whenever I'm logged in" to enable
  **zero prompt** background execution.

### C. Headless Linux / Server / SSH / Docker Containers

* **Keyring Engine:** `gpg-agent` in-memory cache or disposable key.
* **Pinentry Program:** `pinentry-curses` or loopback.
* **Behavior:**
  * *Option 1 (24-hr cache):* Prompt once per day in terminal; cached in RAM.
  * *Option 2 (Disposable Container Key):* Generate the local container key with
    `%no-protection` for 100% automated headless runners.

---

## 4. Disaster Recovery & Fresh Machine Bootstrapping

If setting up a brand new machine or recovering from a wiped drive:

### Step 1: Install Prerequisites

#### On macOS (Homebrew + BWS installer)

```bash
brew install pass gnupg pinentry-mac
curl -sSL https://bws.bitwarden.com/install | sh -s -- --install-dir ~/.local/bin
```

#### On Linux (apt / dnf + BWS installer)

```bash
# Debian / Ubuntu:
sudo apt update && sudo apt install -y pass gnupg pinentry-gnome3

# Fedora / RHEL:
sudo dnf install -y pass gnupg2 pinentry-gnome3

# Bitwarden Secrets Manager CLI:
curl -sSL https://bws.bitwarden.com/install | sh -s -- --install-dir ~/.local/bin
```

### Step 2: Configure GPG Agent

Create or update `~/.gnupg/gpg-agent.conf`:

#### macOS

```conf
pinentry-program /opt/homebrew/bin/pinentry-mac
default-cache-ttl 86400
max-cache-ttl 604800
```

#### Linux Desktop

```conf
pinentry-program /usr/bin/pinentry-gnome3
default-cache-ttl 86400
max-cache-ttl 604800
```

Restart the agent:

```bash
gpgconf --kill gpg-agent
```

### Step 3: Initialize Local Password Store

```bash
# Generate local disposable GPG key for pass
gpg --batch --gen-key <<EOF
Key-Type: EDDSA
Key-Curve: ed25519
Subkey-Type: ECDH
Subkey-Curve: cv25519
Name-Real: agent-user
Name-Email: agent-user@local
Expire-Date: 0
%no-protection
%commit
EOF

# Initialize pass repository
pass init agent-user@local
```

### Step 4: Hydrate from Bitwarden

1. Copy your `BWS_ACCESS_TOKEN` once from your Bitwarden web vault or app.

2. Store the token into `pass` (enter via hidden input):

   ```bash
   cred set bitwarden/access_token
   cred set bitwarden/project_id
   ```

3. Sync all secrets into `pass`:

   ```bash
   cred sync --upstream bitwarden --dest pass
   ```

All secrets are now hydrated locally, encrypted in `pass`, and ready for agents.

---

## 5. Day-to-Day Operations Cheat Sheet

```bash
# List all secret paths without leaking values
cred list

# Launch AI agent with all secrets injected into memory
cred run -- agy

# Sync any updates made in Bitwarden into local pass
cred sync --upstream bitwarden --dest pass

# Add or update a local secret manually with hidden input (no echo)
cred set slack/bot_token

# Ingest an OAuth client JSON file and automatically wipe the source download
cred set gws --from-file ~/Downloads/client_secret_*.json --delete-after
```
