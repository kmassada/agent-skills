#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Dispatches AI agent sessions into dedicated Kitty tabs and split windows.

Supports interactive TUI launches with agy, programmatic conversation creation
via agentapi, joining ongoing conversations, and multi-pane splitting in Kitty.
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
    """Creates a clean, short window title from prompt text.

    Args:
        text: Input string or prompt.
        max_length: Maximum allowed length for the slug.

    Returns:
        Sanitized title string suitable for Kitty tab/window naming.
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
) -> list[str]:
    """Constructs the argv list used to launch agy.

    Returns an argument vector rather than a shell string: Kitty executes the
    program directly, so no shell quoting round trip is needed or wanted.

    Args:
        prompt: Optional initial prompt to pass interactively.
        conversation_id: Existing conversation ID to resume.
        agent_name: Specific agent persona or profile to invoke.
        model: Optional model override (e.g. flash_lite, flash, pro).
        continue_recent: Whether to continue the most recent session.
        extra_flags: Additional CLI arguments for agy.

    Returns:
        Argument vector for the agent process, starting with "agy".
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

    return parts


def run_command_safely(
    args: Sequence[str],
    *,
    cwd: Path | None = None,
) -> tuple[int, str, str]:
    """Runs a subprocess command with captured output.

    The child inherits this process's environment; it is not hermetic.

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
    except json.JSONDecodeError:
        # Not JSON at all: agentapi printed a bare ID on the first line.
        return stdout.splitlines()[0].strip() or None

    if isinstance(data, dict):
        found = (
            data.get("conversationId") or data.get("conversation_id") or data.get("id")
        )
        if found:
            return str(found)
        sys.stderr.write(
            "agentapi new-conversation returned JSON without a conversation ID.\n"
        )
        return None

    # Valid JSON that is not an object carries no ID; echoing it back as one
    # would send a garbage --conversation value to agy.
    sys.stderr.write(
        "agentapi new-conversation returned unexpected JSON "
        f"({type(data).__name__}); no conversation ID found.\n"
    )
    return None


def resolve_match_expression(target_window: str) -> str:
    """Validates an anchor window reference and returns a Kitty match expression.

    Kitty's --match accepts regular expressions and boolean operators, and the
    special value "all". Interpolating an unvalidated string would let a caller
    widen the match from one window to many, and `launch` would then act on an
    unintended window. Only a bare integer or an explicit "id:<int>" is allowed.

    Args:
        target_window: Anchor window reference (e.g. "14" or "id:14").

    Returns:
        A narrow match expression of the form "id:<int>".

    Raises:
        ValueError: If the reference is not a plain integer window ID.
    """
    candidate = target_window.strip()
    if candidate.startswith("id:"):
        candidate = candidate[len("id:") :]
    if not re.fullmatch(r"\d+", candidate):
        raise ValueError(
            f"Invalid target window {target_window!r}: expected an integer "
            'window ID such as "14" or "id:14".'
        )
    return f"id:{candidate}"


def dispatch_to_kitty(
    *,
    command_args: Sequence[str],
    title: str,
    dispatch_mode: str = "tab",
    target_window: str | None = None,
    cwd: Path | None = None,
    detached: bool = True,
    dry_run: bool = False,
    socket: str | None = None,
) -> Mapping[str, str]:
    """Executes kitty @ launch to create a tab or split window running the agent.

    Args:
        command_args: Argument vector to run inside the Kitty window. Passed to
            Kitty verbatim; Kitty execs it directly, without a shell.
        title: Name for the tab or window.
        dispatch_mode: One of 'tab', 'split-v', 'split-h', 'overlay', 'os-window'.
        target_window: Anchor window ID for split and overlay modes.
        cwd: Working directory for the new window.
        detached: If True, passes --keep-focus to avoid stealing focus.
        dry_run: If True, returns planned commands without running.
        socket: Optional Kitty socket path or address.

    Returns:
        Mapping containing target identifiers and execution status.

    Raises:
        ValueError: If the dispatch mode or target window is invalid.
        RuntimeError: If the Kitty launch command fails.
    """
    if not command_args:
        raise ValueError("command_args must contain at least the program name.")

    effective_cwd = str(cwd.resolve()) if cwd else os.getcwd()
    kitty_cmd = ["kitty", "@"]
    effective_socket = socket or os.environ.get("KITTY_LISTEN_ON")
    if effective_socket:
        kitty_cmd.extend(["--to", effective_socket])

    kitty_cmd.append("launch")

    if detached:
        kitty_cmd.append("--keep-focus")

    kitty_cmd.extend(["--cwd", effective_cwd])

    anchored_modes = {
        "split-v": ["--type=window", "--location=vsplit", f"--title={title}"],
        "split-h": ["--type=window", "--location=hsplit", f"--title={title}"],
        "overlay": ["--type=overlay", f"--title={title}"],
    }

    if dispatch_mode == "tab":
        kitty_cmd.extend(["--type=tab", f"--tab-title={title}"])
    elif dispatch_mode in anchored_modes:
        kitty_cmd.extend(anchored_modes[dispatch_mode])
        if target_window:
            kitty_cmd.extend(["--match", resolve_match_expression(target_window)])
    elif dispatch_mode == "os-window":
        kitty_cmd.extend(["--type=os-window", f"--title={title}"])
    else:
        raise ValueError(f"Unknown dispatch mode: {dispatch_mode}")

    # Kitty treats everything after the options as the argv to exec.
    kitty_cmd.extend(command_args)

    if dry_run:
        return {
            "status": "dry_run",
            "dispatch_mode": dispatch_mode,
            "command": shlex.join(kitty_cmd),
            "inner_command": shlex.join(command_args),
        }

    code, stdout, stderr = run_command_safely(kitty_cmd)
    if code != 0:
        raise RuntimeError(f"kitty launch failed ({code}): {stderr}")

    window_id = stdout.strip()
    return {
        "status": "created",
        "window_id": window_id,
        "title": title,
        "dispatch_mode": dispatch_mode,
    }


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parses command line arguments.

    Args:
        argv: Command line arguments to parse.

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        description="Dispatch AI agent sessions into Kitty tabs and windows."
    )
    parser.add_argument(
        "--prompt",
        "-p",
        help="Initial prompt to pass to the agent session.",
    )
    parser.add_argument(
        "--title",
        "-t",
        help="Custom title for the Kitty tab/window (defaults to prompt slug).",
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
        "--profile",
        help="Execution profile, forwarded to agentapi with --method=api.",
    )
    parser.add_argument(
        "--mode",
        choices=["tab", "split-v", "split-h", "overlay", "os-window"],
        default="tab",
        help="Dispatch surface: new tab or split window (default: tab).",
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
        "--target-window",
        help="Anchor window ID for split modes (defaults to $KITTY_WINDOW_ID).",
    )
    parser.add_argument(
        "--cwd",
        type=Path,
        help="Working directory for the agent (defaults to current dir).",
    )
    parser.add_argument(
        "--focus",
        action="store_true",
        help="Switch user focus to the new tab/window (default is detached).",
    )
    parser.add_argument(
        "--socket",
        "-s",
        help="Optional Kitty socket path or address.",
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
    """Main execution entrypoint for Kitty agent dispatching.

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

    # agy takes its task from the resumed session, so a prompt given alongside
    # them would be dropped on the floor. Say so instead of silently ignoring it.
    if args.prompt and (args.conversation or args.continue_recent):
        resume_flag = "--conversation" if args.conversation else "--continue"
        sys.stderr.write(
            f"Error: --prompt cannot be combined with {resume_flag}; the "
            "resumed session supplies its own context. Send a follow-up with "
            "'kitty @ send-text' once the session is up.\n"
        )
        return 1

    if args.profile and args.method != "api":
        sys.stderr.write("Error: --profile requires --method=api.\n")
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
    if args.method == "api" and args.prompt and not conv_id:
        if args.dry_run:
            # Keep the planned command shaped like the real one rather than
            # emitting a bare, prompt-less `agy`.
            conv_id = "<conversation-id-from-agentapi>"
        else:
            conv_id = create_api_conversation(
                prompt=args.prompt,
                title=title,
                model=args.model,
                profile=args.profile,
                cwd=args.cwd,
            )
            if not conv_id:
                return 1

    agent_cmd = build_agent_command(
        prompt=args.prompt if args.method != "api" else None,
        conversation_id=conv_id,
        agent_name=args.agent,
        # In api mode the model was already bound to the conversation; repeating
        # it on the agy side would send a second, possibly conflicting override.
        model=args.model if args.method != "api" else None,
        continue_recent=args.continue_recent,
    )

    target_window = args.target_window or os.environ.get("KITTY_WINDOW_ID")

    try:
        res = dispatch_to_kitty(
            command_args=agent_cmd,
            title=title,
            dispatch_mode=args.mode,
            target_window=target_window,
            cwd=args.cwd,
            detached=not args.focus,
            dry_run=args.dry_run,
            socket=args.socket,
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
        target_info = output_data.get("window_id", "")
        print(f"Agent dispatched successfully ({status}) -> window {target_info}")
        if conv_id:
            print(f"Conversation ID: {conv_id}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
