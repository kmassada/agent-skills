# Dispatching and Orchestrating AI Agents in Kitty

This guide details patterns and best practices for dispatching, orchestrating,
and monitoring AI agents inside dedicated Kitty tabs and windows using the
Antigravity CLI (`agy`) and the `agentapi` protocol.

---

## 1. Why Kitty for Agent Orchestration?

When an agent executes long-running, multi-step subtasks (such as background test
runs, exploratory refactoring, or independent audits), executing them directly
in the primary agent subshell causes:

* **Subshell Blocking:** The primary agent is blocked waiting for output.
* **Context Pollution:** Large CLI logs and build artifacts flood the agent's
  context window.
* **Process Fragility:** If the subshell disconnects, the task terminates.

By dispatching agents into dedicated **Kitty tabs or split windows**:

1. **Persistent Execution:** The agent process runs inside a separate Kitty
   window/tab independent of the calling subshell.
2. **User Visibility:** The user can view the agent running in its own tab or
   side-by-side pane without focus disruption.
3. **Parallel Concurrency:** Multiple agents can run simultaneously across
   dedicated tabs or split layouts.
4. **Rich Terminal Output:** Agents can output images, plots, and formatted text
   directly onto the Kitty canvas.

---

## 2. Dispatch Patterns

### Pattern A: Dedicated Tab (Direct `agy`)

Launch an interactive agent session in a new background tab:

```bash
kitty @ launch --type=tab --tab-title="refactor-db" --keep-focus \
  --cwd="$PWD" agy -i "Refactor SQLite models to use dataclasses"
```

Key flags:

* `--type=tab`: Creates a new tab in the current OS window.
* `--tab-title="<title>"`: Sets a human-readable title on the tab bar.
* `--keep-focus`: Prevents stealing user cursor focus from the current window.
* `--cwd="<dir>"`: Sets working directory for the agent workspace.

---

### Pattern B: Side-by-Side Split Window

When pairing with an agent in the same tab:

```bash
# Split vertically beside the current window ($KITTY_WINDOW_ID)
kitty @ launch --type=window --location=vsplit --title="agent-pair" \
  --keep-focus --cwd="$PWD" agy -i "Review recent diffs in git"
```

For top/bottom stacked splits, use `--location=hsplit`.

---

### Pattern C: Programmatic Conversation via `agentapi`

When you need an explicit conversation ID to track or message programmatically:

```bash
# 1. Create a headless conversation
CONV_ID=$(agentapi new-conversation --title="api-audit" "Audit auth endpoints")

# 2. Open a dedicated tab connected to the conversation
kitty @ launch --type=tab --tab-title="api-audit" --keep-focus \
  --cwd="$PWD" agy --conversation "$CONV_ID"
```

---

### Pattern D: Continuing Recent Session

To resurrect or continue the user's most recent conversation:

```bash
kitty @ launch --type=tab --tab-title="recent-agy" --keep-focus \
  --cwd="$PWD" agy --continue
```

---

## 3. Communication & Inter-Agent Coordination

### Sending Follow-Up Prompts

Send text directly into the running Kitty window:

```bash
kitty @ send-text --match id:15 "Run unit tests now\r"
```

### Silent Observation (Zero Focus Stealing)

To read the agent's progress without disrupting the user:

```bash
# Read visible screen
kitty @ get-text --match id:15 --extent=screen

# Read last command output specifically
kitty @ get-text --match id:15 --extent=last_cmd_output

# Read full scrollback history
kitty @ get-text --match id:15 --extent=all
```

---

## 4. Helper Script: `dispatch_agent.py`

The companion script `scripts/dispatch_agent.py` automates argument escaping,
slug generation, and launch configuration:

```bash
# Dispatch to new tab
python3 controlling-kitty/scripts/dispatch_agent.py \
  --title="db-migrate" \
  --prompt="Apply latest Alembic migrations"

# Dispatch to split window beside current
python3 controlling-kitty/scripts/dispatch_agent.py \
  --mode=split-v \
  --prompt="Run test suite"

# Dry run (prints planned Kitty commands as JSON without running)
python3 controlling-kitty/scripts/dispatch_agent.py \
  --prompt="Test run" \
  --dry-run --json
```
