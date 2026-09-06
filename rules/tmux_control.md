---
trigger: model_decision
description: "Guidelines and tool workflows for interacting with tmux sessions, windows, and panes"
---

# Terminal Multiplexing & Tmux Control (controlling-tmux)

Whenever interacting with terminal multiplexers, dispatching background agent
tasks, or managing persistent shell panes, adhere to the
[`controlling-tmux`][controlling-tmux-skill] skill:

* **Focus Safety**: Never steal user focus. Capture pane output quietly using
  `tmux capture-pane -p` without switching the active window or session.
* **Target Resolution**: Dynamically inspect and resolve target sessions and
  windows before sending keystrokes. Avoid hardcoding static pane IDs.
* **Geometric Navigation**: Coordinate adjacent panes predictably using
  directional navigation commands.
* **Agent Dispatch**: When dispatching long-running commands or secondary
  agents, provision dedicated tmux windows so execution remains isolated and
  inspectable.
* **Authoritative Reference**: Review the complete runbook and scripts in
  [`controlling-tmux/SKILL.md`][controlling-tmux-skill].

[controlling-tmux-skill]: https://github.com/kmassada/agent-skills/blob/main/controlling-tmux/SKILL.md
