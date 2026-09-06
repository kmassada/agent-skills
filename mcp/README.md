# Model Context Protocol (MCP) Directory

This directory hosts standardized Model Context Protocol (MCP) configuration
templates and server setups for the `agent-skills` repository.

---

## Configuration Philosophy: Decoupled & Credential-Agnostic

MCP server configurations in this repository are strictly **credential-agnostic**
and decoupled from secret providers:

* **Zero Hardcoded Secrets**: Configuration files never contain API keys,
  tokens, or passwords.
* **Zero Baked-In Wrappers**: Configuration files do not hardcode wrapper
  commands (like `doppler run` or custom loaders).
* **Process Inheritance**: Stdio MCP servers automatically inherit environment
  variables directly from the parent agent process at runtime.

---

## Active MCP Servers

### `slack`

Integrates Slack workspace interactions using the official
`@modelcontextprotocol/server-slack` package.

#### Server Declaration ([`mcp_config.json`](./mcp_config.json))

```json
{
  "mcpServers": {
    "slack": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-slack"
      ]
    }
  }
}
```

#### Expected Runtime Environment

The Slack server process reads these variables from its inherited process
environment:

* `SLACK_BOT_TOKEN`: The Bot User OAuth Token starting with `xoxb-...`.
* `SLACK_TEAM_ID`: The unique Slack Workspace/Team ID starting with `T...`.

Required Slack App Bot User OAuth permissions:

* `channels:read` (read public channel listings)
* `channels:history` (read messages and threads)
* `chat:write` (post messages to channels)
* `users:read` (resolve member details)

---

## Runtime Credential Injection

Because the server definition is decoupled, you choose how to inject credentials
into the agent's environment:

### Option A: Doppler Session Wrapping (Recommended for Local Dev)

Launch the agent session via `doppler run`. All child MCP servers inherit the
injected tokens without writing anything to disk:

```bash
doppler run -- agy
```

### Option B: Shell Environment

Export credentials in your local session or shell profile:

```bash
export SLACK_BOT_TOKEN="xoxb-..."
export SLACK_TEAM_ID="T..."
agy
```
