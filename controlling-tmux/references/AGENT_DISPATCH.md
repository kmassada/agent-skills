# Dispatching and Orchestrating AI Agents in Tmux

This guide details patterns and best practices for dispatching, orchestrating,
and monitoring AI agents inside dedicated tmux windows and panes using the
Antigravity CLI (`agy`) and the `agentapi` protocol.

---

## 1. Why Tmux for Agent Orchestration?

When an agent executes long-running, multi-step subtasks (such as background
test runs, exploratory refactoring, or independent audits), executing them
directly in the main agent's subshell causes:

- **Subshell Blocking:** The main agent is blocked waiting for output.
- **Context Pollution:** Large CLI logs and build artifacts flood the main
  agent's context window.
- **Process Fragility:** If the subshell disconnects, the task terminates.

By dispatching agents into dedicated **tmux windows or panes**:

1. **Persistent Execution:** The agent process runs inside a detached tmux
   window (`-d`) independent of the calling subshell.
2. **User Visibility:** The user can switch to the window (`<prefix> w` or
   `tmux select-window -t <id>`) to observe and interact with the agent's TUI.
3. **Parallel Concurrency:** Multiple agents can run simultaneously across
   dedicated windows or side-by-side splits.
4. **Seamless Attachment:** Ongoing conversations can be rejoined or monitored
   at any time via `agy --conversation <id>` or `agentapi send-message`.

---

## 2. Dispatch Patterns

### Pattern A: Interactive TUI Window (Direct `agy`)

Launch an interactive agent session with an initial prompt in a new detached
window:

```bash
# 1. Create detached window running agy with an initial prompt
tmux new-window -d -n "refactor-db" -c "/Users/makz/src/agent-skills" \
  -P -F '#{window_id} #{pane_id}' \
  "agy -i 'Refactor SQLite models to use dataclasses'"
```

Key flags:

- `-d`: Detached (does not steal user focus from the current window).
- `-n <name>`: Human-readable window title for the status bar.
- `-c <dir>`: Sets working directory for the agent workspace.
- `-P -F '#{window_id} #{pane_id}'`: Prints the immutable IDs (`@12 %35`).
- `"agy -i '...'"`: Passes the prompt to the interactive TUI.

---

### Pattern B: Programmatic Conversation via `agentapi`

When you need an explicit conversation ID to track or message programmatically:

```bash
# 1. Create a headless conversation
CONV_ID=$(agentapi new-conversation --title="api-audit" "Audit auth endpoints")

# 2. Open a dedicated tmux window connected to the conversation
tmux new-window -d -n "api-audit" -c "$PWD" \
  -P -F '#{window_id}' \
  "agy --conversation $CONV_ID"
```

Benefits:

- Generates a trackable conversation ID before opening UI.
- Allows sending follow-up messages or checking metadata via `agentapi`.

---

### Pattern C: Side-by-Side Split Pane

When pair-programming or having an assistant agent assist in the same window:

```bash
# Split horizontally beside the current pane ($TMUX_PANE)
tmux split-window -h -d -t "$TMUX_PANE" -c "$PWD" \
  -P -F '#{pane_id}' \
  "agy -i 'Review diffs in current git branch'"
```

Use `split-window -v` for stacked vertical splits.

---

### Pattern D: Continuing Recent Session

To resurrect or continue the user's most recent conversation:

```bash
tmux new-window -d -n "recent-agy" -c "$PWD" "agy -c"
```

---

## 3. Communication & Inter-Agent Coordination

### Sending Follow-Up Prompts

#### Option 1: Via Tmux Keys (TUI Input)

Send text directly into the running agent pane:

```bash
# Send prompt and submit with Enter (C-m)
tmux send-keys -t %35 'Run unit tests now' C-m
```

#### Option 2: Via `agentapi send-message` (API Level)

Send a message directly into the conversation queue:

```bash
agentapi send-message "$CONV_ID" "Build completed. Verify deployment status."
```

---

### Silent Observation (Zero Focus Stealing)

To read the agent's progress without disrupting the user:

```bash
# Read visible screen
tmux capture-pane -t %35 -p

# Read last 100 lines of scrollback history
tmux capture-pane -t %35 -p -S -100
```

To check status via API:

```bash
agentapi get-conversation-metadata "$CONV_ID"
```

---

## 4. Helper Script: `dispatch_agent.py`

The companion script `scripts/dispatch_agent.py` automates command construction,
slug naming, argument escaping, and ID extraction:

```bash
# Dispatch to new window
python3 controlling-tmux/scripts/dispatch_agent.py \
  --title="db-migrate" \
  --prompt="Apply latest Alembic migrations"

# Dispatch via API method with specific model
python3 controlling-tmux/scripts/dispatch_agent.py \
  --method=api \
  --model=flash \
  --title="linter" \
  --prompt="Fix all ruff warnings in src/"

# Split current window horizontally and attach conversation
python3 controlling-tmux/scripts/dispatch_agent.py \
  --conversation="d202f5d4-f6b7-4b75-bdb3-03679b8122fa" \
  --mode=split-h

# Dry run (prints planned tmux commands without running)
python3 controlling-tmux/scripts/dispatch_agent.py \
  --prompt="Test run" \
  --dry-run --json
```

---

## 5. Anti-Patterns & Safety Rules

| Anti-Pattern | Risk | Correct Practice |
| :--- | :--- | :--- |
| **Blocking Subshell Execution** | Running `agy -i ...` in the agent's own subshell freezes the primary workflow. | Always spawn inside tmux via `tmux new-window -d` or `dispatch_agent.py`. |
| **Focus Stealing** | Calling `select-window` or omitting `-d` pulls user cursor away from their active editor. | Always pass `-d` (detached) unless user explicitly says "open and switch to it". |
| **Unanchored Splitting** | Splitting without `-t "$TMUX_PANE"` may target whichever window the user has active. | Always anchor splits with `-t "$TMUX_PANE"`. |
| **Unsanitized Prompts** | Shell quotes breaking when prompt has single quotes or newlines. | Use `shlex.quote` or `dispatch_agent.py` to ensure clean escaping. |
