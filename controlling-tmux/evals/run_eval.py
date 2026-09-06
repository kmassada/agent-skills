#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Multi-agent evaluation runner conforming to Claude's skill-creator schema.

Reads evals/evals.json (Claude standard format) and executes tests across
both Antigravity (agy) and Claude Code CLI / tool calling.
"""

import argparse
import json
import os
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
EVAL_SOCKET = "tmux-eval-sandbox"


class TermColor:
    """Terminal color codes for formatted CLI reporting."""

    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def setup_dummy_tmux(socket_name: str) -> tuple[bool, str]:
    """Creates an isolated dummy tmux session with predefined panes for testing.

    Args:
        socket_name: Socket identifier for isolated tmux server.

    Returns:
        Tuple of (success_boolean, pane_id_or_error_message).
    """
    try:
        subprocess.run(
            ["tmux", "-L", socket_name, "kill-server"],
            stderr=subprocess.DEVNULL,
            check=False,
        )
        time.sleep(0.2)

        res = subprocess.run(
            [
                "tmux",
                "-L",
                socket_name,
                "new-session",
                "-d",
                "-s",
                "eval-session",
                "-n",
                "editor",
                "-x",
                "160",
                "-y",
                "50",
                "-P",
                "-F",
                "#{pane_id}",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        pane_0 = res.stdout.strip()
        subprocess.run(
            ["tmux", "-L", socket_name, "split-window", "-h", "-t", pane_0],
            check=True,
        )
        subprocess.run(
            ["tmux", "-L", socket_name, "split-window", "-v", "-t", pane_0],
            check=True,
        )
        return True, pane_0
    except (subprocess.SubprocessError, OSError) as e:
        return False, str(e)


def teardown_dummy_tmux(socket_name: str) -> None:
    """Cleans up the dummy tmux server.

    Args:
        socket_name: Socket identifier to terminate.
    """
    subprocess.run(
        ["tmux", "-L", socket_name, "kill-server"],
        stderr=subprocess.DEVNULL,
        check=False,
    )


def evaluate_commands(
    commands_executed: Sequence[str],
    expected_patterns: Sequence[str],
    forbidden_patterns: Sequence[str],
) -> tuple[bool, list[str]]:
    """Validates captured commands against expected and forbidden patterns.

    Args:
        commands_executed: Sequence of commands extracted from tool executions.
        expected_patterns: Regex patterns that must match at least one command.
        forbidden_patterns: Regex patterns that must not match any command.

    Returns:
        Tuple of (passed_boolean, failure_messages_list).
    """
    failures: list[str] = []

    for exp_pat in expected_patterns:
        matched = any(re.search(exp_pat, cmd) for cmd in commands_executed)
        if not matched:
            failures.append(f"Missing expected command pattern: {exp_pat}")

    for forb_pat in forbidden_patterns:
        matches = [cmd for cmd in commands_executed if re.search(forb_pat, cmd)]
        if matches:
            failures.append(
                f"Triggered forbidden anti-pattern '{forb_pat}' "
                f"in command: {matches[0]}"
            )

    return len(failures) == 0, failures


def extract_commands(raw_output: str) -> list[str]:
    """Extracts bash commands across both Antigravity (agy) and Claude schemas.

    Args:
        raw_output: Full text output from agent CLI run.

    Returns:
        List of extracted command strings.
    """
    executed_commands: list[str] = []

    for raw_line in raw_output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            if isinstance(data, dict):
                # 1. Antigravity format: tool_calls -> run_command -> args.CommandLine
                for tc in data.get("tool_calls", []):
                    if tc.get("name") == "run_command":
                        cmd = tc.get("args", {}).get("CommandLine", "")
                        if cmd:
                            executed_commands.append(cmd)

                # 2. Claude format: type="tool_use", name="Bash" / "bash"
                if data.get("type") == "tool_use" or "name" in data:
                    name = data.get("name", "").lower()
                    if name in ("bash", "execute_command", "run_command"):
                        inp = data.get("input") or data.get("args") or {}
                        cmd = (
                            inp.get("command")
                            or inp.get("CommandLine")
                            or inp.get("cmd")
                        )
                        if cmd:
                            executed_commands.append(cmd)

                # 3. Claude content blocks with tool_use
                for block in data.get("content", []):
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        if block.get("name", "").lower() in (
                            "bash",
                            "execute_command",
                        ):
                            cmd = block.get("input", {}).get("command")
                            if cmd:
                                executed_commands.append(cmd)
        except json.JSONDecodeError:
            pass

    if not executed_commands:
        cmd_line_matches = re.findall(
            r"(?:CommandLine|command|bash)['\"]?\s*[:=]\s*['\"]([^'\"]+)['\"]",
            raw_output,
        )
        executed_commands.extend(cmd_line_matches)

    return executed_commands


def run_live_case(
    case: Mapping[str, Any],
    backend: str,
    socket_name: str,
    timeout_sec: int = 45,
) -> tuple[bool, list[str]]:
    """Runs a live test prompt via the selected CLI backend (agy or claude).

    Args:
        case: Test case mapping.
        backend: Target backend ('agy' or 'claude').
        socket_name: Sandbox socket identifier.
        timeout_sec: Timeout duration in seconds.

    Returns:
        Tuple of (passed_boolean, failure_messages_list).
    """
    prompt = case["prompt"]

    if backend == "agy":
        cmd = ["agy", "-p", prompt, "--output-format", "json", "--effort", "low"]
    elif backend == "claude":
        cmd = ["claude", "-p", prompt, "--output-format", "json"]
    else:
        return False, [f"Unknown backend: {backend}"]

    env = os.environ.copy()
    env["TMUX"] = f"/tmp/tmux-{os.getuid()}/{socket_name},1,0"
    env["TMUX_PANE"] = "%0"

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            env=env,
            cwd=str(SKILL_ROOT),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, [f"CLI execution timed out after {timeout_sec}s"]
    except FileNotFoundError:
        return False, [f"CLI executable '{cmd[0]}' not found in PATH."]

    raw_output = proc.stdout
    executed_commands = extract_commands(raw_output)

    skill_referenced = "tmux" in raw_output.lower() or any(
        "tmux" in c.lower() for c in executed_commands
    )

    failures: list[str] = []
    should_activate = bool(case.get("expected_command_patterns"))
    if should_activate and not skill_referenced:
        failures.append("Skill did not activate for expected positive trigger prompt.")
    elif not should_activate and any("tmux" in c for c in executed_commands):
        failures.append(
            "Skill false-positive: tmux commands executed for negative prompt."
        )

    passed, pat_failures = evaluate_commands(
        executed_commands,
        case.get("expected_command_patterns", []),
        case.get("forbidden_command_patterns", []),
    )
    failures.extend(pat_failures)

    return len(failures) == 0, failures


def run_dry_test(case: Mapping[str, Any]) -> tuple[bool, list[str]]:
    """Validates Claude schema conformance and regex patterns.

    Args:
        case: Test case mapping to evaluate.

    Returns:
        Tuple of (passed_boolean, validation_error_messages).
    """
    errors: list[str] = []
    for key in ("id", "prompt", "expected_output", "expectations"):
        if key not in case:
            errors.append(f"Missing Claude-schema required field: '{key}'")

    expectations = case.get("expectations")
    if not isinstance(expectations, list) or len(expectations) == 0:
        errors.append("Field 'expectations' must be a non-empty list of strings.")

    for pat in case.get("expected_command_patterns", []):
        try:
            re.compile(pat)
        except re.error as e:
            errors.append(f"Invalid regex in expected pattern '{pat}': {e}")

    for pat in case.get("forbidden_command_patterns", []):
        try:
            re.compile(pat)
        except re.error as e:
            errors.append(f"Invalid regex in forbidden pattern '{pat}': {e}")

    return len(errors) == 0, errors


def load_dataset(dataset_path: Path) -> tuple[str, list[dict[str, Any]]]:
    """Loads dataset supporting Claude's evals.json object structure and lists.

    Args:
        dataset_path: Path to evals.json file.

    Returns:
        Tuple of (skill_name, cases_list).

    Raises:
        ValueError: If evals format is unrecognized.
    """
    with open(dataset_path, encoding="utf-8") as f:
        raw = json.load(f)

    if isinstance(raw, dict) and "evals" in raw:
        skill_name = raw.get("skill_name", "unknown")
        return skill_name, raw["evals"]
    elif isinstance(raw, list):
        return "legacy", raw
    else:
        raise ValueError("Unrecognized evals schema format")


def detect_backend() -> str:
    """Auto-detects whether agy or claude CLI is available.

    Returns:
        Detected backend name ('agy' or 'claude').
    """
    if shutil.which("agy"):
        return "agy"
    if shutil.which("claude"):
        return "claude"
    return "agy"


def main(argv: Sequence[str] | None = None) -> None:
    """Main CLI orchestrator for tmux skill evaluation suite.

    Args:
        argv: Optional command-line arguments sequence; defaults to sys.argv[1:].
    """
    parser = argparse.ArgumentParser(
        description="Eval suite for controlling-tmux skill (Claude Conforming)"
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET,
        help="Path to evals.json",
    )
    parser.add_argument(
        "--case",
        type=str,
        default=None,
        help="Run only specific eval ID (e.g. 1 or 2)",
    )
    parser.add_argument(
        "--live", action="store_true", help="Run actual CLI evaluations"
    )
    parser.add_argument(
        "--backend",
        choices=["agy", "claude"],
        default=detect_backend(),
        help="Agent CLI backend to evaluate ('agy' or 'claude')",
    )
    parser.add_argument(
        "--socket",
        type=str,
        default=EVAL_SOCKET,
        help="Isolated tmux socket name",
    )
    args = parser.parse_args(argv)

    if not args.dataset.exists():
        print(
            f"{TermColor.RED}Error: Dataset not found at "
            f"{args.dataset}{TermColor.RESET}",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        skill_name, cases = load_dataset(args.dataset)
    except (json.JSONDecodeError, ValueError, OSError) as e:
        print(
            f"{TermColor.RED}Failed to load dataset: {e}{TermColor.RESET}",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.case:
        cases = [c for c in cases if str(c.get("id")) == str(args.case)]
        if not cases:
            print(
                f"{TermColor.RED}No test case found with ID: "
                f"{args.case}{TermColor.RESET}",
                file=sys.stderr,
            )
            sys.exit(1)

    banner = (
        f"\n{TermColor.BOLD}=== Running controlling-tmux Skill Evals "
        f"(Claude-Conforming) ==={TermColor.RESET}"
    )
    print(banner)
    print(f"Skill:   {TermColor.CYAN}{skill_name}{TermColor.RESET}")
    print(f"Dataset: {TermColor.CYAN}{args.dataset.name}{TermColor.RESET}")
    mode_str = (
        f"LIVE CLI ({args.backend})"
        if args.live
        else "SCHEMA CONFORMANCE & REGEX VERIFICATION"
    )
    print(f"Mode:    {TermColor.BLUE}{mode_str}{TermColor.RESET}")
    print(f"Backend: {TermColor.BLUE}{args.backend}{TermColor.RESET}")
    print(f"Loaded:  {len(cases)} test cases\n")

    if args.live:
        ok, err = setup_dummy_tmux(args.socket)
        if not ok:
            print(
                f"{TermColor.RED}Failed to setup sandbox tmux server: "
                f"{err}{TermColor.RESET}",
                file=sys.stderr,
            )
            sys.exit(1)
        print(f"Sandbox tmux server initialized on socket: {args.socket}\n")

    passed_count = 0
    total_count = len(cases)

    try:
        for idx, case in enumerate(cases, 1):
            cid = case.get("id")
            prompt = case.get("prompt", "")
            print(
                f"[{idx}/{total_count}] Eval #{cid}: "
                f'{TermColor.BOLD}"{prompt}"{TermColor.RESET}'
            )

            expectations = case.get("expectations", [])
            for exp in expectations:
                print(f"     * Expectation: {TermColor.CYAN}{exp}{TermColor.RESET}")

            if args.live:
                passed, issues = run_live_case(case, args.backend, args.socket)
            else:
                passed, issues = run_dry_test(case)

            if passed:
                passed_count += 1
                print(
                    f"     Result: {TermColor.GREEN}[PASS] "
                    f"(Conforms to Claude Schema){TermColor.RESET}"
                )
            else:
                print(f"     Result: {TermColor.RED}[FAIL]{TermColor.RESET}")
                for issue in issues:
                    print(f"       - {TermColor.YELLOW}{issue}{TermColor.RESET}")
            print()

    finally:
        if args.live:
            teardown_dummy_tmux(args.socket)
            print(f"Sandbox tmux server {args.socket} cleanly terminated.")

    print("--------------------------------------------------")
    score_color = TermColor.GREEN if passed_count == total_count else TermColor.RED
    print(
        f"Score: {score_color}{passed_count}/{total_count} Passed{TermColor.RESET} "
        f"({(passed_count / total_count) * 100:.1f}%)"
    )
    print("--------------------------------------------------\n")

    if passed_count < total_count:
        sys.exit(1)


if __name__ == "__main__":
    main()
