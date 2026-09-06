# Model Context Protocol (MCP) Directory

This directory hosts standardized Model Context Protocol (MCP) configuration
templates and server setups for the `agent-skills` repository.

---

## Configuration Overview

The primary configuration file is [`mcp_config.json`](./mcp_config.json), which
declares available MCP servers for Google Antigravity and Anthropic Claude Code.

### Active Servers

* **`slack`**: Integrates Slack workspace interactions using the official
  `@modelcontextprotocol/server-slack` server package.

---

## Slack MCP Server Setup

### 1. Prerequisites

The Slack MCP server requires:

* Node.js and `npx` installed on the host.
* A registered Slack App with Bot User OAuth permissions:
  * `channels:read` (read public channel listings)
  * `channels:history` (read messages and threads)
  * `chat:write` (post messages to channels)
  * `users:read` (resolve member details)

### 2. Required Environment Variables

The server expects two environment variables at runtime:

* `SLACK_BOT_TOKEN`: The Bot User OAuth Token starting with `xoxb-...`.
* `SLACK_TEAM_ID`: The unique Slack Workspace/Team ID starting with `T...`.

### 3. Server Declaration

Standard stdio transport declared in `mcp_config.json`:

```json
{
  "mcpServers": {
    "slack": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-slack"],
      "env": {
        "SLACK_BOT_TOKEN": "${SLACK_BOT_TOKEN}",
        "SLACK_TEAM_ID": "${SLACK_TEAM_ID}"
      }
    }
  }
}
```

---

## Activation in Agent Clients

### Antigravity (`agy`)

Copy or link the configuration into your Antigravity configuration file at
`~/.gemini/config/mcp_config.json`:

```bash
# Verify active environment variables
echo "SLACK_BOT_TOKEN=${SLACK_BOT_TOKEN:+SET}"
echo "SLACK_TEAM_ID=${SLACK_TEAM_ID:+SET}"
```

### Claude Code

Merge the `mcpServers` block into your Claude Code settings or project MCP
configuration file.
