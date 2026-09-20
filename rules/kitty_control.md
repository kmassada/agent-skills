---
trigger: model_decision
description: "Guidelines and tool workflows for interacting with Kitty terminal windows, tabs, and splits"
---

# Kitty Terminal Control (controlling-kitty)

Whenever interacting with the Kitty terminal emulator, dispatching background
agent tasks, or managing persistent shell windows, adhere to the
[`controlling-kitty`][controlling-kitty-skill] skill:

* **Focus Safety**: Never steal user focus. Always pass `--keep-focus` when
  launching tabs or splits, and use `kitty @ get-text` for silent inspection.
* **Semantic Extraction**: Use `--extent=last_cmd_output` to extract clean
  command outputs without capturing terminal grid blanks or prompt noise.
* **Target Resolution**: Target explicit IDs (`--match id:<window_id>`) or
  native directional neighbors (`--match neighbor:<dir>`).
* **Agent Dispatch**: When dispatching long-running commands or secondary
  agents, spawn dedicated background tabs or splits via `dispatch_agent.py`.
* **Authoritative Reference**: Review the complete runbook and scripts in
  [`controlling-kitty/SKILL.md`][controlling-kitty-skill].

[controlling-kitty-skill]: https://github.com/kmassada/agent-skills/blob/main/controlling-kitty/SKILL.md
