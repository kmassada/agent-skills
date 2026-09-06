# Agent Skills

A standardized suite of cross-platform skills for AI coding agents, fully
compatible with both **Google Antigravity** and **Anthropic Claude Code**.

---

## Catalog (<!-- SKILLS_COUNT --> Skills)

<!-- SKILLS_TABLE -->

---

## Skill Breakdown

<!-- SKILLS_DETAILS -->

---

## Architectural Principles

Every skill in this repository follows the strict architectural guidelines
codified in [`authoring-skills`](authoring-skills/SKILL.md) and
[`writing-markdown`](writing-markdown/SKILL.md):

- **Cross-Platform Compatibility**: Fully functional in both Google
  Antigravity (`agy`) and Anthropic Claude Code (`claude`).
- **Primary Dispatcher Pattern**: Top-level `SKILL.md` is lean (<100 lines) and
  acts as a dispatcher to focused guides in `references/`.
- **Automated Evaluations**: Every skill contains benchmark scenarios defined
  in `evals/evals.json` run via deterministic test harnesses.
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
