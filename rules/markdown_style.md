---
trigger: glob
globs: "*.md,*.markdown"
description: "Markdown formatting, markdownlint compliance, spacing rules, and ASCII hygiene"
---

# Writing Markdown (writing-markdown)

Whenever authoring or modifying Markdown documents, adhere to the standards
defined in the [`writing-markdown`][writing-markdown-skill] skill:

* **Lists & Blank Lines (MD032)**: Always surround lists with blank lines.
  When introducing a list after a line ending with a colon (`:`), insert a
  blank line before the first bullet. Standardize on `*` for unordered lists.
* **Headings & Hierarchy (MD022, MD026)**: Surround headings with blank lines.
  Never end headings with punctuation (`:`, `.`, `!`). Increment heading levels
  sequentially without skipping levels.
* **Code Fences (MD031, MD040)**: Surround code blocks with blank lines and
  always specify a language tag.
* **ASCII Hygiene**: Use standard ASCII characters (`$`, `>`, `->`, `'`, `"`,
  `--`). Avoid smart quotes, unicode arrows, or special symbols that trigger
  VS Code unicodeHighlight warnings.
* **Verification**: Format prose at 80 characters and verify zero lint errors
  using `markdownlint --fix <file>` followed by `markdownlint <file>`.
* **Authoritative Reference**: Review the complete skill and rule breakdowns in
  [`writing-markdown/SKILL.md`][writing-markdown-skill].

[writing-markdown-skill]: https://github.com/kmassada/agent-skills/blob/main/writing-markdown/SKILL.md
