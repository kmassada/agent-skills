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
├── .github/scripts/           # Automated catalog generator & CI tooling
├── rules/                     # Repository-level agent behavioral rules
├── authoring-skills/          # Skill creation & auditing standards
├── controlling-tmux/          # Terminal multiplexer control & agent dispatch
├── sharing-snips/             # Screenshot capture & cloud sharing
├── writing-markdown/          # Markdown linting & formatting standards
├── writing-python/            # Python typing, Ruff, & testing discipline
├── .pre-commit-config.yaml    # 16 automated quality gates
├── AGENTS.md                  # This operational playbook
└── README.md                  # Generated catalog (DO NOT EDIT MANUALLY)
```

Each skill directory (`<skill-name>/`) contains:

* `SKILL.md`: Lean operational runbook and dispatch document.
* `scripts/`: Production utilities with companion unit tests (`*_test.py`).
* `evals/`: Claude-conforming `evals.json`, `run_eval.py`, and `run_eval_test.py`.
* `references/`: In-depth guides and architectural references.
* `pyproject.toml` / `.markdownlint.json`: Isolated tool configurations.

---

## 2. Core Repository Invariants

Every agent working in this monorepo must respect these non-negotiable gates:

### A. Scoped Pre-Commit Test Hooks

In `.pre-commit-config.yaml`, companion unit tests are scoped per skill
directory using regex path filters:

```yaml
- id: controlling-tmux-tests
  name: Run controlling-tmux companion tests
  entry: sh -c 'python3 controlling-tmux/scripts/... && python3 controlling-tmux/evals/...'
  language: system
  files: ^controlling-tmux/
  pass_filenames: false
```

* **Rule**: When adding or editing a skill, register or update its companion test
  hook in `.pre-commit-config.yaml`.
* **Reason**: Prevents running test suites for untouched skills during focused
  feature development while still guaranteeing full repository coverage.

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

5. **Register Scoped Pre-Commit Hook**:
   * Add `<skill-name>-tests` to `.pre-commit-config.yaml` with
     `files: ^<skill-name>/`.

6. **Regenerate Catalog**:
   * Run `python3 .github/scripts/generate_readme.py`.
   * Verify output: `python3 .github/scripts/generate_readme.py --check`.

7. **Audit Skill Compliance**:
   * Run `python3 authoring-skills/scripts/audit_skill.py <skill-name>`.
   * Fix any reported errors or warnings until the audit reports 100% clean.

8. **Execute Pre-Commit Gate**:
   * Run `uvx pre-commit run --all-files`.
   * Confirm all 15+ hooks pass green before committing.

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
# Markdown tests
python3 writing-markdown/scripts/lint_ascii_test.py
python3 writing-markdown/evals/run_eval_test.py

# Python tests
python3 writing-python/scripts/check_python_test.py
python3 writing-python/evals/run_eval_test.py

# Authoring skills tests
python3 authoring-skills/scripts/audit_skill_test.py
python3 authoring-skills/evals/run_eval_test.py

# Tmux control tests
python3 controlling-tmux/scripts/relative_pane_test.py
python3 controlling-tmux/scripts/dispatch_agent_test.py
python3 controlling-tmux/evals/run_eval_test.py

# Sharing snips tests
python3 sharing-snips/scripts/test_quota_guard.py
python3 sharing-snips/scripts/test_snip.py

# Catalog generator tests
python3 .github/scripts/generate_readme_test.py
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
