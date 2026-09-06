---
name: managing-credentials
description: >-
  Configures and manages credentials locally using Doppler without external
  cloud sync. Use when installing Doppler, authenticating locally, setting
  secrets, or injecting environment variables into local scripts, agents, and
  MCP servers. Don't use for configuring cloud sync integrations, CI/CD
  deployments, Kubernetes operators, or unencrypted local dot-env files.
metadata:
  version: "0.1.0"
---

# Managing Credentials

Use this skill to configure local credential management using Doppler, ensuring
sensitive tokens (such as Slack, API keys, or database credentials) remain
off disk and out of git repositories.

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

## 2. Local Project Setup (No External Sync)

Set up a project scope without attaching external cloud or CI/CD sync targets:

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

Set, inspect, or delete credentials directly through the CLI:

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

## 4. Injecting Credentials at Runtime

Inject secrets into process memory at execution time rather than writing
unencrypted `.env` files to disk.

### Running Local Scripts and Commands

Use `doppler run -- <command>` to inject all secrets as environment variables:

```bash
doppler run -- python3 scripts/my_agent_task.py
```

### Configuring MCP Servers

Configure Model Context Protocol (MCP) servers to pull secrets dynamically:

```json
{
  "mcpServers": {
    "slack": {
      "command": "doppler",
      "args": ["run", "--", "npx", "-y", "@modelcontextprotocol/server-slack"]
    }
  }
}
```

---

## 5. Anti-Patterns & Guardrails

| Anti-Pattern | Why It Fails | Recommended Pattern |
| :--- | :--- | :--- |
| **Committed `.env` file** | Exposes plaintext tokens to git history. | Use `doppler run -- <command>`. |
| **Setting up Cloud Sync** | Unnecessary external attack surface for local dev. | Keep project local without sync. |
| **Echoing secrets to logs** | Leaks tokens into shell logs or CI output. | Use `doppler secrets --names`. |
| **Hardcoding in MCP configs** | Storing `xoxb-...` in JSON configs leaks tokens. | Wrap MCP commands with `doppler run`. |

---

## 6. Companion Scripts

* Use [`scripts/check_doppler.py`](./scripts/check_doppler.py) to check CLI
  availability, setup status, and secret key existence.
