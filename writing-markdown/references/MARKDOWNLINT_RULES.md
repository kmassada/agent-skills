# Markdownlint Rules Reference

This document details the standard `markdownlint` rules enforced by VS Code
extensions (DavidAnson.markdownlint) and CI lint runners (`markdownlint-cli`),
along with the exact patterns required to satisfy them.

---

## 1. Core Spacing Rules

### MD032: Blanks Around Lists (`blanks-around-lists`)

- **The Rule:** Every list (ordered or unordered) must be preceded and followed
  by at least one blank line.
- **Why it matters:** Without a preceding blank line, CommonMark and GFM parsers
  treat list items as continuation text of the preceding paragraph.
- **Common Trigger:** Lines ending with a colon (`:`) immediately followed by a
  bullet on the next line.
- **Bad:**

  ```text
  Prerequisites:
  * Node.js 18+
  * Python 3.11+
  ```

- **Good:**

  ```text
  Prerequisites:

  * Node.js 18+
  * Python 3.11+
  ```

---

### MD022: Blanks Around Headings (`blanks-around-headings`)

- **The Rule:** Headings (`#`, `##`, `###`, etc.) must have exactly one blank
  line before them and one blank line after them.
- **Exception:** Headings at the very beginning of the document do not require a
  preceding blank line.
- **Bad:**

  ```text
  ## Installation
  Run the command below.
  ```

- **Good:**

  ```text
  ## Installation

  Run the command below.
  ```

---

### MD031: Blanks Around Fences (`blanks-around-fences`)

- **The Rule:** Fenced code blocks must be preceded and followed by an empty
  blank line.
- **Bad Example:** Placing code blocks adjacent to text lines without separating
  blank lines:

  ````text
  Run this command:
  ```bash
  git status
  ```
  Check the output.
  ````

- **Good Example:**

  ````text
  Run this command:

  ```bash
  git status
  ```

  Check the output.
  ````

---

### MD012: No Multiple Consecutive Blank Lines (`no-multiple-blanks`)

- **The Rule:** Do not use more than one consecutive blank line anywhere in the
  document.
- **Good:** Always separate paragraphs, headers, and blocks with exactly a
  single blank line.

---

### MD009: No Trailing Spaces (`no-trailing-spaces`)

- **The Rule:** Do not leave whitespace characters at the end of lines.
- **Exception:** If using two trailing spaces for manual line breaks, prefer
  explicit HTML `<br>` or separate paragraphs to prevent accidental lint
  failures.

---

## 2. Heading & Hierarchy Rules

### MD001: Heading Increment (`heading-increment`)

- **The Rule:** Heading levels should increment by only one level at a time.
- **Bad:** `# Title` followed directly by `### Sub-section` (skipping `##`).
- **Good:** `# Title` -> `## Major Section` -> `### Sub-section`.

---

### MD025: Single Top-Level Heading (`single-title`)

- **The Rule:** A document should have exactly one top-level `# Title` heading
  (or start with YAML frontmatter followed by a single `# Title`).

---

### MD026: No Trailing Punctuation in Headings (`no-trailing-punctuation`)

- **The Rule:** Headings must not end with punctuation marks such as colons
  (`:`), periods (`.`), or exclamation marks (`!`).
- **Bad:** `## Setup Instructions:`
- **Good:** `## Setup Instructions`

---

## 3. Code Block & List Rules

### MD040: Fenced Code Language (`fenced-code-language`)

- **The Rule:** Fenced code blocks must always declare a syntax/language
  identifier.
- **Valid Identifiers:** `bash`, `python`, `json`, `yaml`, `markdown`, `sql`,
  `text` (for generic output).
- **Bad:** Empty triple backticks with no language tag.
- **Good:** Triple backticks with `bash` or `text`.

---

### MD007 / MD005: List Indentation & Nesting

- **The Rule:** List items must use consistent indentation.
- **Nesting in Lists:** Indent child list items by 2 or 4 spaces consistently.
- **Nesting Code Blocks in Lists:**
  1. Insert a blank line after the list item text.
  2. Indent the opening backticks, code content, and closing backticks by **4
     spaces** to align with the list text.

- **Example:**

  ````text
  1. Prepare the configuration file:

      ```bash
      cp config.example.json config.json
      ```

  2. Verify the installation.
  ````

---

### MD029: Ordered List Prefix (`ordered-list-marker`)

- **The Rule:** Ordered list numbers should increment sequentially (`1.`, `2.`,
  `3.`) unless a 1-based prefix configuration (`1.`, `1.`, `1.`) is explicitly
  configured in project lint settings.
