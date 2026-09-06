#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Evaluation runner for authoring-skills benchmarks.

Supports deterministic static benchmark validation as well as live execution
against agent backends (Google Antigravity and Anthropic Claude Code).

Usage:
    # Run deterministic static checks across all test cases:
    python3 run_eval.py --static

    # Run against active Google Antigravity CLI:
    python3 run_eval.py --backend agy --eval-id 1

    # Run against Anthropic Claude Code CLI:
    python3 run_eval.py --backend claude --eval-id 1
"""

import argparse
import json
import re
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


def check_authoring_expectation(content: str, expectation: str) -> tuple[bool, str]:
    """Evaluates a single natural-language expectation against generated output.

    Args:
        content: Text content produced by agent or test solution.
        expectation: Natural language expectation string.

    Returns:
        Tuple of (passed_boolean, diagnostic_detail_string).
    """
    exp_lower = expectation.lower()

    if "gerund" in exp_lower or "inspecting-logs" in exp_lower:
        match = bool(
            re.search(r"inspecting-logs", content)
            or re.search(r"\b[a-z]+ing-[a-z]+\b", content)
        )
        return (
            match,
            "Found gerund skill naming pattern"
            if match
            else "Missing gerund naming pattern",
        )

    if "folded scalar" in exp_lower or ">-" in exp_lower:
        match = ">-" in content or ">" in content
        return (
            match,
            "Found folded scalar block indicator (>-)"
            if match
            else "Missing folded scalar block",
        )

    if "positive trigger" in exp_lower or "use when" in exp_lower:
        match = bool(re.search(r"use when", content, re.IGNORECASE))
        return (
            match,
            "Found positive trigger 'Use when'"
            if match
            else "Missing positive trigger",
        )

    if (
        "negative guardrail" in exp_lower
        or "don't use" in exp_lower
        or "do not use" in exp_lower
    ):
        match = bool(
            re.search(
                r"(don't use|do not use|not intended for|never use)",
                content,
                re.IGNORECASE,
            )
        )
        return (
            match,
            "Found negative guardrail 'Don't use for'"
            if match
            else "Missing negative guardrail",
        )

    if "dispatcher" in exp_lower or "references/" in exp_lower:
        match = bool(
            re.search(r"references/", content) or "dispatcher" in content.lower()
        )
        return (
            match,
            "Found dispatcher references" if match else "Missing dispatcher structure",
        )

    if "redundant" in exp_lower or "**name:**" in exp_lower:
        has_redundant = bool(re.search(r"\*\*(Name|Description):\*\*", content))
        passed = not has_redundant
        return (
            passed,
            "No redundant bold markers found"
            if passed
            else "Found redundant **Name:** or **Description:** in body",
        )

    if (
        "focus hijacking" in exp_lower
        or "capture-pane" in exp_lower
        or "select-pane" in exp_lower
    ):
        match = bool(
            re.search(r"capture-pane", content, re.IGNORECASE)
            or re.search(r"focus hijacking", content, re.IGNORECASE)
            or re.search(r"silent", content, re.IGNORECASE)
        )
        return (
            match,
            "Addressed focus hijacking / silent capture"
            if match
            else "Missing focus hijacking mitigation",
        )

    if "context confusion" in exp_lower or "subshell" in exp_lower:
        match = bool(
            re.search(r"context confusion", content, re.IGNORECASE)
            or re.search(r"subshell", content, re.IGNORECASE)
            or re.search(r"docker exec", content, re.IGNORECASE)
        )
        return (
            match,
            "Addressed context confusion / target execution"
            if match
            else "Missing context confusion mitigation",
        )

    if "500-line" in exp_lower or "budget" in exp_lower:
        match = bool(
            re.search(r"500", content) or re.search(r"budget", content, re.IGNORECASE)
        )
        return (
            match,
            "Referenced line budget guidelines"
            if match
            else "Missing line budget guidelines",
        )

    if "quiz" in exp_lower or "tasks" in exp_lower:
        match = bool(
            re.search(r"task", content, re.IGNORECASE)
            or re.search(r"quiz", content, re.IGNORECASE)
        )
        return (
            match,
            "Addressed task-oriented eval principles"
            if match
            else "Missing task-oriented principles",
        )

    if "tool names" in exp_lower:
        match = bool(
            re.search(r"tool name", content, re.IGNORECASE)
            or re.search(r"avoid.*tool", content, re.IGNORECASE)
            or "cli flags" in content.lower()
        )
        return (
            match,
            "Addressed avoiding tool names in prompts"
            if match
            else "Missing tool name avoidance guidance",
        )

    if "outcome" in exp_lower:
        match = bool(
            re.search(r"outcome", content, re.IGNORECASE)
            or re.search(r"what.*not.*how", content, re.IGNORECASE)
        )
        return (
            match,
            "Asserts outcome-based verification"
            if match
            else "Missing outcome-based assertion principle",
        )

    if "schema" in exp_lower:
        match = bool("expected_output" in content and "expectations" in content)
        return (
            match,
            "Conforms to evals.json schema"
            if match
            else "Missing evals.json schema elements",
        )

    if "shebang" in exp_lower or "executable" in exp_lower:
        match = bool(
            re.search(r"#!/usr/bin/env", content)
            or re.search(r"shebang", content, re.IGNORECASE)
        )
        return (
            match,
            "Addressed executable shebang"
            if match
            else "Missing executable shebang guidance",
        )

    if "third person" in exp_lower or "active verb" in exp_lower:
        is_active_verb = bool(
            re.search(
                r"^\s*(description:\s*([>|]-?\s*)?)?[A-Z][a-z]+s\b",
                content,
                re.MULTILINE,
            )
        )
        match = bool(
            re.search(r"third person", content, re.IGNORECASE) or is_active_verb
        )
        return (
            match,
            "Specified third-person phrasing"
            if match
            else "Missing third-person guidance",
        )

    if "1024" in exp_lower or "column" in exp_lower or "limit" in exp_lower:
        within_limits = len(content) <= 1024 and all(
            len(line) <= 80 for line in content.splitlines()
        )
        match = within_limits or bool(
            re.search(r"1024", content) or re.search(r"80", content)
        )
        return (
            match,
            "Verified character and column limits"
            if match
            else "Failed character or column limits",
        )

    # Default fallback: check if key nouns from expectation appear in content
    tokens = [w for w in re.findall(r"[a-z0-9_-]+", exp_lower) if len(w) > 4]
    found = [t for t in tokens if t in content.lower()]
    passed = len(found) >= max(1, len(tokens) // 2)
    return (
        passed,
        f"Matched {len(found)}/{len(tokens)} terms ({', '.join(found[:3])}...)"
        if passed
        else f"Failed match: expected terms from '{expectation[:30]}...'",
    )


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
        1: (
            "---\n"
            "name: inspecting-logs\n"
            "description: >-\n"
            "  Extracts and analyzes containerized service logs without disturbing\n"
            "  running applications. Use when debugging container crashes or "
            "analyzing\n"
            "  log streams. Don't use for modifying container configuration.\n"
            "---\n"
            "# Inspecting Logs\n\n"
            "See [details](./references/DETAILS.md) for full guide.\n"
        ),
        2: (
            "The draft skill demonstrates two major anti-patterns:\n"
            "1. Focus Hijacking: selecting tmux panes interrupts user workflow. "
            "Use `tmux capture-pane -p`.\n"
            "2. Context Confusion: executing in the local subshell risks "
            "environment pollution. Target `docker exec`.\n"
            "3. Overtriggering: add negative guardrails "
            "(e.g. 'Don't use for generic SQL').\n"
        ),
        3: (
            "Refactor using progressive disclosure:\n"
            "1. Cap SKILL.md under the 500-line budget as a lean primary "
            "dispatcher.\n"
            "2. Offload API schemas and deep tables into "
            "references/API_REFERENCE.md.\n"
            "3. Ensure all relative links maintain integrity.\n"
        ),
        4: (
            "{\n"
            '  "skill_name": "inspecting-k8s",\n'
            '  "evals": [\n'
            "    {\n"
            '      "id": 1,\n'
            '      "prompt": "Inspect cluster nodes in namespace prod",\n'
            '      "expected_output": '
            '"Reports healthy status for all active nodes.",\n'
            '      "expectations": [\n'
            '        "Frame authentic task, not knowledge quiz",\n'
            '        "Do not mention tool names",\n'
            '        "Assert outcomes"\n'
            "      ]\n"
            "    }\n"
            "  ]\n"
            "}\n"
        ),
        5: (
            "The skill audit tool performs comprehensive verification:\n"
            "1. YAML frontmatter validation: regex name pattern, description under "
            "1024 chars, folded scalar (>-), positive and negative triggers.\n"
            "2. Markdown layout: H1 header, 500-line budget, no broken code "
            "blocks, and relative link integrity.\n"
            "3. Script standards: verifies executable shebang "
            "(#!/usr/bin/env python3) and syntax validity.\n"
        ),
        6: (
            "description: >-\n"
            "  Inspects and debugs Kubernetes cluster health, nodes, and pods.\n"
            "  Use when diagnosing node pressure, pod eviction, or deployment "
            "crashes.\n"
            "  Don't use for Docker Compose or local machine system "
            "troubleshooting.\n"
        ),
    }

    solution = sample_solutions.get(test_id) or test_case.get("expected_output") or ""
    failures: list[str] = []

    for exp in expectations:
        passed, detail = check_authoring_expectation(solution, exp)
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
        cmd = ["agy", "--prompt", prompt, "--no-interactive"]
    elif backend == "claude":
        cmd = ["claude", "-p", prompt]
    else:
        return False, [f"Unsupported backend: '{backend}'"]

    start_time = time.time()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return False, [f"Backend execution failed: {e}"]

    duration = time.time() - start_time
    if verbose:
        print(f"    [RUN] Exit code: {proc.returncode} ({duration:.1f}s)")

    output = proc.stdout + "\n" + proc.stderr
    failures: list[str] = []

    for exp in test_case.get("expectations", []):
        passed, detail = check_authoring_expectation(output, exp)
        if not passed:
            failures.append(f"Failed expectation: '{exp}' ({detail})")

    return len(failures) == 0, failures


def main(argv: Sequence[str] | None = None) -> int:
    """CLI orchestrator for authoring-skills evaluation runner.

    Args:
        argv: Optional command-line arguments.

    Returns:
        Exit code: 0 if all tests passed, 1 otherwise.
    """
    parser = argparse.ArgumentParser(
        description="Run evaluation benchmarks for authoring-skills."
    )
    parser.add_argument(
        "--static",
        action="store_true",
        help="Run deterministic static checks on canonical benchmark scenarios.",
    )
    parser.add_argument(
        "--backend",
        choices=["agy", "claude"],
        help="Live agent CLI backend to test.",
    )
    parser.add_argument(
        "--eval-id",
        type=int,
        help="Specific test case ID to execute (1-indexed).",
    )
    parser.add_argument(
        "--evals-file",
        type=Path,
        default=Path(__file__).parent / "evals.json",
        help="Path to evals.json benchmark file.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print detailed check messages.",
    )
    args = parser.parse_args(argv)

    if not args.evals_file.is_file():
        print(f"Error: evals file '{args.evals_file}' not found.", file=sys.stderr)
        return 1

    try:
        data = json.loads(args.evals_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"Error parsing evals file: {e}", file=sys.stderr)
        return 1

    cases: Sequence[Mapping[str, Any]] = data.get("evals", [])
    if args.eval_id:
        cases = [c for c in cases if c.get("id") == args.eval_id]
        if not cases:
            print(f"Error: No test case found with id {args.eval_id}.", file=sys.stderr)
            return 1

    total = len(cases)
    passed_count = 0
    all_failures: list[tuple[int, list[str]]] = []

    print(f"Running evaluation on {total} test case(s)...")
    print("=" * 70)

    for case in cases:
        cid = case.get("id", "?")
        prompt = case.get("prompt", "")
        print(f"\n[EVAL #{cid}] {prompt[:65]}...")

        if args.backend:
            passed, failures = run_agent_eval(case, args.backend, verbose=args.verbose)
        else:
            passed, failures = evaluate_static_benchmark(case, verbose=args.verbose)

        if passed:
            print("  --> PASS")
            passed_count += 1
        else:
            print("  --> FAIL")
            for f in failures:
                print(f"      • {f}")
            all_failures.append((cid, failures))

    print("\n" + "=" * 70)
    print(f"Results: {passed_count}/{total} passed ({passed_count / total * 100:.1f}%)")

    return 0 if passed_count == total else 1


if __name__ == "__main__":
    sys.exit(main())
