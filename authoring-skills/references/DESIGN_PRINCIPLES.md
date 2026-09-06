# Principles of Skill Design

When creating or modifying an agent skill, adhere to these core design
principles to ensure it provides high signal, reliable triggering, and
actionable execution guidance.

---

## 1. Experience Before Theory

Try to solve the target tasks **before** writing the skill. Do not speculate
about what might go wrong.

- Run sample prompts without any skill loaded and observe where the agent fails,
  hallucinates, or takes inefficient detours.
- The specific edge cases and gotchas discovered through initial failure are the
  skill's most valuable content.
- Encode solutions to real observed failure modes rather than hypothetical
  scenarios.

---

## 2. Explain the Why

Agents comply significantly better with understood intent than with rigid, blind
directives.

- When you explain **why** an instruction or constraint exists, the model
  generalizes accurately to unforeseen edge cases.
- Avoid heavy-handed, caps-lock directives like `ALWAYS` or `NEVER` without
  providing the underlying technical rationale (e.g., instead of _"NEVER use
  select-pane"_, write _"Do not use select-pane to view logs, as switching
  active panes interrupts user typing in interactive workflows"_).

---

## 3. Signal, Not Noise

Every line in a skill consumes attention budget in the model's context window.

- **Keep:** Concrete command sequences, specific flag combinations, Gotchas,
  regexes, and environment-specific patterns.
- **Cut:** Generic programming advice (e.g., _"write clean code"_, _"check your
  work"_), obvious explanations of basic tools, and filler introductory text.

---

## 4. One Job Well

Each skill should focus on a coherent, well-defined operational domain. If
describing a skill requires joining multiple unrelated capabilities with "and",
consider splitting it into dedicated skills.

- **Naming Convention (Gerund Form):** Use the **Gerund form** (verb + -ing) in
  `kebab-case` for the skill identifier (e.g., `authoring-skills`,
  `debugging-containers`, `managing-tmux`).
- **Description Ergonomics:** Skill descriptions must be written in the **third
  person** (e.g., _"Deploys and manages staging clusters..."_ not _"I help you
  deploy"_ or _"You can use this to..."_). This ensures accurate matching by
  semantic skill routers.

---

## 5. Generalize, Don't Overfit

When refining a skill after evaluation failures, avoid narrow, overfitted fixes
that only satisfy the specific failed test prompt.

- Identify the underlying behavioral class or ambiguity that caused the issue.
- Encode the general operational rule or provide a deterministic script rather
  than patching in an overly specific condition.

---

## 6. Environment & Path Portability

Skills must run seamlessly across different machines, CI/CD runners, and
developer environments without relying on fixed absolute paths.

- **No Hardcoded Home Directories:** Never hardcode paths like `/Users/alice/`
  or `/home/bob/` in scripts or markdown.
- **Dynamic Placeholders:** Use `{skill_dir}` in markdown instructions when
  referencing local sibling assets.
- **Self-Locating Scripts:** In bash scripts, dynamically resolve the script's
  root directory:

  ```bash
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  ```

- **Relative Documentation Links:** Always use relative paths when linking to
  bundled references (e.g., `[FORMAT](./FORMAT.md)` or
  `[eval_schemas](./EVAL_SCHEMAS.md)`).

---

## 7. Progressive Disclosure & Layout Discipline

To maintain high agent performance, respect the three-tier disclosure model:

- **Tier 1 (Metadata):** Keep the YAML frontmatter under 100 words. It is loaded
  on every turn to route queries.
- **Tier 2 (SKILL.md):** Target under 500 lines. Focus on workflow dispatching,
  gotchas, and core procedures.
- **Tier 3 (Bundled Resources):** Offload detailed API tables, schemas, and deep
  documentation to `references/`, and complex procedural logic to executable
  scripts in `scripts/`.

---

## 8. Test Automation & Pre-Submit Gates

A skill is production code. When skills bundle scripts in `scripts/` or
evaluations in `evals/`, they must include automated test gates:

- **Companion Unit Tests:** Every executable script must have a sibling
  `*_test.py` that executes deterministically without mutating the user's
  live environment.
- **Eval Runner & Schema Gate:** `evals/run_eval.py` must support a dry-run
  mode verifying that `evals/evals.json` syntax, expectation schemas, and regex
  patterns remain valid.
- **Composite Pre-Commit Gates:** Bundle a `.pre-commit-config.yaml` within
  the skill package for standalone autonomy, and ensure companion tests can be
  dynamically discovered and verified in monorepo CI environments.
