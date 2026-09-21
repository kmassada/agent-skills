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

### D. Entries Withheld from Injection

Bulk injection is deliberately not "everything in the store":

* **`bitwarden/*` and `bws/*` are never injected.** These are bootstrap
  credentials: they unlock the upstream vault that holds every other secret.
  Injecting them would mean one leaky MCP server costs you the whole vault
  instead of one service token. `cred sync` reads them directly; child processes
  never see them.
* **Process-control variables are refused.** An entry that would render as
  `PATH`, `HOME`, `LD_PRELOAD`, `DYLD_INSERT_LIBRARIES` (and similar) is skipped
  with a warning, so a store entry cannot hijack the process `cred run` launches.

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

Choose a key type deliberately — this decides what "encrypted at rest" actually
buys you.

#### Desktop (macOS / Linux) — passphrase-protected key

This is the default you want on any machine you carry. The passphrase is cached
by the OS keyring via the pinentry configured in Step 2, so background agents
still run without prompts:

```bash
# Generate a passphrase-protected key (gpg prompts via pinentry)
gpg --full-generate-key --expert

# Initialize pass repository against that key's email
pass init agent-user@local
```

#### Headless / CI / container — unprotected key

```bash
# Disposable container key: no passphrase, for automated runners only
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

pass init agent-user@local
```

> **What `%no-protection` costs you.** The private key sits unencrypted in
> `~/.gnupg`. Anything that can read that directory — a process running as you,
> a Time Machine or `rsync` backup, a stolen unlocked disk image — decrypts the
> entire store. The store is then obfuscated at rest, not encrypted against a
> local attacker. That is an acceptable trade for a disposable runner that holds
> scoped credentials and is rebuilt from upstream; it is a poor one for a laptop.
> Note also that the macOS "Allow all applications to access this item" Keychain
> ACL in §3A grants every local process access to the cached passphrase — prefer
> leaving the ACL prompting per-application if you can tolerate the first prompt.

### Step 3b: Install the `cred` Command

`cred` is this skill's `scripts/get_credential.py` on your `PATH`. Symlink it
rather than copying, so the command cannot drift from the skill:

```bash
mkdir -p ~/.local/bin
ln -sf "$PWD/scripts/get_credential.py" ~/.local/bin/cred
chmod +x scripts/get_credential.py
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

# Ingest an OAuth client JSON file and purge the source download afterwards
cred set gws --from-file ~/Downloads/client_secret_*.json --delete-after
```

> `--delete-after` overwrites the source file's bytes and unlinks it, but only
> once the vault write is confirmed. It is best effort, not a forensic wipe:
> copy-on-write filesystems (APFS, Btrfs), SSD wear levelling, snapshots and
> editor backups may retain the original blocks. Treat a credential that ever
> touched disk as one to rotate, not merely to delete.
