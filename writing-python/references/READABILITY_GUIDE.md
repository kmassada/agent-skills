# Python Readability & Clean Code Guide

Standards for open-source Python readability, style conventions, static
analysis, and runtime safety.

---

## 1. Core OSS Standards & Linters

All Python code must strictly pass the standard open-source toolchain:

- **[PEP 8 Style Guide](https://peps.python.org/pep-0008/)**: The canonical
  standard for Python style, layout, naming, and whitespace.
- **[Ruff Linter & Formatter](https://docs.astral.sh/ruff/)**: The modern,
  blazing-fast Rust linter and code formatter.
- **[Pyright / Pylance](https://microsoft.github.io/pyright/)**: Static type
  checker enforcing strict typing and contract correctness.

### Mandatory Verification Commands

```bash
# Check code for style, deprecations, and bug patterns
uvx ruff check .

# Check code for canonical formatting
uvx ruff format --check .

# Automatically apply safe style fixes and reformatting
uvx ruff format .
uvx ruff check --fix .

# Verify static typing with Pyright
uvx pyright .
```

---

## 2. Exception Handling Discipline

Never write blind or bare exception handlers:

```python
# BANNED: Swallows KeyboardInterrupt, SystemExit, and masks bugs
try:
    content = path.read_text()
except Exception:
    pass

# REQUIRED: Catch specific, expected failure modes
try:
    content = path.read_text(encoding="utf-8")
except (OSError, UnicodeDecodeError) as e:
    print(f"Error reading {path}: {e}", file=sys.stderr)
    return None
```

---

## 3. Subprocess Safety (PLW1510)

Whenever calling `subprocess.run()`, you MUST explicitly declare the `check`
behavior:

```python
import subprocess

# Explicit check=False when exit codes are handled manually
proc = subprocess.run(["git", "status"], capture_output=True, text=True, check=False)
if proc.returncode != 0:
    print("Git repository not clean")

# Explicit check=True when failure should raise an exception immediately
subprocess.run(["mkdir", "-p", "output"], check=True)
```

---

## 4. Script & Shebang Hygiene

- **Executable Permissions (EXE001)**: If a Python script includes a shebang
  line (`#!/usr/bin/env python3`), it MUST have executable file permissions:

  ```bash
  chmod +x path/to/script.py
  ```

- **Encoding**: Always specify `encoding="utf-8"` when calling
  `pathlib.Path.read_text()` or `open()`.
- **Standard Indentation**: 4 spaces per indentation level (never tabs).

---

## 5. Comment Hygiene: Explain "Why", Never "What"

PEP 8 is explicitly critical of useless comments, warning that:

> _"Inline comments are unnecessary and in fact distracting if they state the
> obvious. Comments that contradict the code are worse than no comments."_

### The Golden Rules of Python Comments

1. **Explain "Why", Not "What"**: Code should be self-documenting regarding
   _what_ it does. Comments are reserved for explaining _why_ a particular,
   non-obvious decision was made.
2. **Never Mechanically Narrate Code**: Delete comments that merely restate
   Python syntax in English.
3. **Refactor Obscure Code Before Commenting**: If code is unclear, extract a
   well-named function or variable rather than attaching an explanatory comment.
4. **No Commented-Out Dead Code (ERA001)**: Never leave commented-out dead code
   blocks in files. Use Git history for version retrieval.

### Anti-Patterns vs Good Practice

```python
# BAD: States the obvious (mechanical narration)
count = count + 1  # Increment count
for item in items:  # Loop over items
    process(item)

# GOOD: Explains non-obvious context or algorithmic intent
count = count + 1  # Compensate for 1-based indexing in external API
for item in items:  # Process sequentially to prevent rate-limit throttling
    process(item)

# BAD: Compensating for poor variable naming
d = 86400  # seconds in a day

# GOOD: Self-documenting identifier
SECONDS_PER_DAY = 86400
```

---

## 6. Google-Style Docstrings (PEP 257 + Google Convention)

Python code should use Google-style docstrings, validated deterministically by
Ruff using `[tool.ruff.lint.pydocstyle] convention = "google"`.

### Core Rules for Google Docstrings

1. **One-Line Docstrings**: Use when a function's purpose and return are
   obvious.
   ```python
   def is_empty(seq: Sequence[object]) -> bool:
       """Returns True if the sequence contains zero elements."""
       return len(seq) == 0
   ```
2. **Multi-Line Docstrings**: Begin with a 1-line summary ending with a period,
   followed by a blank line, optional detailed description, and sections:
   `Args:`, `Returns:`, and `Raises:`.
3. **Never Duplicate Type Annotations**: Types belong in the function signature
   (`arg: str -> int`), NOT in `Args:` or `Returns:`. Duplicating types violates
   DRY and drifts out of date.
4. **When to Include `Args:` and `Returns:`**: Include them when parameters have
   constraints (e.g. units `ms`, range `0.0 <= x <= 1.0`), edge-case behaviors
   (sentinel `None`), or side effects.

### Example: Proper Google-Style Docstring

```python
def fetch_records(
    query: str,
    limit: int = 100,
    timeout_ms: int = 5000,
) -> list[Record]:
    """Retrieves database records matching the specified query filter.

    Args:
        query: SQL or search filter string.
        limit: Maximum number of rows to return (must be positive).
        timeout_ms: Execution deadline in milliseconds.

    Returns:
        List of deserialized Record instances.

    Raises:
        TimeoutError: If query execution exceeds timeout_ms.
        ValueError: If limit is less than 1.
    """
    ...
```
