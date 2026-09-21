---
name: controlling-tmux
description: >-
  Manages tmux terminal sessions, windows, and panes. Creates windows,
  splits panes (horizontal/vertical/full-width), sends commands to specific
  panes, quietly captures outputs without stealing user focus, navigates
  adjacent panes geometrically, and dispatches AI agent sessions into
  dedicated tmux windows. Use when interacting with terminal multiplexers,
  dispatching AI agents to tmux windows, running background tasks in tmux,
  reading outputs from persistent panes, or navigating adjacent panes. Don't
  use for local subshell command execution, standard file manipulation, or
  non-terminal workflows.
---

# Controlling Tmux

> [!IMPORTANT] **Strict Context Separation** **YOUR** `run_command` tool
> executes commands directly in **YOUR** current agent subshell/environment.
>
> - **To run a command in a tmux pane:** You **MUST** use
>   `tmux send-keys -t <target_pane> -l '<command>'` followed by
>   `tmux send-keys -t <target_pane> Enter`.
> - **To read another pane:** You **MUST** use
>   `tmux capture-pane -t <target_pane> -p`.
> - **NEVER** run the user's targeted command directly in your own subshell
>   unless the user explicitly tells you to run it locally.

---

## Core Instructions

### 1. Hierarchy & Terminology

Before taking action, distinguish between windows and panes:

- **Windows:** A window occupies the entire terminal screen. It has an
  immutable ID (`@10`) and a volatile index (`1`, `2`, `3`...).
  - _User says:_ **"new window"** -> `tmux new-window -d -n <name> -P -F
    '#{window_id}'`.
- **Panes:** A window is split into multiple panes. A pane likewise has an
  immutable ID (`%17`) and a volatile index (`0`, `1`, `2`...). The `%` prefix
  always marks an ID, never an index.
  - _User says:_ **"new pane"** or **"split pane"** -> Split the target pane
    (`tmux split-window -h` or `-v`).
- **Splitting Logic:** If the user doesn't specify horizontal or vertical,
  inspect the layout using `tmux list-panes`:
  - If panes are side-by-side (horizontal layout), split vertically (`-v`).
  - If panes are stacked top-to-bottom (vertical layout), split horizontally
    (`-h`).

### 2. Immutable IDs & Pane Anchoring (`$TMUX_PANE`)

- **Always use immutable IDs:** Pane indices change when neighboring panes
  close. Always capture and reference explicit IDs (`%17`, `@10`):
  - `tmux split-window -P -F '#{pane_id}'`
  - `tmux new-window -P -F '#{window_id}'`
- **Anchor to Origin:** When running inside an active tmux session, `$TMUX_PANE`
  contains your current pane ID. For relative requests ("split beside me", "in
  this window"), anchor using `-t "$TMUX_PANE"`.
- **Avoid Focus Volatility:** Never run target-less commands
  (`tmux display-message` without `-t`) as the user's focus may move while the
  agent is executing.

### 3. Safe Execution Loop (Read-After-Write)

When sending commands to any pane, follow this 4-step sequence:

1. **Inspect & Clear Copy Mode:** Check deterministic mode state:

   ```bash
   MODE=$(tmux display-message -p -t <pane_id> '#{pane_in_mode}')
   [ "$MODE" = "1" ] && tmux copy-mode -q -t <pane_id>
   ```

2. **Explicitly Targeted Write:** Send the command literally with `-l`, then
   submit Enter as a separate key:

   ```bash
   tmux send-keys -t <pane_id> -l '<command>'
   tmux send-keys -t <pane_id> Enter
   ```

   Without `-l`, tmux interprets a payload that exactly matches a key name
   (`Enter`, `Escape`, `BSpace`, `Space`, `Tab`, `C-c`, `F1`...) as that
   keypress instead of typing the text. If the command itself contains a single
   quote, quote it for your own shell first (`printf %q`, or write it to a file
   and use the buffer method in section 5).

3. **Deterministic Completion Check:** Query `#{pane_current_command}` rather
   than guessing sleep times:

   ```bash
   # Returns active process (e.g. pytest, cargo) or idle shell (zsh, bash)
   tmux display-message -p -t <pane_id> '#{pane_current_command}'
   ```

4. **Verify & Read Output:** Capture screen, stripping only the trailing
   virtual terminal grid blanks:

   ```bash
   # -e :a ... deletes blank lines at the END of the stream only
   tmux capture-pane -t <pane_id> -p | sed -e :a -e '/^\n*$/{$d;N;ba' -e '}' \
     | tail -n 20
   ```

   Do **not** use `sed '/^[[:space:]]*$/d'`: it deletes every blank line in the
   capture, collapsing the interior spacing that separates stack traces, diff
   hunks, and test-failure blocks.

### 4. Silent Observation (Zero Focus-Stealing)

- **External Observation:** Always read remote pane output silently from your
  shell using `tmux capture-pane -t <pane_id> -p`.
- **Do NOT steal user focus:** Never call `select-pane` or `select-window` just
  to view output. Only change focus when the user explicitly asks to switch
  focus.
- **Buffer Depth:** By default, `capture-pane` reads visible lines. For history,
  use `-S -100` (last 100 lines) or `-S -` (entire scrollback).
- **Grid Blank Rows:** Terminal height padding leaves trailing blanks at the
  bottom. Trim only those (see section 3, step 4) - a global blank-line delete
  would also destroy the interior spacing that makes output readable.

### 5. Large Input & Multiline Payloads

Pasting large blocks of text or scripts through `send-keys` can drop characters
or get corrupted by shell auto-suggestions.

- For multi-line code or large inputs, write the content to a temporary file in
  your scratch directory, then load and paste it:

  ```bash
  tmux load-buffer <file_path> && tmux paste-buffer -t <pane_id>
  ```

### 6. AI Agent Dispatching

Never run `agy` in your own subshell: it blocks your execution loop and floods
your context. Dispatch it into tmux instead - see
[Agent Dispatching & Multi-Agent Orchestration](#agent-dispatching--multi-agent-orchestration)
below for the commands and flags.

---

## Key Operations Cheat Sheet

| Operation            | User Intent                     | Command Pattern                                                                                          | Key Notes                     |
| :------------------- | :------------------------------ | :------------------------------------------------------------------------------------------------------- | :---------------------------- |
| **New Window**       | "Create window named server"    | `tmux new-window -d -n <name> -c <path> -P -F '#{window_id}'`                                            | Returns `@window_id`          |
| **Split Horizontal** | "Split window side-by-side"     | `tmux split-window -h -t "$TMUX_PANE" -P -F '#{pane_id}'`                                                | Returns `%pane_id`            |
| **Split Vertical**   | "Split window top/bottom"       | `tmux split-window -v -t "$TMUX_PANE" -P -F '#{pane_id}'`                                                | Returns `%pane_id`            |
| **Full-Width Split** | "Full-width pane across bottom" | `tmux split-window -f -v -t "$TMUX_PANE" -P -F '#{pane_id}'`                                             | `-f` spans full width         |
| **Send Command**     | "In pane %17 run cargo build"   | `tmux send-keys -t %17 -l 'cargo build'` then `tmux send-keys -t %17 Enter`                              | `-l` sends text literally     |
| **Get Pane Output**  | "What is in pane %17?"          | `tmux capture-pane -t %17 -p`                                                                            | Add `-S -100` for history     |
| **Exit Copy Mode**   | "Clear search/scroll lock"      | `tmux copy-mode -q -t %17`                                                                               | Restores normal prompt        |
| **Paste Buffer**     | "Paste multiline script"        | `tmux load-buffer <file> && tmux paste-buffer -t %17`                                                    | Safe for large blocks         |
| **List Windows**     | "List all tmux windows"         | `tmux list-windows`                                                                                      | Shows IDs & active status     |
| **List Panes**       | "List panes in current window"  | `tmux list-panes -t <window_id>`                                                                         | Shows IDs & geometry          |
| **Select Window**    | "Switch to window @10"          | `tmux select-window -t @10`                                                                              | Only when user asks to switch |
| **Select Pane**      | "Focus pane %17"                | `tmux select-pane -t %17`                                                                                | Only when user asks to focus  |
| **Rename Window**    | "Rename window to logs"         | `tmux rename-window -t @10 logs`                                                                         | Updates title                 |
| **Kill Target**      | "Close pane %17 / window @10"   | `tmux kill-pane -t %17` / `tmux kill-window -t @10`                                                      | Terminate target              |
| **Dispatch Agent**   | "Run agent to refactor DB"      | `python3 {skill_dir}/scripts/dispatch_agent.py --title=db --prompt="..."`                                | Detached `agy` window         |
| **Split Agent**      | "Open agent side-by-side"       | `python3 {skill_dir}/scripts/dispatch_agent.py --mode=split-h --target-pane="$TMUX_PANE" --prompt="..."` | Anchor is required            |
| **Resume Session**   | "Attach to conv-1234 in window" | `tmux new-window -d -n agent "agy --conversation <id>"`                                                  | Joins ongoing conversation    |

---

## Anti-Patterns & Correct Usage

| Anti-Pattern          | What the Agent did wrong                                                               | Correct Pattern                                     |
| :-------------------- | :------------------------------------------------------------------------------------- | :-------------------------------------------------- |
| **Direct Execution**  | User: "Run `git status` in pane 2" -> Agent runs `git status` via its own subshell.    | `tmux send-keys -t %2 -l 'git status'` then `Enter` |
| **Blind Reading**     | User: "Read pane 2" -> Agent tries to `cat` a log file or attach to pane.              | `tmux capture-pane -t %2 -p`                        |
| **Focus Hijack**      | Agent executes `select-pane` just to view output, disrupting user typing.              | Use `capture-pane` silently in background.          |
| **Index Volatility**  | Relying on relative indices (`1`, `2`) which shift as panes are closed.                | Always target explicit IDs (`%17`, `@10`).          |
| **Blocking Dispatch** | User: "Start agent to run migrations" -> Agent runs `agy` in its own subshell.         | `tmux new-window -d -n db "agy -i '...'"`           |
| **Unanchored Split**  | `tmux split-window -h` with no `-t`, which splits whichever pane the user has focused. | Always pass `-t "$TMUX_PANE"` or an explicit `%id`. |
| **Blind Blank Strip** | `sed '/^[[:space:]]*$/d'` on a capture, which also deletes interior blank lines.       | Trim trailing blanks only (section 3, step 4).      |

---

## Relative Directional Navigation

When the user asks to interact with or focus an adjacent pane by direction
(_"pane to the right"_, _"pane below"_, _"pane above"_, _"left pane"_):

1. **Use the geometric resolver script:**

   ```bash
   # Get adjacent target pane ID
   python3 {skill_dir}/scripts/relative_pane.py --direction=right --pane="$TMUX_PANE"

   # Target and focus adjacent pane directly
   python3 {skill_dir}/scripts/relative_pane.py --direction=under --pane="$TMUX_PANE" --select
   ```

   Always pass `--pane`. The script scopes its geometry lookup to that pane's
   window; without it, tmux falls back to whichever window is active, so the
   answer depends on where the user's focus happens to be. `--select` is the
   only flag here that moves focus - omit it to resolve an ID silently.

2. See
   [references/GEOMETRIC_NAVIGATION.md](./references/GEOMETRIC_NAVIGATION.md)
   for coordinate geometry details and fallback calculations.

---

## Agent Dispatching & Multi-Agent Orchestration

When the user asks to spin up an agent, run an AI task in parallel, or inspect
an ongoing conversation:

1. **Use `dispatch_agent.py`:**

   ```bash
   # Create a detached tmux window running agy
   python3 {skill_dir}/scripts/dispatch_agent.py --title="audit" --prompt="Audit repository"

   # Split current window side-by-side and attach to conversation
   python3 {skill_dir}/scripts/dispatch_agent.py --conversation="<conv_id>" --mode=split-h
   ```

2. **`dispatch_agent.py` flags:**

   | Flag                   | Purpose                                                           |
   | :--------------------- | :---------------------------------------------------------------- |
   | `--prompt`, `-p`       | Initial prompt (one of prompt/conversation/continue is required). |
   | `--conversation`, `-c` | Attach to an existing conversation ID.                            |
   | `--continue`           | Resume the most recent `agy` conversation.                        |
   | `--title`, `-t`        | Window name; slugged to `[a-z0-9_-]` either way.                  |
   | `--mode`               | `window` (default), `split-h`, or `split-v`.                      |
   | `--target-pane`        | Split anchor; defaults to `$TMUX_PANE`. Splits fail without one.  |
   | `--method`             | `interactive` (default) or `api` (via `agentapi`).                |
   | `--agent`              | Agent persona or profile for the session.                         |
   | `--model`              | `flash_lite`, `flash`, or `pro`.                                  |
   | `--profile`            | Execution profile for `agentapi` (`--method=api` only).           |
   | `--extra-flag`         | Extra `agy` argument, repeatable; use `--extra-flag=--foo`.       |
   | `--cwd`                | Working directory for the agent.                                  |
   | `--focus`              | Switch focus to the new window/pane (default is detached).        |
   | `--socket`, `-L`       | Target a non-default tmux socket.                                 |
   | `--dry-run`            | Print the planned tmux command as JSON without running it.        |
   | `--json`               | Emit the structured result.                                       |

3. **See [references/AGENT_DISPATCH.md](./references/AGENT_DISPATCH.md)** for
   the complete guide to `agy` CLI flags, `agentapi` integration, and
   inter-agent messaging.

---

## Troubleshooting & Delegation

- **Can't find pane / session:** Verify tmux is running with `tmux ls`.
- **Complex State Resolution:** If you encounter persistent "can't find
  window/pane" errors, or deeply nested multi-session layouts, delegate
  diagnosis to the `tmux-investigator` subagent (defined in
  `agents/tmux-investigator.md`).
