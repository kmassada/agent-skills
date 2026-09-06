# Python Modern Typing Guide

Standards for static typing in modern Python (3.10+), strictly enforcing
Pylance/Pyright compliance and standard library abstractions.

---

## 1. The Core Principle: Abstract Inputs, Concrete Outputs

Follow the fundamental design rule: **"Be liberal in what you accept,
conservative in what you return."**

- **Function Arguments**: ALWAYS accept abstract interfaces from
  [`collections.abc`](https://docs.python.org/3/library/collections.abc.html).
  Do NOT annotate arguments as `list[T]` or `dict[K, V]` unless you explicitly
  require in-place mutation (`.append()`, `.pop()`).
- **Return Types**: Return concrete types (`list[T]`, `dict[K, V]`,
  `tuple[T, ...]`) so callers receive full capability without downcasting.

### Comparison Example

```python
from collections.abc import Iterable, Mapping, Sequence


# BAD: Rigid, forces callers to convert sets/tuples/generators to lists
def process_items(items: list[str], config: dict[str, str]) -> list[str]:
    return [x.strip() for x in items if x in config]


# GOOD: Flexible, accepts lists, tuples, sets, generators, dicts
def process_items(
    items: Sequence[str] | Iterable[str],
    config: Mapping[str, str],
) -> list[str]:
    return [x.strip() for x in items if x in config]
```

---

## 2. Abstraction Mapping Reference

Always import these interfaces from
[`collections.abc`](https://docs.python.org/3/library/collections.abc.html):

| Use Case                         | Abstract Annotation (`collections.abc`) | Why Avoid Concrete                           |
| :------------------------------- | :-------------------------------------- | :------------------------------------------- |
| **Ordered lookup / slicing**     | `Sequence[T]`                           | Allows `tuple`, `list`, custom sequences     |
| **One-pass iteration / streams** | `Iterable[T]`                           | Allows generators, sets, ranges              |
| **Key-value read-only lookup**   | `Mapping[K, V]`                         | Allows `dict`, `defaultdict`, immutable maps |
| **Unique element membership**    | `Set[T]`                                | Allows `set`, `frozenset`, custom sets       |
| **Higher-order callbacks**       | `Callable[[Arg1, Arg2], ReturnType]`    | Decouples functions and lambdas              |
| **Stateful iteration**           | `Iterator[T]`                           | Explicit iterator protocol                   |

---

## 3. Deprecated `typing` Constructs (Banned)

Never import deprecated capitalized generics from the legacy `typing` module in
Python 3.10+:

- **Banned**: `typing.List`, `typing.Dict`, `typing.Tuple`, `typing.Set`,
  `typing.FrozenSet`
  - **Use Instead**: `list[T]`, `dict[K, V]`, `tuple[T, ...]`, `set[T]`, or
    abstract types from `collections.abc`.
- **Banned**: `typing.Optional[T]`
  - **Use Instead**: `T | None` (PEP 604 union syntax).
- **Banned**: `typing.Union[A, B]`
  - **Use Instead**: `A | B`.

---

## 4. Pylance & Pyright Compliance

All code must pass [Pyright](https://microsoft.github.io/pyright/) with zero
errors and zero warnings:

```bash
uvx pyright .
```

### Common Type Errors & Fixes

1. **`str | None` passed to `str` parameter**:
   - _Problem_: `func(optional_var)` fails when `optional_var` can be `None`.
   - _Fix_: Guard with `if optional_var is None:` or provide fallback:
     `func(optional_var or "")`.
2. **Missing generic parameters**:
   - _Problem_: Annotating bare `list` or `dict`.
   - _Fix_: Always parameterize generics: `list[str]`, `dict[str, Any]`,
     `Sequence[Path]`.
3. **Subprocess output typing**:
   - _Problem_: `proc.stdout` is `str | bytes | None`.
   - _Fix_: Pass `text=True` or `capture_output=True` and verify non-null:
     `out = proc.stdout or ""`
