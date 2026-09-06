---
name: writing-markdown
description: >-
  Guides writing and formatting clean, lint-compliant Markdown documents. Use
  when authoring or editing READMEs, documentation, runbooks, or SKILL.md files,
  especially to satisfy VS Code markdownlint rules like MD032 (blanks around
  lists), MD031 (blanks around code blocks), and basic ASCII hygiene. Don't use
  for plain text or generic chat responses.
---

# Writing Markdown

This skill standardizes how to write, format, and structure clean, readable, and
strictly lint-compliant Markdown documents. It adheres to GitHub-Flavored
Markdown (GFM) and standard `markdownlint` rules enforced by VS Code extensions
and CI quality gates.

> [!NOTE] **Primary Dispatcher**
>
> Consult the table below for deep rule references and copy-paste snippets:
>
> - [MARKDOWNLINT_RULES.md](./references/MARKDOWNLINT_RULES.md): Exhaustive
>   breakdown of markdownlint rules (`MD032`, `MD022`, `MD031`, etc.).
> - [CHEATSHEET.md](./references/CHEATSHEET.md): Ready-to-copy patterns for
>   nested code blocks, tables, and callouts.

---

## Core Spacing & Structural Rules

When generating or editing any Markdown document, strictly enforce these rules:

### 1. Lists & Blank Lines (MD032)

- **Always insert a blank line before and after any list** (bulleted or
  ordered).
- **The Colon Rule:** If a line ends with a colon (`:`) and introduces a list,
  you **MUST** insert an empty line between the colon line and the first list
  item. Omission causes `MD032` lint errors and text collapsing in Markdown
  parsers.
- Standardize on asterisks (`*`) for unordered bullet items.

### 2. Headings & Hierarchy (MD022, MD001, MD026)

- **Surround all headings with blank lines:** Exactly one blank line before and
  one blank line after every heading (`#`, `##`, `###`). Never place text or
  lists directly on the line following a heading.
- **Sequential Increment:** Increment headings by exactly 1 level at a time
  (e.g., `#` -> `##` -> `###`). Never skip levels.
- **No Trailing Punctuation:** Never end headings with colons (`:`), periods, or
  exclamation marks.

### 3. Fenced Code Blocks (MD031, MD040)

- **Surround all code blocks with blank lines:** Blank line before the opening
  fence and blank line after the closing fence.
- **Always Declare Language:** Every code block must declare a language
  identifier (e.g., `bash`, `python`, `yaml`, `text`).

### 4. Nesting Code Blocks inside Lists

To place a code block inside a numbered or bulleted list without breaking list
numbering:

1. Insert a blank line after the list item's text.
2. Indent the code block (the triple backticks and all code lines) by **4
   spaces**.
3. Insert a blank line before the next list item.

### 5. Command Line Continuation

- Long CLI commands must be broken across multiple lines using a trailing
  backslash (`\`).
- Break lines before flags (e.g., `--flag`) or pipes (`|`).
- Indent continuation lines by 2 spaces.

### 6. Callouts & Alerts

- Use GitHub-Flavored Markdown alert syntax:

  ```markdown
  > [!NOTE] Informational context or rationale.

  > [!WARNING] Critical instructions or breaking changes.
  ```

- Always surround callout blocks with an empty blank line before and after.

### 7. Basic ASCII & Unicode Hygiene (Anti-Unicode-Highlight)

- **Avoid Non-Basic ASCII Characters:** Do not use special Unicode symbols or
  glyphs that trigger VS Code `editor.unicodeHighlight` warnings.
- **Prompts:** Use standard ASCII `$` or `>` (never Unicode prompt glyphs like
  U+276F).
- **Quotes:** Use straight quotes (`'` and `"`) instead of curved or smart
  quotes.
- **Dashes & Ranges:** Use ASCII hyphens for ranges (e.g., `1-2s` instead of
  en-dash `U+2013`), and `--` instead of em-dashes (`U+2014`).
- **Arrows:** Use `->` or `-->` instead of Unicode arrows (`U+2192`).
- **Bullets:** Use standard ASCII asterisks (`*`) or hyphens (`-`) instead of
  Unicode bullet points.
- **Box-Drawing Exception:** Standard Unicode box-drawing characters (`├──`,
  `└──`, `│`, `─`) inside fenced code blocks are explicitly allowlisted for file
  trees and architectural diagrams.

---

## Mandatory Post-Write Execution Loop

Whenever generating or modifying any Markdown file, the agent **MUST** execute
this two-step formatting and lint verification sequence:

1. **Hard-wrap prose at 80 characters and format layout with Prettier:**

   ```bash
   npx prettier --write --prose-wrap always --print-width 80 <path_to_file.md>
   ```

2. **Auto-fix markdown spacing and enforce 80-character line limits:**

   ```bash
   markdownlint --fix <path_to_file.md>
   ```

3. **Verify zero remaining lint errors before completing the turn:**

   ```bash
   markdownlint <path_to_file.md>
   ```
