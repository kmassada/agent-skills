# Agent Operating Guidelines: `agent-skills` Monorepo

Welcome to the `agent-skills` monorepo. This repository hosts modular,
production-grade agent skills compatible with both **Google Antigravity** and
**Anthropic Claude Code**.

All AI agents operating within this repository must adhere to the workflows,
quality gates, and invariants detailed below.

---

## 1. Monorepo Architecture & Structure

Each skill is isolated in its own top-level directory and follows a strict,
standardized structure:

```text
agent-skills/
├── .github/scripts/           # Automated catalog generator & CI test runner
├── rules/                     # Repository-level agent behavioral rules
├── <skill-name>/              # Modular skill package (e.g. controlling-tmux)
│   ├── SKILL.md               # Lean operational runbook
│   ├── .pre-commit-config.yaml# Standalone skill pre-commit gate
│   ├── scripts/               # Production utilities & companion tests
│   ├── evals/                 # Benchmark evals & runner
│   └── references/            # Architecture & deep references
├── .pre-commit-config.yaml    # Monorepo composite quality gates
├── AGENTS.md                  # This operational playbook
└── README.md                  # Generated catalog (DO NOT EDIT MANUALLY)
```

Each skill directory (`<skill-name>/`) is an autonomous, self-contained unit
capable of functioning either within this monorepo or as a standalone git
repository.

---

## 2. Core Repository Invariants

Every agent working in this monorepo must respect these non-negotiable gates:

### A. Composite Pre-Commit Architecture

The repository employs a composite pre-commit architecture balancing
standalone portability with monorepo velocity:

* **Standalone Autonomy**: Every skill directory carries its own
  `.pre-commit-config.yaml`. When a skill is cloned or developed as an
  independent repository, running `uvx pre-commit run --all-files` locally
  enforces its own linters, types, and companion tests without monorepo
  dependencies.
* **Monorepo Dynamic Discovery**: The root `.pre-commit-config.yaml` runs
  `python3 .github/scripts/run_skill_tests.py`, which dynamically identifies
  affected skill packages from staged files and executes their companion tests
  automatically. Adding a new skill requires zero edits to the root
  pre-commit configuration.

### B. Catalog Synchronization Invariant

* **Rule**: **NEVER edit `README.md` manually.**
* Always run:

  ```bash
  python3 .github/scripts/generate_readme.py
  ```

* The catalog generator inspects all `SKILL.md` frontmatter, extracts summaries,
  components, and file links, and auto-formats `README.md` with prettier and
  markdownlint.
* Verify catalog synchronization using:

  ```bash
  python3 .github/scripts/generate_readme.py --check
  ```

### C. Python Quality Gates (`writing-python`)

* **Line Length**: Strictly $\le 88$ columns across all Python files.
* **Abstract Container Typing**: Function parameters and return values must use
  abstract interfaces from `collections.abc` (`Sequence[T]`, `Mapping[K, V]`,
  `Iterable[T]`).
* **Zero Concrete Dict Annotations**: In `generate_readme.py` and
  `audit_skill.py`, return `Mapping` or `Sequence[Mapping]`, never concrete
  `dict`.
* **Zero Deprecated Imports**: No `from typing import List, Dict, Optional`.
  Use built-in generics and pipe unions (`str | None`).
* **Hermetic Testing**: Unit tests must use standard library `unittest` with
  100% mocked boundaries (`mock.patch`, `mock.create_autospec`) and temporary
  directories (`tempfile.TemporaryDirectory`). Never modify live user sessions
  or repositories during tests.
* **Deterministic Execution**: Standalone executable scripts must include
  shebang `#!/usr/bin/env python3` and PEP 723 `# /// script` metadata.

### D. Markdown Quality Gates (`writing-markdown`)

* **Line Length**: Strictly $\le 80$ columns for all prose, headings, and lists.
* **Lists**: Surround all lists with blank lines (MD032). Standardize on `*`.
* **Code Fences**: Surround all code blocks with blank lines (MD031) and declare
  language tags (MD040).
* **ASCII Hygiene**: Zero unicode quotes, arrows, or curly symbols. Standard
  ASCII only (`$`, `>`, `->`, `'`, `"`).

---

## 3. New Skill Onboarding Checklist

Follow this 8-step gate whenever adding a new skill to this monorepo:

1. **Gerund Naming**:
   Name the skill directory using a lowercase gerund verb + noun (e.g.,
   `inspecting-logs`, `debugging-queries`).

2. **Frontmatter & SKILL.md Structure**:
   * Set `name: <skill-name>` (must match directory name exactly).
   * Write `description: >-` as a folded scalar with lines wrapped at $\le 80$
     columns.
   * Include clear positive triggers (`Use when...`) and negative guardrails
     (`Don't use for...`).
   * Include a single H1 header matching the skill title.

3. **Scripts & Companion Tests**:
   * Place executable helpers in `<skill-name>/scripts/`.
   * Write a sibling companion test (`*_test.py`) for every script.
   * Verify all tests pass standalone: `python3 <skill-name>/scripts/*_test.py`.

4. **Evaluations Suite**:
   * Create `<skill-name>/evals/evals.json` conforming to Claude schema.
   * Implement `<skill-name>/evals/run_eval.py` supporting dry-run verification.
   * Write companion test `<skill-name>/evals/run_eval_test.py`.

5. **Standalone Pre-Commit Configuration**:
   * Add `<skill-name>/.pre-commit-config.yaml` declaring standalone lint,
     pyright, markdownlint, and companion test hooks so the skill can be
     tested independently when cloned as a standalone repository.

6. **Regenerate Catalog**:
   * Run `python3 .github/scripts/generate_readme.py`.
   * Verify output: `python3 .github/scripts/generate_readme.py --check`.

7. **Audit Skill Compliance**:
   * Run `python3 authoring-skills/scripts/audit_skill.py <skill-name>`.
   * Fix any reported errors or warnings until the audit reports 100% clean.

8. **Execute Pre-Commit Gate**:
   * Run `uvx pre-commit run --all-files`.
   * Confirm all quality hooks pass green before committing.

---

## 4. Command Cheat Sheet

### Run Quality Gates

```bash
# Run all pre-commit hooks across all files
uvx pre-commit run --all-files

# Type checking
uvx pyright .

# Linting & formatting
uvx ruff check .
uvx ruff format --check .

# Markdown linting
markdownlint --config writing-markdown/.markdownlint.json **/*.md

# ASCII hygiene
python3 writing-markdown/scripts/lint_ascii.py **/*.md
```

### Run Skill Companion Tests

```bash
# Run companion tests for a specific skill (example: controlling-tmux)
python3 controlling-tmux/scripts/relative_pane_test.py
python3 controlling-tmux/scripts/dispatch_agent_test.py
python3 controlling-tmux/evals/run_eval_test.py

# Run companion tests dynamically across affected skills
python3 .github/scripts/run_skill_tests.py [modified_files...]

# Run companion tests across all skills
python3 .github/scripts/run_skill_tests.py --all

# Run .github tooling tests
python3 .github/scripts/generate_readme_test.py
python3 .github/scripts/run_skill_tests_test.py
```

### Run Skill Audits & Catalog

```bash
# Audit specific skill
python3 authoring-skills/scripts/audit_skill.py <skill-name>

# Regenerate catalog README.md
python3 .github/scripts/generate_readme.py

# Check catalog sync
python3 .github/scripts/generate_readme.py --check
```

---

## 5. Git Commit & Release Conventions

* **Conventional Commits**: Format commits as `<type>(<scope>): <summary>` in
  imperative present tense (e.g. `feat(controlling-tmux): add agent dispatch`).
* **Atomic Scope**: One logical change per commit. Never mix refactoring with
  formatting or new features.
* **Pre-Commit Gate**: Never bypass git hooks (`--no-verify`).
* **Remote Invariants**: Always verify `git status` and `git diff` before
  pushing to `origin/main`.
