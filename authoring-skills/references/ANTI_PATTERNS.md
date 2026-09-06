# Skill Anti-Patterns & Pitfalls

This guide outlines common anti-patterns encountered in agent skill design and
the recommended patterns to resolve them.

---

## 1. Context Confusion (The Cardinal Anti-Pattern)

- **The Mistake:** The user asks the agent to run a command in a specific target
  environment (e.g., inside Docker, over SSH, or in a tmux pane), and the agent
  runs the command directly in its own local subshell.
- **Why it fails:** Breaks environment boundaries, creates side effects in the
  agent workspace, and fails to execute where intended.
- **Correct Pattern:** Always enforce strict context separation in the
  instructions:
  - For tmux: `tmux send-keys -t <pane_id> '<cmd>' C-m`
  - For containers: `docker exec -it <container> <cmd>`
  - For remote hosts: `ssh <host> '<cmd>'`

---

## 2. Focus Hijacking & Disruptive Observation

- **The Mistake:** The agent switches active windows or selects panes simply to
  view logs or read output (e.g., calling `tmux select-pane` or focusing a
  window).
- **Why it fails:** Interrupts the human user who is typing or navigating
  another terminal pane or editor window.
- **Correct Pattern:** Always use non-invasive, silent observation tools:
  - In tmux: `tmux capture-pane -t <pane_id> -p`
  - In containers: `docker logs <container>`
  - Only change UI focus when the user explicitly requests: _"switch to window
    X"_ or _"focus pane Y"_.

---

## 3. Volatile Identifiers

- **The Mistake:** Directing commands to transient, relative indices (e.g.,
  targeting pane `1` or window `2`).
- **Why it fails:** Indices shift dynamically whenever neighboring panes/windows
  are closed, split, or reordered.
- **Correct Pattern:** Always capture and use immutable IDs:
  - Use `-P -F '#{pane_id}'` or `-P -F '#{window_id}'` during creation to store
    explicit identifiers (e.g., `%17`, `@4`).

---

## 4. Hallucinated Scripting

- **The Mistake:** Expecting the LLM to write complex coordinate math,
  multi-line stream parsing, or intricate regex parsing from scratch in inline
  markdown.
- **Why it fails:** LLMs are non-deterministic and prone to subtle off-by-one
  errors or shell escaping corruptions.
- **Correct Pattern:** Offload complex, repetitive, or sensitive calculations
  into pre-written, unit-tested scripts in the `scripts/` directory.

---

## 5. Over-Triggering & Keyword Collisions

- **The Mistake:** Writing generic descriptions with common programming words
  (e.g., _"Helps split strings and manipulate text"_ triggering on "split pane",
  or _"Builds code"_ triggering on any compiler command).
- **Why it fails:** Causes the skill to activate when completely irrelevant,
  cluttering the agent's context.
- **Correct Pattern:** Include both explicit positive triggers (_"Use when..."_)
  and negative guardrails (_"Don't use for Python string splitting or general
  text editing"_).

---

## 6. Monolithic Instructions (Context Bloat)

- **The Mistake:** Dumping entire API manuals, 3,000-line schemas, or long
  tutorials into `SKILL.md`.
- **Why it fails:** Overwhelms the model's active working memory and degrades
  reasoning quality.
- **Correct Pattern:** Follow progressive disclosure:
  - Keep `SKILL.md` under 500 lines.
  - Move deep specifications into `references/<topic>.md`.
  - The agent will call `view_file` on reference files only when that specific
    subtopic is needed.

---

## 7. Knowledge Quizzes / Trivia Evals

- **The Mistake:** Writing evaluation cases that ask the agent conceptual
  questions (e.g., _"What tools does this skill provide?"_ or _"How do I use
  gcloud?"_).
- **Why it fails:** Evals test the agent's ability to act, not recite
  documentation. Recitation does not guarantee the agent can successfully
  execute workflows in realistic environments.
- **Correct Pattern:** Frame authentic tasks that require applying the skill to
  reach an outcome (e.g., _"The staging web service is returning 502 errors.
  Find the failing container and inspect its exit code."_).

---

## 8. Leaking Tool Names in Eval Prompts

- **The Mistake:** Mentioning specific tools, scripts, or flags in the eval
  prompt (e.g., _"Run `scripts/inspect.py --filter=pods` to find unhealthy
  pods"_).
- **Why it fails:** Bypasses the skill's semantic routing and procedural
  instructions entirely, masking whether the agent would naturally select and
  use the skill.
- **Correct Pattern:** Describe only the authentic user request and context,
  verifying that the agent autonomously discovers and invokes the right tool.
