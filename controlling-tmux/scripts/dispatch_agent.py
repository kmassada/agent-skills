#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Dispatches AI agent sessions into dedicated tmux windows and panes.

Supports interactive TUI launches with agy, programmatic conversation creation
via agentapi, joining ongoing conversations, and multi-pane splitting.
"""

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path


def slugify_title(text: str, max_length: int = 20) -> str:
    """Creates a clean, short tmux window title from prompt text.

    Args:
        text: Input string or prompt.
        max_length: Maximum allowed length for the slug.

    Returns:
        Sanitized title string suitable for tmux window naming.
    """
    cleaned = re.sub(r"[^a-zA-Z0-9_\-]+", "-", text.strip().lower())
    cleaned = cleaned.strip("-")
    if not cleaned:
        return "agent"
    return cleaned[:max_length].rstrip("-")


def build_agent_command(
    *,
    prompt: str | None = None,
    conversation_id: str | None = None,
    agent_name: str | None = None,
    model: str | None = None,
    continue_recent: bool = False,
    extra_flags: Sequence[str] | None = None,
) -> str:
    """Constructs the shell command string to launch agy.

    Args:
        prompt: Optional initial prompt to pass interactively.
        conversation_id: Existing conversation ID to resume.
        agent_name: Specific agent persona or profile to invoke.
        model: Optional model override (e.g. flash_lite, flash, pro).
        continue_recent: Whether to continue the most recent session.
        extra_flags: Additional CLI arguments for agy.

    Returns:
        Shell command string formatted for tmux window/pane execution.
    """
    parts = ["agy"]

    if conversation_id:
        parts.extend(["--conversation", conversation_id])
    elif continue_recent:
        parts.append("--continue")

    if agent_name:
        parts.extend(["--agent", agent_name])

    if model:
        parts.extend(["--model", model])

    if prompt and not conversation_id and not continue_recent:
        parts.extend(["-i", prompt])

    if extra_flags:
        parts.extend(extra_flags)

    return shlex.join(parts)


def run_command_safely(
    args: Sequence[str],
    *,
    cwd: Path | None = None,
) -> tuple[int, str, str]:
    """Runs a subprocess command hermetically and captures output.

    Args:
        args: Command arguments to execute.
        cwd: Working directory for the process.

    Returns:
        Tuple of (returncode, stdout, stderr).
    """
    result = subprocess.run(
        list(args),
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def create_api_conversation(
    prompt: str,
    *,
    title: str | None = None,
    model: str | None = None,
    profile: str | None = None,
    cwd: Path | None = None,
) -> str | None:
    """Spawns a new conversation via agentapi and returns the ID.

    Args:
        prompt: Initial prompt for the agent conversation.
        title: Optional metadata title for the conversation.
        model: Optional model tier (flash_lite, flash, pro).
        profile: Optional execution profile.
        cwd: Working directory.

    Returns:
        Conversation ID string on success, or None on failure.
    """
    cmd = ["agentapi", "new-conversation"]
    if model:
        cmd.append(f"--model={model}")
    if title:
        cmd.append(f"--title={title}")
    if profile:
        cmd.append(f"--profile={profile}")
    cmd.append(prompt)

    code, stdout, stderr = run_command_safely(cmd, cwd=cwd)
    if code != 0 or not stdout:
        sys.stderr.write(f"agentapi new-conversation failed: {stderr}\n")
        return None

    try:
        data = json.loads(stdout)
        if isinstance(data, dict):
            return str(
                data.get("conversationId")
                or data.get("conversation_id")
                or data.get("id", "")
            )
    except json.JSONDecodeError:
        pass

    return stdout.splitlines()[0].strip()


def dispatch_to_tmux(
    *,
    command_str: str,
    title: str,
    dispatch_mode: str = "window",
    target_pane: str | None = None,
    cwd: Path | None = None,
    detached: bool = True,
    dry_run: bool = False,
) -> Mapping[str, str]:
    """Executes tmux command to create window or pane running the agent.

    Args:
        command_str: The shell command to run inside the tmux pane.
        title: Name for the window.
        dispatch_mode: One of 'window', 'split-h', 'split-v'.
        target_pane: Specific anchor pane ID or index for splitting.
        cwd: Working directory for the pane.
        detached: If True, do not change current client focus.
        dry_run: If True, returns planned commands without running.

    Returns:
        Mapping containing target identifiers (e.g. window_id, pane_id).
    """
    effective_cwd = str(cwd.resolve()) if cwd else os.getcwd()

    if dispatch_mode == "window":
        tmux_cmd = ["tmux", "new-window"]
        if detached:
            tmux_cmd.append("-d")
        tmux_cmd.extend(["-n", title, "-c", effective_cwd, "-P", "-F"])
        tmux_cmd.append("#{window_id} #{pane_id}")
        tmux_cmd.append(command_str)
    elif dispatch_mode == "split-h":
        tmux_cmd = ["tmux", "split-window", "-h"]
        if detached:
            tmux_cmd.append("-d")
        if target_pane:
            tmux_cmd.extend(["-t", target_pane])
        tmux_cmd.extend(["-c", effective_cwd, "-P", "-F", "#{pane_id}"])
        tmux_cmd.append(command_str)
    elif dispatch_mode == "split-v":
        tmux_cmd = ["tmux", "split-window", "-v"]
        if detached:
            tmux_cmd.append("-d")
        if target_pane:
            tmux_cmd.extend(["-t", target_pane])
        tmux_cmd.extend(["-c", effective_cwd, "-P", "-F", "#{pane_id}"])
        tmux_cmd.append(command_str)
    else:
        raise ValueError(f"Unknown dispatch mode: {dispatch_mode}")

    if dry_run:
        return {
            "status": "dry_run",
            "dispatch_mode": dispatch_mode,
            "command": shlex.join(tmux_cmd),
            "inner_command": command_str,
        }

    code, stdout, stderr = run_command_safely(tmux_cmd)
    if code != 0:
        raise RuntimeError(f"tmux execution failed ({code}): {stderr}")

    parts = stdout.split()
    if dispatch_mode == "window" and len(parts) >= 2:
        return {
            "status": "created",
            "window_id": parts[0],
            "pane_id": parts[1],
            "title": title,
        }

    return {
        "status": "created",
        "pane_id": parts[0] if parts else "",
        "title": title,
    }


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parses command line arguments.

    Args:
        argv: Command line arguments to parse.

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        description="Dispatch AI agent sessions into tmux windows and panes."
    )
    parser.add_argument(
        "--prompt",
        "-p",
        help="Initial prompt to pass to the agent session.",
    )
    parser.add_argument(
        "--title",
        "-t",
        help="Custom title for the tmux window (defaults to prompt slug).",
    )
    parser.add_argument(
        "--conversation",
        "-c",
        help="Attach to an existing conversation ID.",
    )
    parser.add_argument(
        "--continue",
        dest="continue_recent",
        action="store_true",
        help="Continue the most recent agy conversation.",
    )
    parser.add_argument(
        "--agent",
        help="Agent persona or profile for the session.",
    )
    parser.add_argument(
        "--model",
        choices=["flash_lite", "flash", "pro"],
        help="Model tier for the session.",
    )
    parser.add_argument(
        "--mode",
        choices=["window", "split-h", "split-v"],
        default="window",
        help="Dispatch surface: new window or split pane (default: window).",
    )
    parser.add_argument(
        "--method",
        choices=["interactive", "api"],
        default="interactive",
        help=(
            "Launch method: 'interactive' (direct agy TUI) or 'api' "
            "(agentapi new-conversation followed by agy attach)."
        ),
    )
    parser.add_argument(
        "--target-pane",
        help="Anchor pane ID or index for split modes (defaults to $TMUX_PANE).",
    )
    parser.add_argument(
        "--cwd",
        type=Path,
        help="Working directory for the agent (defaults to current dir).",
    )
    parser.add_argument(
        "--focus",
        action="store_true",
        help="Switch user focus to the new window/pane (default is detached).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned commands as JSON without executing.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output structured JSON result.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Main execution entrypoint for agent dispatching.

    Args:
        argv: Command line arguments.

    Returns:
        Integer exit code (0 for success, non-zero for failure).
    """
    args = parse_arguments(argv)

    if not args.prompt and not args.conversation and not args.continue_recent:
        sys.stderr.write(
            "Error: Must specify at least one of --prompt, --conversation, "
            "or --continue.\n"
        )
        return 1

    title = args.title
    if not title:
        if args.prompt:
            title = slugify_title(args.prompt)
        elif args.conversation:
            title = f"conv-{args.conversation[:8]}"
        else:
            title = "agy-session"

    conv_id = args.conversation
    if args.method == "api" and args.prompt and not conv_id and not args.dry_run:
        conv_id = create_api_conversation(
            prompt=args.prompt,
            title=title,
            model=args.model,
            cwd=args.cwd,
        )
        if not conv_id:
            return 1

    agent_cmd = build_agent_command(
        prompt=args.prompt if args.method != "api" else None,
        conversation_id=conv_id,
        agent_name=args.agent,
        model=args.model,
        continue_recent=args.continue_recent,
    )

    target_pane = args.target_pane or os.environ.get("TMUX_PANE")

    try:
        res = dispatch_to_tmux(
            command_str=agent_cmd,
            title=title,
            dispatch_mode=args.mode,
            target_pane=target_pane,
            cwd=args.cwd,
            detached=not args.focus,
            dry_run=args.dry_run,
        )
    except (RuntimeError, ValueError) as exc:
        sys.stderr.write(f"Dispatch error: {exc}\n")
        return 1

    output_data: dict[str, str] = dict(res)
    if conv_id:
        output_data["conversation_id"] = conv_id

    if args.json or args.dry_run:
        print(json.dumps(output_data, indent=2))
    else:
        status = output_data.get("status", "done")
        target_info = output_data.get("window_id") or output_data.get("pane_id", "")
        print(f"Agent dispatched successfully ({status}) -> {target_info}")
        if conv_id:
            print(f"Conversation ID: {conv_id}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
