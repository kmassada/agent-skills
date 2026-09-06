# Agent Skills

A standardized suite of cross-platform skills for AI coding agents, fully
compatible with both **Google Antigravity** and **Anthropic Claude Code**.

---

## Catalog (2 Skills)

| Skill                                           | Summary                                                                                                                                                                                                                                                  | Components                       |
| :---------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :------------------------------- |
| [`writing-markdown`](writing-markdown/SKILL.md) | Guides writing and formatting clean, lint-compliant Markdown documents.                                                                                                                                                                                  | `references`, `evals`, `scripts` |
| [`writing-python`](writing-python/SKILL.md)     | Enforces modern, idiomatic Python standards, static typing with collections.abc and Pylance/Pyright, open-source readability via Ruff and PEP 8, deterministic execution with uv and PEP 723, companion test discipline, and pre-commit test automation. | `references`, `evals`, `scripts` |

---

## Skill Breakdown

### [`writing-markdown`](writing-markdown/SKILL.md)

> Guides writing and formatting clean, lint-compliant Markdown documents. Use
> when authoring or editing READMEs, documentation, runbooks, or SKILL.md files,
> especially to satisfy VS Code markdownlint rules like MD032 (blanks around
> lists), MD031 (blanks around code blocks), and basic ASCII hygiene. Don't use
> for plain text or generic chat responses.

- **Directory**: [`writing-markdown/`](writing-markdown/)
- **Evaluations**: [`evals.json`](writing-markdown/evals/evals.json)
- **References**:
  - [`CHEATSHEET.md`](writing-markdown/references/CHEATSHEET.md)
  - [`MARKDOWNLINT_RULES.md`](writing-markdown/references/MARKDOWNLINT_RULES.md)
- **Scripts**: [`lint_ascii.py`](writing-markdown/scripts/lint_ascii.py)

### [`writing-python`](writing-python/SKILL.md)

> Enforces modern, idiomatic Python standards, static typing with
> collections.abc and Pylance/Pyright, open-source readability via Ruff and PEP
> 8, deterministic execution with uv and PEP 723, companion test discipline, and
> pre-commit test automation. Use when authoring or editing Python scripts,
> adding type annotations, configuring linters, writing unit tests, or
> initializing projects. Don't use for non-Python application programming.

- **Directory**: [`writing-python/`](writing-python/)
- **Evaluations**: [`evals.json`](writing-python/evals/evals.json)
- **References**:
  - [`READABILITY_GUIDE.md`](writing-python/references/READABILITY_GUIDE.md)
  - [`TOOLING_GUIDE.md`](writing-python/references/TOOLING_GUIDE.md)
  - [`TYPING_GUIDE.md`](writing-python/references/TYPING_GUIDE.md)
- **Scripts**: [`check_python.py`](writing-python/scripts/check_python.py)

---

## Architectural Principles

Every skill in this repository follows the strict architectural guidelines
codified in [`authoring-skills`](authoring-skills/SKILL.md) and
[`writing-markdown`](writing-markdown/SKILL.md):

- **Cross-Platform Compatibility**: Fully functional in both Google Antigravity
  (`agy`) and Anthropic Claude Code (`claude`).
- **Primary Dispatcher Pattern**: Top-level `SKILL.md` is lean (<100 lines) and
  acts as a dispatcher to focused guides in `references/`.
- **Automated Evaluations**: Every skill contains benchmark scenarios defined in
  `evals/evals.json` run via deterministic test harnesses.
- **Strict Formatting**: 80-character maximum line length (`MD013`), blank line
  fencing (`MD031`, `MD032`), and basic ASCII hygiene.

---

## Updating This Catalog

To regenerate `README.md` after adding, updating, or removing skills:

```bash
python3 .github/scripts/generate_readme.py
```

To verify whether `README.md` is in sync (useful in CI or pre-commit hooks):

```bash
python3 .github/scripts/generate_readme.py --check
```
