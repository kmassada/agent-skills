---
name: controlling-kitty
description: >-
  Manages Kitty terminal emulator tabs, windows, and splits. Creates tabs,
  splits panes (vertical/horizontal), sends commands to specific windows,
  quietly captures outputs without stealing user focus, inspects state via
  JSON, navigates adjacent windows directionally, and dispatches AI agent
  sessions into dedicated Kitty tabs and splits. Use when interacting with
  Kitty terminal emulator, dispatching AI agents to Kitty tabs, running
  background tasks in Kitty, reading outputs from persistent windows, or
  navigating adjacent Kitty windows. Don't use for local subshell command
  execution, standard file manipulation, or non-terminal workflows.
---

# Controlling Kitty

> [!IMPORTANT]
> **Strict Context Separation**
> **YOUR** `run_command` tool executes commands directly in **YOUR** current
> agent subshell/environment.
>
> * **To run a command in a Kitty window:** You **MUST** use
>   `kitty @ send-text --match id:<target_id> '<command>\r'`.
> * **To read another Kitty window:** You **MUST** use
>   `kitty @ get-text --match id:<target_id>`.
> * **NEVER** run the user's targeted command directly in your own subshell
>   unless the user explicitly tells you to run it locally.

---

## Core Instructions

### 1. Hierarchy & Terminology

Before taking action, distinguish between Kitty tabs and windows:

* **OS Windows (`os_window`):** Top-level desktop GUI application windows.
* **Tabs (`tab`):** Tabs inside an OS window (equivalent to tmux windows).
  * *User says:* **"new tab"** ->
    `kitty @ launch --type=tab --tab-title=<name> --keep-focus`
* **Windows (`window`):** Splits or panes inside a tab (equivalent to tmux
  panes).
  * *User says:* **"new pane"** or **"split window"** ->
    `kitty @ launch --type=window --location=vsplit --keep-focus`
* **Splitting Logic:**
  * Side-by-side split -> `--location=vsplit`
  * Stacked top-and-bottom split -> `--location=hsplit`

### 2. Immutable IDs & Window Anchoring (`$KITTY_WINDOW_ID`)

* **Always target explicit IDs:** Use `--match id:<window_id>` (e.g.,
  `--match id:14`) to ensure commands reach the intended target.
* **Anchor to Origin:** When running inside an active Kitty session,
  `$KITTY_WINDOW_ID` contains your current integer window ID. For relative
  requests ("split beside me", "in this tab"), anchor using
  `--match id:$KITTY_WINDOW_ID`.
* **Avoid Focus Volatility:** Always pass `--keep-focus` when creating tabs or
  splits unless the user explicitly requested to switch focus.

### 3. Safe Execution Loop (Read-After-Write)

When sending commands to any window, follow this sequence:

1. **Targeted Write:** Send text with newline carriage return (`\r`):

   ```bash
   kitty @ send-text --match id:<window_id> '<command>\r'
   ```

2. **Inspect Process State:** Inspect the active foreground process via
   `kitty @ ls` or `kitty_state.py`:

   ```bash
   python3 {skill_dir}/scripts/kitty_state.py --find-window <window_id>
   ```

3. **Verify & Read Output:** Capture the semantic output of the command:

   ```bash
   # Capture exact output of the last completed command
   kitty @ get-text --match id:<window_id> --extent=last_cmd_output
   ```

### 4. Silent Observation (Zero Focus-Stealing)

* **External Observation:** Always read remote window output silently using
  `kitty @ get-text --match id:<window_id>`.
* **Do NOT steal user focus:** Never call `kitty @ focus-window` or
  `kitty @ focus-tab` just to view output. Only change focus when the user
  explicitly asks to switch focus.
* **Extent Options:**
  * `--extent=screen`: Visible screen area only.
  * `--extent=last_cmd_output`: Semantic output of the last command.
  * `--extent=all`: Entire scrollback buffer.

### 5. Large Input & Multiline Payloads

Pasting large blocks of text or scripts through raw arguments can cause quoting
errors.

* Use `--stdin` to stream large or multiline content safely:

  ```bash
  cat script.sh | kitty @ send-text --match id:<window_id> --stdin
  ```

### 6. AI Agent Dispatching & Multi-Agent Sessions

When dispatching a long-running, parallel, or exploratory agent task:

* **Do NOT execute in the local subshell:** Running `agy` in your current
  subshell blocks execution and pollutes context.
* **Dispatch to a dedicated background tab:**

  ```bash
  kitty @ launch --type=tab --tab-title="<title>" --keep-focus \
    --cwd="<dir>" agy -i "<prompt>"
  ```

* **Automate with `dispatch_agent.py`:**

  ```bash
  python3 {skill_dir}/scripts/dispatch_agent.py --title="refactor" --prompt="Fix tests"
  ```

* See [references/AGENT_DISPATCH.md](./references/AGENT_DISPATCH.md) for details.

---

## Key Operations Cheat Sheet

| Operation | User Intent | Command Pattern | Key Notes |
| :--- | :--- | :--- | :--- |
| **New Tab** | "Create tab named server" | `kitty @ launch --type=tab --tab-title=server --keep-focus` | Returns new window ID |
| **Split Side-by-Side** | "Split window side-by-side" | `kitty @ launch --type=window --location=vsplit --keep-focus` | Vertical split |
| **Split Stacked** | "Split window top/bottom" | `kitty @ launch --type=window --location=hsplit --keep-focus` | Horizontal split |
| **Send Command** | "In window 2 run cargo build" | `kitty @ send-text --match id:2 'cargo build\r'` | Uses carriage return |
| **Get Window Output** | "What is in window 2?" | `kitty @ get-text --match id:2 --extent=screen` | Silent read |
| **Last Command Output** | "Get output of last command" | `kitty @ get-text --match id:2 --extent=last_cmd_output` | Semantic extraction |
| **Get Full History** | "Show full logs in window 2" | `kitty @ get-text --match id:2 --extent=all` | Full scrollback |
| **Send Stdin** | "Paste multiline script" | `kitty @ send-text --match id:2 --stdin < script.py` | Safe multiline input |
| **List Windows/Tabs** | "List all tabs and windows" | `kitty @ ls` or `python3 {skill_dir}/scripts/kitty_state.py` | Structured JSON |
| **Focus Window** | "Switch to window 2" | `kitty @ focus-window --match id:2` | Only when requested |
| **Focus Neighbor** | "Focus window to the right" | `kitty @ focus-window --match neighbor:right` | Built-in navigation |
| **Close Window** | "Close window 2" | `kitty @ close-window --match id:2` | Closes target window |
| **Dispatch Agent** | "Run agent to refactor DB" | `python3 {skill_dir}/scripts/dispatch_agent.py --prompt="..."` | Detached tab |

---

## Anti-Patterns & Correct Usage

| Anti-Pattern | What the Agent did wrong | Correct Pattern |
| :--- | :--- | :--- |
| **Direct Execution** | User: "Run `git status` in window 2" -> Agent runs locally. | `kitty @ send-text --match id:2 'git status\r'` |
| **Blind Reading** | User: "Read window 2" -> Agent tries to cat log files. | `kitty @ get-text --match id:2` |
| **Focus Hijack** | Agent executes `focus-window` just to view output. | Use `get-text` silently in background. |
| **Blocking Dispatch** | User: "Start agent to run migrations" -> Runs `agy` in subshell. | `kitty @ launch --type=tab agy -i '...'` |

---

## Directional Navigation

Kitty natively supports directional relative window targeting without manual
coordinate math:

```bash
# Focus window to the left, right, top, or bottom
kitty @ focus-window --match neighbor:left
kitty @ focus-window --match neighbor:right
kitty @ focus-window --match neighbor:top
kitty @ focus-window --match neighbor:bottom
```
