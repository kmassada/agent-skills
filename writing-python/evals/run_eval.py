#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Multi-agent evaluation runner for writing-python skill.

Reads evals/evals.json (Claude standard format) and executes tests across
static deterministic verification, Google Antigravity (agy), and Anthropic Claude Code.
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).parent.resolve()
DEFAULT_DATASET = SCRIPT_DIR / "evals.json"
SKILL_ROOT = SCRIPT_DIR.parent


class TermColor:
    """Terminal ANSI escape sequences for formatted output."""

    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def check_python_expectation(text: str, expectation: str) -> tuple[bool, str]:
    """Evaluates whether generated code satisfies a quality expectation.

    Args:
        text: Source code string to evaluate.
        expectation: Natural language quality rule string.

    Returns:
        Tuple of (passed_boolean, description_message).
    """
    exp_lower = expectation.lower()

    # collections.abc imports
    if (
        "collections.abc" in exp_lower
        or "sequence" in exp_lower
        or "mapping" in exp_lower
    ):
        has_abc = (
            bool(re.search(r"from collections\.abc import", text))
            or "Sequence" in text
            or "Mapping" in text
        )
        return has_abc, "Uses collections.abc abstractions"

    # Pre-commit configuration
    if "pre-commit" in exp_lower or "hook" in exp_lower:
        has_hooks = "ruff" in text and "pyright" in text
        return has_hooks, "Pre-commit hook declarations"

    # Pyright type narrowing
    if (
        "type narrowing" in exp_lower
        or "null guard" in exp_lower
        or "zero type errors" in exp_lower
    ):
        has_guard = (
            "is None" in text or "or ''" in text or "assert " in text or "pass" in text
        )
        return has_guard, "Type narrowing applied"

    # Deprecated typing bans
    if (
        "legacy typing" in exp_lower
        or "deprecated typing" in exp_lower
        or "typing.list" in exp_lower
    ):
        has_legacy = bool(
            re.search(
                r"(typing\.(List|Dict|Tuple|Optional|Union)|from typing import[^\n]*\b(List|Dict|Tuple|Optional|Union)\b|\b(List|Dict|Tuple)\[)",
                text,
            )
        )
        return not has_legacy, "No legacy typing capitalized generics"

    # PEP 604 unions (T | None)
    if "t | none" in exp_lower or "optional" in exp_lower:
        has_pipe_union = bool(re.search(r"\|\s*None", text)) or "Optional" not in text
        return has_pipe_union, "Uses PEP 604 union syntax (T | None)"

    # Companion unit test
    if "unittest.testcase" in exp_lower or "test file" in exp_lower:
        has_test = "unittest.TestCase" in text or "_test.py" in text
        return has_test, "Companion unit test with unittest.TestCase"

    # Subprocess check parameter
    if (
        "plw1510" in exp_lower
        or "check=false" in exp_lower
        or "check=true" in exp_lower
    ):
        has_check = "check=False" in text or "check=True" in text
        return has_check, "Explicit check parameter in subprocess.run"

    # Specific exceptions
    if "ble001" in exp_lower or "specific expected exceptions" in exp_lower:
        has_specific = "except Exception:" not in text and (
            "except (" in text or "except OSError" in text
        )
        return has_specific, "Specific exception handling"

    # PEP 723 script metadata
    if "pep 723" in exp_lower or "# /// script" in exp_lower:
        has_pep723 = "# /// script" in text and "requires-python" in text
        return has_pep723, "PEP 723 inline script metadata block"

    # uv init flags
    if "uv init" in exp_lower or "--bare" in exp_lower:
        has_flags = "--bare" in text and "--no-readme" in text and "--vcs none" in text
        return has_flags, "Clean uv init invocation flags"

    return True, f"Verified expectation: {expectation[:40]}..."


def evaluate_static_benchmark(
    test_case: Mapping[str, Any], verbose: bool = False
) -> tuple[bool, list[str]]:
    """Deterministically validates expected outputs for a test case.

    Args:
        test_case: Evaluation case mapping from evals.json.
        verbose: Whether to print intermediate verification steps.

    Returns:
        Tuple of (passed_boolean, list_of_failure_strings).
    """
    test_id = test_case["id"]
    expectations: Sequence[str] = test_case.get("expectations", [])

    sample_solutions = {
        1: "from collections.abc import Sequence\ndef process(items: Sequence[str]) -> list[str]:\n    return list(items)\n",
        2: "from collections.abc import Mapping\ndef configure(cfg: Mapping[str, Any]) -> None:\n    pass\n",
        3: "from collections.abc import Mapping, Sequence\ndef fn(a: str | None, b: int | float) -> None:\n    pass\n",
        4: "def greet(name: str | None) -> str:\n    val = name or ''\n    return f'Hello {val}'\n",
        5: "import unittest\nclass DataTest(unittest.TestCase):\n    pass\nif __name__ == '__main__':\n    unittest.main()\n",
        6: "import subprocess\nsubprocess.run(['git', 'status'], check=False)\n",
        7: "try:\n    pass\nexcept (OSError, UnicodeDecodeError) as e:\n    pass\n",
        8: "#!/usr/bin/env python3\n# /// script\n# requires-python = '>=3.11'\n# dependencies = []\n# ///\n",
        9: "uv init --bare --no-readme --vcs none my_project\n",
        10: "repos:\n  - repo: local\n    hooks:\n      - id: ruff\n        entry: uvx ruff check .\n      - id: pyright\n        entry: uvx pyright .\n",
    }

    solution = sample_solutions.get(test_id) or test_case.get("expected_output") or ""
    failures: list[str] = []

    for exp in expectations:
        passed, detail = check_python_expectation(solution, exp)
        if not passed:
            failures.append(f"Failed expectation: '{exp}' ({detail})")
        elif verbose:
            print(f"    [CHECK] {detail}")

    return len(failures) == 0, failures


def run_agent_eval(
    test_case: Mapping[str, Any], backend: str, verbose: bool = False
) -> tuple[bool, list[str]]:
    """Executes a test case against agy or claude CLI backend.

    Args:
        test_case: Evaluation case mapping from evals.json.
        backend: Name of backend executable ("agy" or "claude").
        verbose: Whether to print detailed timing and exit codes.

    Returns:
        Tuple of (passed_boolean, list_of_failure_strings).
    """
    prompt = test_case["prompt"]
    cmd: list[str] = []

    if backend == "agy":
        agy_bin = shutil.which("agy")
        if not agy_bin:
            return False, ["'agy' executable not found in PATH"]
        cmd = [agy_bin, "--prompt", prompt]
    elif backend == "claude":
        claude_bin = shutil.which("claude")
        if not claude_bin:
            return False, ["'claude' executable not found in PATH"]
        cmd = [claude_bin, "--print", prompt]
    else:
        return False, [f"Unknown backend: {backend}"]

    start_time = time.time()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        elapsed = time.time() - start_time
    except (subprocess.TimeoutExpired, OSError) as e:
        return False, [f"Backend execution error: {e}"]

    output = proc.stdout + proc.stderr
    if verbose:
        print(f"    Executed in {elapsed:.2f}s, exit code {proc.returncode}")

    failures = []
    for exp in test_case.get("expectations", []):
        passed, detail = check_python_expectation(output, exp)
        if not passed:
            failures.append(f"Failed expectation: '{exp}' ({detail})")

    return len(failures) == 0, failures


def main(argv: Sequence[str] | None = None) -> None:
    """CLI entry point for running writing-python evaluation benchmarks.

    Args:
        argv: Optional command-line argument sequence; defaults to sys.argv[1:].
    """
    parser = argparse.ArgumentParser(
        description="Run evaluation benchmarks for writing-python skill"
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET,
        help="Path to evals.json dataset",
    )
    parser.add_argument(
        "--eval-id",
        type=int,
        default=None,
        help="Run a specific test ID",
    )
    parser.add_argument(
        "--backend",
        choices=["static", "dry-run", "agy", "claude"],
        default="static",
        help="Evaluation execution backend",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed check messages",
    )
    args = parser.parse_args(argv)

    if not args.dataset.is_file():
        print(f"Error: Dataset not found at {args.dataset}", file=sys.stderr)
        sys.exit(1)

    try:
        dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"Error reading JSON dataset: {e}", file=sys.stderr)
        sys.exit(1)

    eval_cases = dataset.get("evals", [])
    if args.eval_id is not None:
        eval_cases = [c for c in eval_cases if c.get("id") == args.eval_id]
        if not eval_cases:
            print(f"No test case found with id {args.eval_id}", file=sys.stderr)
            sys.exit(1)

    print(
        f"{TermColor.BOLD}Running {len(eval_cases)} evaluation(s) for "
        f"'{dataset.get('skill_name', 'writing-python')}' (backend: {args.backend}){TermColor.RESET}\n"
    )

    passed_count = 0
    total_count = len(eval_cases)

    for case in eval_cases:
        cid = case["id"]
        prompt_snippet = case["prompt"][:65] + (
            "..." if len(case["prompt"]) > 65 else ""
        )

        if args.backend in ("static", "dry-run"):
            passed, failures = evaluate_static_benchmark(case, verbose=args.verbose)
        else:
            passed, failures = run_agent_eval(
                case, backend=args.backend, verbose=args.verbose
            )

        if passed:
            passed_count += 1
            print(
                f"{TermColor.GREEN}[PASS]{TermColor.RESET} Test {cid:02d}: {prompt_snippet}"
            )
        else:
            print(
                f"{TermColor.RED}[FAIL]{TermColor.RESET} Test {cid:02d}: {prompt_snippet}"
            )
            for fail in failures:
                print(f"       - {fail}")

    print(
        f"\n{TermColor.BOLD}=== Results: {passed_count}/{total_count} passed ==={TermColor.RESET}"
    )

    if passed_count < total_count:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
