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

# 2. Store a field. Omit the value: you are prompted without echo, so the
#    secret never reaches shell history or `ps`.
cred set slack/bot_token
cred set slack/team_id

# 3. Ingest OAuth JSON or .env file, purging the source once the write lands
cred set gws --from-file ~/Downloads/client_secret_*.json --delete-after

# 4. Launch agy or any tool with all secrets injected strictly into memory
cred run -- agy
```

> **Never pass a secret as a command-line argument.** `cred set name "xoxb-..."`
> writes the token to shell history and exposes it in `ps` to every process on
> the machine. `cred` warns when you do this. Pipe instead when scripting:
> `printf %s "$TOKEN" | cred set slack/bot_token`.

### Installing the `cred` command

`cred` is `scripts/get_credential.py` on your `PATH`. Symlink it so the command
tracks the skill instead of drifting from a stale copy:

```bash
mkdir -p ~/.local/bin
ln -sf "$PWD/scripts/get_credential.py" ~/.local/bin/cred
chmod +x scripts/get_credential.py
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

# Insert or update an individual field (prompts without echo)
python3 scripts/get_credential.py set slack/bot_token
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

### What Is Deliberately Not Injected

Two classes of entry are withheld from bulk injection:

* **Upstream vault keys** (`bitwarden/*`, `bws/*`). These unlock every other
  secret you own. A single leaky MCP server would otherwise surrender the whole
  upstream vault rather than one service token. `cred sync` still reads them.
* **Process-control variables** (`PATH`, `HOME`, `LD_PRELOAD`,
  `DYLD_INSERT_LIBRARIES`, and similar). A store entry named `path` would
  otherwise hijack the child process. `cred` warns and skips.

Narrow the injection further with `--keys` when a tool needs only one secret:

```bash
cred run --keys SLACK_BOT_TOKEN -- python3 my_script.py
```

---

## 6. Resolving from Other Providers

`pass` is the default local engine, but single values can be read from Google
Cloud Secret Manager or Doppler without ever landing on disk:

```bash
# Read one secret from GCP Secret Manager
python3 scripts/get_credential.py get SLACK_BOT_TOKEN \
  --provider gcp --project my-corp

# Equivalent raw CLI call
gcloud secrets versions access latest --secret=SLACK_BOT_TOKEN --project=my-corp

# Inject a GCP-resolved secret straight into a process
cred run --provider gcp --project my-corp -- python3 my_script.py
```

To eval a value into the current shell, use `--format export`, which shell-quotes
the secret so metacharacters cannot execute:

```bash
eval "$(cred get slack/bot_token --format export)"
```

---

## 7. Anti-Patterns & Guardrails

| Anti-Pattern | Why It Fails | Recommended Pattern |
| :--- | :--- | :--- |
| **Committed `.env` file** | Plaintext tokens enter git history. | `cred run -- <command>`. |
| **Plaintext disk files** | Unencrypted tokens leak on disk. | Keep in `pass` or Bitwarden. |
| **Secret in argv** | Lands in shell history and `ps`. | `cred set <path>`, no value. |
| **Echoing secrets to logs** | Tokens leak into shell logs or CI. | `cred list`. |
| **Hardcoding in MCP configs** | `xoxb-...` in JSON leaks tokens. | Launch session via `cred run`. |
| **Unprotected GPG key** | Store decrypts for any local process. | Passphrase + keyring caching. |

---

## 8. Companion Scripts & References

* [`scripts/get_credential.py`](./scripts/get_credential.py): Local `pass` and
  multi-backend resolver, runtime injector, and secret synchronization engine.
* [`references/ARCHITECTURE.md`](./references/ARCHITECTURE.md): Deep
  architecture guide, macOS/Linux keyring setups, and disaster recovery.
