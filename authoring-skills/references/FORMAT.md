# Skill Structure and Format

All skills must adhere to standard directory layouts and frontmatter formatting
rules to guarantee discovery across Antigravity and Claude Code environments.

---

## 1. Directory Structure

A standardized skill follows this file tree:

```text
skills/<skill-name>/
|-- SKILL.md                  # Required: Main instruction file with YAML frontmatter
|-- scripts/                  # Optional: Deterministic helper scripts (Python, Bash)
|-- references/               # Optional: Specialized sub-guides, specifications, schemas
|-- resources/                # Optional: Assets, static data files, templates
\-- evals/                    # Strongly Recommended: Automated test cases
    |-- evals.json            # Canonical test definitions & expectations
    \-- run_eval.py           # Multi-agent test runner
```

---

## 2. Frontmatter Standards

The `SKILL.md` file must open with a strict YAML frontmatter block:

```yaml
---
name: my-specialized-skill
description: >-
  Third-person capability statement describing what the skill does. Explicitly
  list positive triggers using "Use when..." and negative triggers using "Don't
  use for...". Include key operational terms. Wrap lines cleanly at 80
  characters.
metadata:
  version: "0.1.0"
---
```

### Constraints & Validation Rules

1. **`name`** _(string, required)_:
   - Lowercase letters, numbers, and hyphens only (`^[a-z0-9-]+$`).
   - No leading, trailing, or double hyphens (`--`).
   - Maximum length: **64 characters**.
   - Strongly prefer the **Gerund form** (e.g., `authoring-skills`,
     `profiling-service`).

2. **`description`** _(string, required)_:
   - Use the folded scalar block indicator `>-` for clean, multi-line YAML
     formatting.
   - **Capability Statement:** Start with a third-person verb phrase (e.g.,
     _"Analyzes profiling traces..."_ not _"I help you analyze"_).
   - **Explicit Triggers:** Always include both positive triggers (_"Use
     when..."_) and negative guardrails (_"Don't use for..."_).
   - **No XML / HTML Tags:** Do not use angle brackets (`<` or `>`) in the
     description text.
   - **Character Limit:** Maximum **1024 characters**.
   - **Line Wrapping:** Wrap each line inside the description at **80
     characters** (including the 4-space indentation), as formatters do not
     automatically wrap YAML frontmatter.

3. **`metadata`** _(object, optional)_:
   - Versioning following Semantic Versioning (e.g. `version: "0.1.0"`).

---

## 3. Markdown Body Structure

Following the frontmatter, structure the document logically:

1. **Title:** Single `# Title` header matching the skill name (e.g.,
   `# Authoring Skills`).
2. **Primary Dispatcher (for multi-topic skills):** Provide a clear markdown
   table mapping user tasks to dedicated files in `references/`.
3. **Core Instructions:** Step-by-step procedures, required flags, and execution
   loops.
4. **Anti-Patterns Table:** Explicitly contrast common mistakes with the correct
   pattern.
5. **No Redundancy:** Do **not** repeat `**Name:**` or `**Description:**` in the
   markdown body -- the frontmatter is the single source of truth.
