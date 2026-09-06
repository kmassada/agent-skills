---
name: writing-python
description: >-
  Enforces modern, idiomatic Python standards, static typing with
  collections.abc and Pylance/Pyright, open-source readability via Ruff and PEP
  8, deterministic execution with uv and PEP 723, companion test discipline, and
  pre-commit test automation. Use when authoring or editing Python scripts,
  adding type annotations, configuring linters, writing unit tests, or
  initializing projects. Don't use for non-Python application programming.
---

# Writing Python

This skill standardizes how to write, format, type-check, test, and package
clean, robust, and idiomatic Python code. It enforces strict compliance with
modern static typing, open-source style guides, and fast development workflows.

> [!NOTE] **Primary Dispatcher**
>
> Consult the table below for dedicated reference guides on typing contracts,
> style rules, testing discipline, and `uv` automation:

---

## Reference Guide Directory

| Task / Domain                  | Guide                                                     | Key Topics & Tools                                     |
| :----------------------------- | :-------------------------------------------------------- | :----------------------------------------------------- |
| **Static Typing & Interfaces** | [`TYPING_GUIDE.md`](references/TYPING_GUIDE.md)           | `collections.abc`, `Pylance`, `Pyright`, PEP 604       |
| **Style & Readability**        | [`READABILITY_GUIDE.md`](references/READABILITY_GUIDE.md) | `PEP 8`, `Ruff check`, `Ruff format`, Exception safety |
| **Tooling, Testing & CI**      | [`TOOLING_GUIDE.md`](references/TOOLING_GUIDE.md)         | `uv init`, `uv run`, `PEP 723`, `unittest`, Pre-commit |

---

## Core Rules & Non-Negotiables

1. **Always Use `collections.abc` for Typing**: Function arguments MUST accept
   abstract interfaces (`Sequence[T]`, `Mapping[K, V]`, `Iterable[T]`) from
   [`collections.abc`](https://docs.python.org/3/library/collections.abc.html)
   rather than rigid concrete types like `list` or `dict`.
2. **Zero Pylance / Pyright Errors**: Every Python module MUST pass static type
   checking via [`pyright`](https://microsoft.github.io/pyright/) with zero
   errors:

   ```bash
   uvx pyright .
   ```

3. **OSS Readability with Ruff**: All files must strictly obey
   [`PEP 8`](https://peps.python.org/pep-0008/) and pass
   [`Ruff`](https://docs.astral.sh/ruff/):

   ```bash
   uvx ruff check . && uvx ruff format --check .
   ```

4. **Mandatory Companion Unit Tests**: Every Python file or CLI tool MUST have a
   companion unit test (e.g. `scripts/tool_test.py`) using standard library
   `unittest`.
5. **Deterministic Script Execution via `uv`**: Standalone scripts MUST declare
   [PEP 723](https://peps.python.org/pep-0723/) inline metadata and execute via
   `uv run`.
6. **Strict Comment Hygiene (PEP 8)**: Comments MUST explain _why_, never
   _what_. Never write comments that mechanically narrate code syntax, and never
   commit commented-out dead code.
7. **Google-Style Docstrings (`pydocstyle`)**: Configure Ruff with
   `[tool.ruff.lint.pydocstyle] convention = "google"` and select `"D"`. Public
   modules, classes, and functions must have docstrings. Document `Args:`,
   `Returns:`, and `Raises:` for non-trivial logic, and never duplicate type
   annotations in the docstring.
