#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Automated quality gate checking Ruff, Pyright, and unit tests."""

import argparse
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path


def run_command(cmd: Sequence[str], description: str) -> tuple[bool, str]:
    """Runs a subprocess command and captures output.

    Args:
        cmd: Command arguments to execute.
        description: Human-readable label for logging.

    Returns:
        Tuple of (success_boolean, stripped_output_string).
    """
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, ValueError) as e:
        return False, f"Failed to execute {cmd[0]}: {e}"

    output = (proc.stdout + proc.stderr).strip()
    return proc.returncode == 0, output


def check_ruff(target_dir: Path) -> tuple[bool, str]:
    """Verifies style and formatting with ruff.

    Args:
        target_dir: Path to directory to inspect.

    Returns:
        Tuple of (success_boolean, status_message).
    """
    uv_bin = shutil.which("uvx") or shutil.which("uv")
    if not uv_bin:
        return False, "'uv' or 'uvx' not found in PATH"

    ok_check, out_check = run_command(
        [uv_bin, "ruff", "check", str(target_dir)], "ruff check"
    )
    if not ok_check:
        return False, out_check

    ok_fmt, out_fmt = run_command(
        [uv_bin, "ruff", "format", "--check", str(target_dir)],
        "ruff format check",
    )
    if not ok_fmt:
        return False, out_fmt

    return True, "Ruff lint and formatting clean"


def check_pyright(target_dir: Path) -> tuple[bool, str]:
    """Verifies static typing with pyright.

    Args:
        target_dir: Path to directory to inspect.

    Returns:
        Tuple of (success_boolean, status_message).
    """
    uv_bin = shutil.which("uvx") or shutil.which("uv")
    if not uv_bin:
        return False, "'uv' or 'uvx' not found in PATH"

    return run_command([uv_bin, "pyright", str(target_dir)], "pyright")


def run_tests(test_files: Sequence[Path]) -> tuple[bool, list[str]]:
    """Executes companion unit test files.

    Args:
        test_files: Sequence of test file paths to execute.

    Returns:
        Tuple of (all_passed_boolean, list_of_failure_messages).
    """
    failures: list[str] = []
    for test_file in test_files:
        ok, out = run_command(
            [sys.executable, str(test_file)], f"test {test_file.name}"
        )
        if not ok:
            failures.append(f"{test_file.name} failed:\n{out}")
    return len(failures) == 0, failures


def main() -> None:
    """CLI entry point for verifying repository Python quality gates."""
    parser = argparse.ArgumentParser(
        description="Verify Python code against Ruff, Pyright, and unit tests"
    )
    parser.add_argument(
        "target",
        type=Path,
        nargs="?",
        default=Path("."),
        help="Target directory to inspect",
    )
    args = parser.parse_args()
    target_dir = args.target.resolve()

    print(f"Checking Python quality gates for: {target_dir}\n")

    ok_ruff, ruff_msg = check_ruff(target_dir)
    status_ruff = "[PASS]" if ok_ruff else "[FAIL]"
    print(f"{status_ruff} Ruff (style & formatting)")
    if not ok_ruff:
        print(f"       {ruff_msg}")

    ok_pyright, pyright_msg = check_pyright(target_dir)
    status_pyright = "[PASS]" if ok_pyright else "[FAIL]"
    print(f"{status_pyright} Pyright (static typing)")
    if not ok_pyright:
        print(f"       {pyright_msg}")

    test_files = [p for p in target_dir.rglob("*_test.py") if ".git" not in p.parts]
    ok_tests, test_failures = run_tests(test_files)
    status_tests = "[PASS]" if ok_tests else "[FAIL]"
    print(f"{status_tests} Unit tests ({len(test_files)} test suite(s) found)")
    if not ok_tests:
        for f in test_failures:
            print(f"       {f}")

    if ok_ruff and ok_pyright and ok_tests:
        print("\nAll Python quality gates passed successfully.")
        sys.exit(0)
    else:
        print("\nQuality gate failures detected.")
        sys.exit(1)


if __name__ == "__main__":
    main()
