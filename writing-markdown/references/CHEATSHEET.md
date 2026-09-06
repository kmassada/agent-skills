# Markdown Formatting Cheat Sheet

Use these clean, lint-verified snippets when constructing Markdown documents.

---

## 1. List Preceded by Colon & Paragraph (MD032 Compliant)

Always place an empty line between a colon-terminated lead-in and the list:

```markdown
To start the services, verify the following prerequisites:

- Docker engine 24.0+ is running
- Port 8080 is available
- Configuration file exists at `config.yaml`

Once verified, continue to initialization.
```

---

## 2. Code Block Nested inside a List Item

To embed a code block within a list item without breaking list continuity:

````markdown
1. Install dependencies:

   ```bash
   npm install
   ```

2. Start the development server:

   ```bash
   npm run dev
   ```
````

_Note: The blank line above the code block and the 4-space indentation on the
backticks and code lines prevent lint errors and renderer squashing._

---

## 3. Command Line Continuation (`\`)

For long shell commands, break lines before flags and pipes, indenting
continuations by 2 spaces:

```bash
docker run -d \
  --name web-server \
  --publish 8080:80 \
  --restart unless-stopped \
  nginx:alpine
```

---

## 4. GitHub-Flavored Callouts / Alerts

Surround callout blocks with blank lines before and after:

```markdown
> [!NOTE] Explains background context, non-obvious design rationale, or tips.

> [!WARNING] Highlights critical prerequisites, breaking changes, or dangerous
> operations.
```

---

## 5. Clean Markdown Table

Align columns clearly with consistent spacing:

| Command      | Target         | Description                        |
| :----------- | :------------- | :--------------------------------- |
| `git status` | Working Tree   | Shows modified and untracked files |
| `git diff`   | Staged Changes | Displays uncommitted line changes  |
