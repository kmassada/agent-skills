---
trigger: model_decision
description: "Standards, schemas, and best practices for creating, evaluating, and auditing agent skills"
---

# Authoring Agent Skills (authoring-skills)

Whenever creating, refactoring, or auditing agent skills or `SKILL.md` files,
adhere to the [`authoring-skills`][authoring-skills-skill] skill:

* **Primary Dispatcher Pattern**: Keep top-level `SKILL.md` lean (<100 lines).
  Use it as a high-level router that dispatches deep domain instructions to
  focused reference documents in `references/`.
* **Cross-Platform Compatibility**: Maintain full compatibility across both
  Google Antigravity (`agy`) and Anthropic Claude Code (`claude`).
* **Evaluation Benchmarks**: Include reproducible evaluation scenarios in
  `evals/evals.json` using standardized input schemas.
* **Frontmatter Rigor**: Ensure YAML frontmatter contains an explicit `name` and
  actionable `description` stating both positive triggers and negative
  constraints.
* **Authoritative Reference**: Review schemas, anti-patterns, and scripts in
  [`authoring-skills/SKILL.md`][authoring-skills-skill].

[authoring-skills-skill]: https://github.com/kmassada/agent-skills/blob/main/authoring-skills/SKILL.md
