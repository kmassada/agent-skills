#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Dynamic test runner for changed skill companion test suites.

Discovers modified skill packages from staged file paths, locates their
companion unit tests (*_test.py and test_*.py in scripts/ and evals/),
and executes them deterministically.

Usage:
    python3 run_skill_tests.py [file_path ...]
    python3 run_skill_tests.py --all
"""

import argparse
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path


def find_skill_root(file_path: Path, repo_root: Path) -> Path | None:
    """Finds the root directory of a skill containing the given file.

    Args:
        file_path: Absolute or repo-relative path to an inspected file.
        repo_root: Root directory of the repository.

    Returns:
        Path to the skill root if inside a skill with SKILL.md, else None.
    """
    try:
        resolved_file = file_path.resolve()
        resolved_root = repo_root.resolve()
        rel = resolved_file.relative_to(resolved_root)
    except (ValueError, OSError):
        return None

    parts = rel.parts
    if not parts:
        return None

    top_level = resolved_root / parts[0]
    if top_level.is_dir() and (top_level / "SKILL.md").is_file():
        return top_level

    return None


def discover_skill_tests(skill_dir: Path) -> Sequence[Path]:
    """Discovers companion test files within a skill package.

    Inspects scripts/ and evals/ subdirectories for *_test.py and test_*.py.

    Args:
        skill_dir: Directory of the skill to scan.

    Returns:
        Sorted sequence of paths to discovered test scripts.
    """
    test_files: list[Path] = []
    for sub in ("scripts", "evals"):
        folder = skill_dir / sub
        if not folder.is_dir():
            continue
        for p in folder.iterdir():
            if not p.is_file() or p.name.startswith(".") or not p.name.endswith(".py"):
                continue
            if p.name.endswith("_test.py") or p.name.startswith("test_"):
                test_files.append(p)

    return sorted(test_files)


def run_test_files(test_files: Sequence[Path], repo_root: Path) -> bool:
    """Executes each test file with python3.

    Args:
        test_files: Sequence of test file paths to execute.
        repo_root: Working directory for test execution.

    Returns:
        True if all tests passed with exit code 0, False otherwise.
    """
    all_passed = True
    for test_path in test_files:
        rel_test = test_path.relative_to(repo_root)
        print(f"Running companion test: {rel_test}...", flush=True)
        result = subprocess.run(
            [sys.executable, str(test_path)],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            all_passed = False
            print(f"FAIL: {rel_test} (exit code {result.returncode})", file=sys.stderr)
            if result.stdout:
                print(result.stdout, file=sys.stderr)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
        else:
            print(f"PASS: {rel_test}", flush=True)

    return all_passed


def main(argv: Sequence[str] | None = None) -> int:
    """Main entrypoint for running companion tests.

    Args:
        argv: Command line arguments.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    parser = argparse.ArgumentParser(
        description="Run companion tests for changed skills."
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="Modified files to detect changed skill packages.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run tests across all skills in the repository.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parent.parent.parent,
        help="Path to repository root.",
    )

    args = parser.parse_args(argv)
    repo_root: Path = args.repo_root.resolve()

    skills_to_test: set[Path] = set()

    if args.all:
        for child in repo_root.iterdir():
            if child.is_dir() and (child / "SKILL.md").is_file():
                skills_to_test.add(child)
    else:
        for file_str in args.files:
            p = Path(file_str)
            if not p.is_absolute():
                p = repo_root / p
            skill_dir = find_skill_root(p, repo_root)
            if skill_dir:
                skills_to_test.add(skill_dir)

    if not skills_to_test:
        print("No skill packages affected; companion test check skipped.")
        return 0

    sorted_skills = sorted(skills_to_test)
    print(
        f"Detected {len(sorted_skills)} affected skill(s): "
        f"{', '.join(s.name for s in sorted_skills)}"
    )

    all_test_files: list[Path] = []
    for skill in sorted_skills:
        tests = discover_skill_tests(skill)
        all_test_files.extend(tests)

    if not all_test_files:
        print("No companion tests found in affected skills.")
        return 0

    success = run_test_files(all_test_files, repo_root)
    if not success:
        return 1

    print(f"All {len(all_test_files)} companion test suite(s) passed cleanly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
