#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Evaluation runner for managing-credentials skill.

Reads evals/evals.json and executes deterministic static verification or agent
evaluations across supported backends.

Usage:
    python3 run_eval.py [--static] [--backend {agy,claude}] [--verbose]
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


class TermColor:
    """Terminal ANSI escape sequences for formatting."""

    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def check_credential_expectation(text: str, expectation: str) -> tuple[bool, str]:
    """Evaluates whether generated output satisfies a credential management rule.

    Args:
        text: Response or run output to evaluate.
        expectation: Natural language expectation string.

    Returns:
        Tuple of (passed_boolean, description_message).
    """
    lower_text = text.lower()
    lower_exp = expectation.lower()

    if "doppler projects create" in lower_exp or "projects create" in lower_exp:
        has_match = bool(re.search(r"doppler\s+projects\s+create", lower_text))
        return has_match, "Mentions 'doppler projects create'"

    if "doppler setup" in lower_exp:
        has_match = bool(re.search(r"doppler\s+setup", lower_text))
        return has_match, "Mentions 'doppler setup'"

    if "doppler secrets set" in lower_exp or "secrets set" in lower_exp:
        has_match = bool(re.search(r"doppler\s+secrets\s+set", lower_text))
        return has_match, "Mentions 'doppler secrets set'"

    if "doppler run" in lower_exp or "runtime injection" in lower_exp:
        has_match = bool(re.search(r"doppler\s+run\s+--", lower_text))
        return has_match, "Uses 'doppler run --'"

    if "mcp" in lower_exp:
        has_match = "mcp" in lower_text or "servers" in lower_text
        return has_match, "Addresses MCP server configuration"

    if "sync" in lower_exp or "warns" in lower_exp or "git" in lower_exp:
        has_guard = (
            "sync" in lower_text
            or "git" in lower_text
            or ".env" in lower_text
            or "leak" in lower_text
        )
        return has_guard, "Warns against sync/git leaks"

    return True, "Default check"


def run_static_eval(
    test_case: Mapping[str, Any], verbose: bool = False
) -> tuple[bool, Sequence[str]]:
    """Evaluates test expectations against expected outputs deterministically.

    Args:
        test_case: Evaluation case dictionary from evals.json.
        verbose: If True, prints check details.

    Returns:
        Tuple of (passed_boolean, failure_reasons_sequence).
    """
    test_id = test_case.get("id", "unknown")
    expectations: Sequence[str] = test_case.get("expectations", [])
    expected_patterns: Sequence[str] = test_case.get("expected_command_patterns", [])
    forbidden_patterns: Sequence[str] = test_case.get("forbidden_command_patterns", [])

    sample_solutions: dict[int, str] = {
        1: (
            "Run `doppler projects create ai-agents` to create your project.\n"
            "Next, run `doppler setup --project ai-agents --config dev`.\n"
            "Set tokens via `doppler secrets set SLACK_BOT_TOKEN='xoxb-...'`.\n"
            "Do not configure cloud sync or commit unencrypted .env files."
        ),
        2: (
            "Use `doppler run -- python3 scripts/my_agent.py` to inject "
            "environment variables into memory without writing .env to disk.\n"
            "Keep MCP server configs clean and launch the agent session via "
            "`doppler run -- agy` so MCP servers inherit credentials."
        ),
    }

    solution = sample_solutions.get(test_id) or test_case.get("expected_output") or ""
    failures: list[str] = []

    for pat in expected_patterns:
        if not re.search(pat, solution, flags=re.IGNORECASE):
            failures.append(f"Missing expected command pattern: {pat}")

    for pat in forbidden_patterns:
        if re.search(pat, solution, flags=re.IGNORECASE):
            failures.append(f"Contains forbidden command pattern: {pat}")

    for exp in expectations:
        passed, detail = check_credential_expectation(solution, exp)
        if not passed:
            failures.append(f"Failed expectation: '{exp}' ({detail})")
        elif verbose:
            print(f"    [CHECK] {detail}")

    return len(failures) == 0, failures


def run_agent_eval(
    test_case: Mapping[str, Any], backend: str, verbose: bool = False
) -> tuple[bool, Sequence[str]]:
    """Executes a test case against an external agent backend (agy or claude).

    Args:
        test_case: Test case mapping.
        backend: Backend name ("agy" or "claude").
        verbose: Verbose output toggle.

    Returns:
        Tuple of (passed_boolean, failure_reasons_sequence).
    """
    prompt = str(test_case.get("prompt", ""))
    bin_name = backend
    bin_path = shutil.which(bin_name)
    if not bin_path:
        return False, [f"'{bin_name}' executable not found in PATH"]

    cmd = (
        [bin_path, "--print", prompt]
        if backend == "claude"
        else [bin_path, "--prompt", prompt]
    )

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
        if verbose:
            print(f"    Agent exit code: {proc.returncode} in {elapsed:.2f}s")
        output = proc.stdout + "\n" + proc.stderr
    except subprocess.TimeoutExpired:
        return False, ["Execution timed out after 120s"]

    failures: list[str] = []
    for exp in test_case.get("expectations", []):
        passed, detail = check_credential_expectation(output, exp)
        if not passed:
            failures.append(f"Failed expectation: '{exp}' ({detail})")

    return len(failures) == 0, failures


def load_dataset(dataset_path: Path) -> Sequence[Mapping[str, Any]]:
    """Loads evaluation test cases from evals.json.

    Args:
        dataset_path: Path to evals.json file.

    Returns:
        Sequence of test case dictionaries.
    """
    if not dataset_path.is_file():
        raise FileNotFoundError(f"Dataset not found: {dataset_path}")

    data = json.loads(dataset_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "evals" not in data:
        raise ValueError("Invalid evals.json format: missing 'evals' key")

    return data["evals"]


def main(argv: Sequence[str] | None = None) -> int:
    """Evaluation CLI entry point.

    Args:
        argv: Optional command line argument sequence.

    Returns:
        Exit code (0 for pass, 1 for fail).
    """
    parser = argparse.ArgumentParser(
        description="Run evaluation benchmarks for managing-credentials."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET,
        help="Path to evals.json dataset.",
    )
    parser.add_argument(
        "--static",
        action="store_true",
        help="Run deterministic static verification without launching agents.",
    )
    parser.add_argument(
        "--backend",
        choices=["agy", "claude"],
        default="claude",
        help="Agent backend CLI to execute if not running static verification.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output logging.",
    )

    args = parser.parse_args(argv)

    try:
        cases = load_dataset(args.dataset)
    except (OSError, ValueError, json.JSONDecodeError) as e:
        print(f"{TermColor.RED}Failed to load dataset: {e}{TermColor.RESET}")
        return 1

    total = len(cases)
    passed_count = 0

    print(
        f"{TermColor.BOLD}Running benchmark ({'static' if args.static else args.backend}): "
        f"{total} cases{TermColor.RESET}\n"
    )

    for case in cases:
        cid = case.get("id", "?")
        print(f"Case #{cid}: {case.get('prompt', '')[:65]}...")

        if args.static:
            ok, failures = run_static_eval(case, verbose=args.verbose)
        else:
            ok, failures = run_agent_eval(
                case, backend=args.backend, verbose=args.verbose
            )

        if ok:
            passed_count += 1
            print(f"  {TermColor.GREEN}PASS{TermColor.RESET}")
        else:
            print(f"  {TermColor.RED}FAIL{TermColor.RESET}")
            for f in failures:
                print(f"    - {f}")

    print(f"\n{TermColor.BOLD}Summary: {passed_count}/{total} passed{TermColor.RESET}")
    return 0 if passed_count == total else 1


if __name__ == "__main__":
    sys.exit(main())
