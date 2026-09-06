---
trigger: glob
globs: "*.py"
description: "Open-source Python standards, static typing, companion testing, and tooling"
---

# Writing Python (writing-python)

Whenever authoring, editing, or auditing Python (`.py`) files, adhere to the
standards defined in the [`writing-python`][writing-python-skill] skill:

* **Typing Interfaces**: Function arguments MUST accept abstract interfaces from
  `collections.abc` (`Sequence[T]`, `Mapping[K, V]`, `Iterable[T]`) rather than
  rigid concrete types like `list` or `dict`.
* **Zero Type Errors**: Every module must pass static type checking with zero
  errors using `uvx pyright .`.
* **Formatting & Linting**: Adhere to PEP 8 and verify zero lint errors with
  `uvx ruff check .` and `uvx ruff format --check .`.
* **Companion Unit Tests**: Every script or module must have a companion unit
  test using standard library `unittest`, practicing hermetic test sandboxing
  and narrow mocking.
* **Deterministic Execution**: Standalone scripts must declare PEP 723 metadata
  and execute via `uv run`.
* **Authoritative Reference**: Review the complete skill and reference guides
  in [`writing-python/SKILL.md`][writing-python-skill].

[writing-python-skill]: https://github.com/kmassada/agent-skills/blob/main/writing-python/SKILL.md
