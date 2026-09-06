# Python Tooling & Testing Discipline Guide

Workflows for package initialization, dependency-free script execution, testing
discipline, and pre-commit automation using `uv`.

---

## 1. Project Initialization with `uv`

When initializing a new Python directory or skill package, use `uv init` with
flags that prevent repo clutter:

```bash
uv init --bare --no-readme --vcs none [DIR_NAME]
```

- `--bare`: Only creates `pyproject.toml` (avoids dummy `hello.py` or `.venv`).
- `--no-readme`: Prevents creating a dummy `README.md` that conflicts with
  existing documentation or `SKILL.md`.
- `--vcs none`: Prevents spawning unwanted nested `.git` repositories.

---

## 2. Canonical `pyproject.toml` Configuration

Every repository or skill containing Python code should include a
`pyproject.toml` configuring Ruff with Google-style docstring enforcement:

```toml
[project]
name = "my-project"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = []

[tool.ruff]
target-version = "py311"
line-length = 88

[tool.ruff.lint]
select = [
    "E",      # pycodestyle errors
    "F",      # pyflakes
    "W",      # pycodestyle warnings
    "I",      # isort
    "UP",     # pyupgrade
    "B",      # flake8-bugbear
    "D",      # pydocstyle
    "BLE",    # flake8-blind-except
    "PLW",    # pylint warnings
    "ERA001", # eradicate commented-out dead code
]
ignore = [
    "E501",   # Line length handled by ruff format
]

[tool.ruff.lint.pydocstyle]
convention = "google"

[tool.ruff.lint.per-file-ignores]
"*_test.py" = ["D100", "D101", "D102", "D103"]
```

---

## 3. PEP 723 Inline Script Metadata

Every standalone, executable Python script MUST declare its metadata and
dependencies in a [PEP 723](https://peps.python.org/pep-0723/) block directly
beneath the shebang:

```python
#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Module docstring describing script functionality."""
```

### Why PEP 723 is Mandatory

1. **Zero Virtualenv Setup**: Anyone can execute the script using
   `uv run script.py` without needing manual `venv` creation or `pip install`.
2. **Deterministic Isolation**: `uv` provisions an ephemeral, cached environment
   in milliseconds and executes the script hermetically.

---

## 4. Mandatory Companion Unit Tests

**The Rule**: Every Python file or CLI tool MUST have a companion unit test.

- Sibling convention: `scripts/tool.py` -> `scripts/tool_test.py`.
- Test files MUST be self-contained and run cleanly via standard library
  `unittest`:

  ```python
  import sys
  import unittest
  from pathlib import Path

  # Ensure sibling script can be imported directly
  sys.path.insert(0, str(Path(__file__).resolve().parent))
  ```

- Execution command:

  ```bash
  uv run python3 scripts/tool_test.py
  ```

---

## 5. Pre-Commit Configuration

Every repository or skill containing Python code MUST wire test and style gates
into `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: local
    hooks:
      - id: ruff-check
        name: Lint Python with ruff check
        entry: uvx ruff check .
        language: system
        types: [python]
        pass_filenames: false

      - id: ruff-format
        name: Check Python formatting with ruff format
        entry: uvx ruff format --check .
        language: system
        types: [python]
        pass_filenames: false

      - id: pyright-check
        name: Check Python types with pyright
        entry: uvx pyright .
        language: system
        types: [python]
        pass_filenames: false

      - id: python-tests
        name: Run Python unit tests
        entry:
          sh -c 'python3 scripts/tool_test.py && python3 evals/run_eval_test.py'
        language: system
        types: [python]
        pass_filenames: false
```
