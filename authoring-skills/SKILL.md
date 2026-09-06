---
name: authoring-skills
description: >-
  Guides the creation, structuring, formatting, evaluating, and auditing of
  agent skills. Use when authoring new skills, editing SKILL.md files, designing
  eval suites, or reviewing skills for anti-patterns. Don't use for generic
  application programming or non-agent repository workflows.
---

# Authoring Skills

Use when creating new skills, structuring instruction runbooks, writing
evaluations in `evals/evals.json`, or auditing skills against cross-platform
standards (Google Antigravity and Anthropic Claude Code).

> [!NOTE] **Primary Dispatcher Pattern**
>
> This skill acts as a Primary Dispatcher. Consult the table below to identify
> the dedicated reference guide for your specific task, and call `view_file` on
> that file to load detailed guidance.

---

## Reference Guide Directory

| Task / Topic                   | Dedicated Reference File                                          | Key Instructions Covered                                                                                        |
| :----------------------------- | :---------------------------------------------------------------- | :-------------------------------------------------------------------------------------------------------------- |
| **Design Principles**          | [DESIGN_PRINCIPLES.md](./references/DESIGN_PRINCIPLES.md)         | Experience-based drafting, explaining intent, signal-to-noise ratio, gerund naming, and progressive disclosure. |
| **Skill Format & Layout**      | [FORMAT.md](./references/FORMAT.md)                               | Directory structure, YAML frontmatter constraints, folded scalars (`>-`), and character limits.                 |
| **Eval Schemas & Testing**     | [EVAL_SCHEMAS.md](./references/EVAL_SCHEMAS.md)                   | Canonical `evals.json` schema, writing verifiable expectations, `grading.json`, and `benchmark.json`.           |
| **Anti-Patterns & Pitfalls**   | [ANTI_PATTERNS.md](./references/ANTI_PATTERNS.md)                 | Context confusion, focus hijacking, volatile identifiers, monolithic instructions, and over/undertriggering.    |
| **Quality & Format Audit**     | [audit_skill.py](./scripts/audit_skill.py)                        | CLI tool validating frontmatter, layout, link integrity, and script standards.                                  |
| **Skill Boilerplate Template** | [SKILL.md.template](./references/templates/SKILL.md.template)     | Ready-to-use template for new skills.                                                                           |
| **Eval Boilerplate Template**  | [evals.json.template](./references/templates/evals.json.template) | Starter template for Claude-conforming eval suites.                                                             |

---

## Execution Commands

- **Audit a skill directory:**

  ```bash
  python3 scripts/audit_skill.py <path/to/skill>
  ```

- **Run deterministic static evaluations:**

  ```bash
  python3 evals/run_eval.py --static
  ```

---

## Tools

- `view_file`: Load the appropriate reference file above before executing
  actions.
- `run_command`: Execute test harnesses and audit scripts.
