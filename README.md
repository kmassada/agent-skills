# Agent Skills

A standardized suite of cross-platform skills for AI coding agents, fully
compatible with both **Google Antigravity** and **Anthropic Claude Code**.

---

## Catalog (3 Skills)

| Skill                                           | Summary                                                                                 | Components                       |
| :---------------------------------------------- | :-------------------------------------------------------------------------------------- | :------------------------------- |
| [`authoring-skills`](authoring-skills/SKILL.md) | Guides the creation, structuring, formatting, evaluating, and auditing of agent skills. | `references`                     |
| [`tmux-control`](tmux-control/SKILL.md)         | Manages tmux terminal sessions, windows, and panes.                                     | `references`, `evals`, `scripts` |
| [`writing-markdown`](writing-markdown/SKILL.md) | Guides writing and formatting clean, lint-compliant Markdown documents.                 | `references`, `evals`, `scripts` |

---

## Skill Breakdown

### [`authoring-skills`](authoring-skills/SKILL.md)

> Guides the creation, structuring, formatting, evaluating, and auditing of
> agent skills. Use when authoring new skills, editing SKILL.md files, designing
> eval suites, or reviewing skills for anti-patterns. Don't use for generic
> application programming or non-agent repository workflows.

- **Directory**: [`authoring-skills/`](authoring-skills/)
- **References**:
  - [`ANTI_PATTERNS.md`](authoring-skills/references/ANTI_PATTERNS.md)
  - [`DESIGN_PRINCIPLES.md`](authoring-skills/references/DESIGN_PRINCIPLES.md)
  - [`EVAL_SCHEMAS.md`](authoring-skills/references/EVAL_SCHEMAS.md)
  - [`FORMAT.md`](authoring-skills/references/FORMAT.md)

### [`tmux-control`](tmux-control/SKILL.md)

> Manages tmux terminal sessions, windows, and panes. Capable of creating
> windows, splitting panes (horizontal/vertical/full-width), sending commands to
> specific panes, quietly capturing pane outputs without stealing user focus,
> navigating adjacent panes directionally (left/right/above/under), and handling
> long-running background tasks. Triggers on phrases like 'run this in tmux',
> 'split pane on the right', 'create window', 'what is in pane %2', 'focus pane
> below', or 'send command to pane'.

- **Directory**: [`tmux-control/`](tmux-control/)
- **Evaluations**: [`evals.json`](tmux-control/evals/evals.json)
- **References**:
  [`GEOMETRIC_NAVIGATION.md`](tmux-control/references/GEOMETRIC_NAVIGATION.md)
- **Scripts**:
  - [`relative_pane.py`](tmux-control/scripts/relative_pane.py)
  - [`relative_pane_test.py`](tmux-control/scripts/relative_pane_test.py)

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
