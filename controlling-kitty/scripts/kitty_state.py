#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Inspects and queries Kitty terminal emulator hierarchy and state via JSON."""

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from typing import Any


def query_kitty_ls(
    socket: str | None = None,
) -> Sequence[Mapping[str, Any]]:
    """Queries `kitty @ ls` and returns parsed OS-windows hierarchy.

    Args:
        socket: Optional Kitty socket path or UNIX socket address.

    Returns:
        Sequence of OS-window mappings containing tabs and windows.
    """
    cmd = ["kitty", "@"]
    effective_socket = socket or os.environ.get("KITTY_LISTEN_ON")
    if effective_socket:
        cmd.extend(["--to", effective_socket])
    cmd.append("ls")

    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    parsed = json.loads(res.stdout)
    if isinstance(parsed, list):
        return parsed
    return []


def extract_tabs(
    os_windows: Sequence[Mapping[str, Any]],
) -> Sequence[Mapping[str, Any]]:
    """Extracts all tabs across all OS windows in a flat sequence.

    Args:
        os_windows: Parsed OS-windows structure from `kitty @ ls`.

    Returns:
        Sequence of tab dictionary objects.
    """
    tabs: list[dict[str, Any]] = []
    for os_win in os_windows:
        os_id = os_win.get("id")
        for tab in os_win.get("tabs", []):
            item = dict(tab)
            item["os_window_id"] = os_id
            tabs.append(item)
    return tabs


def extract_windows(
    os_windows: Sequence[Mapping[str, Any]],
) -> Sequence[Mapping[str, Any]]:
    """Extracts all windows (panes/splits) across all tabs in a flat sequence.

    Args:
        os_windows: Parsed OS-windows structure from `kitty @ ls`.

    Returns:
        Sequence of window dictionary objects with tab and OS window context.
    """
    windows: list[dict[str, Any]] = []
    for os_win in os_windows:
        os_id = os_win.get("id")
        for tab in os_win.get("tabs", []):
            tab_id = tab.get("id")
            tab_title = tab.get("title", "")
            for win in tab.get("windows", []):
                item = dict(win)
                item["tab_id"] = tab_id
                item["tab_title"] = tab_title
                item["os_window_id"] = os_id
                windows.append(item)
    return windows


def get_current_window_id(socket: str | None = None) -> int | None:
    """Gets current Kitty window ID from environment or active window inquiry.

    Args:
        socket: Optional Kitty socket path.

    Returns:
        Integer window ID or None if unavailable.
    """
    env_id = os.environ.get("KITTY_WINDOW_ID")
    if env_id:
        try:
            return int(env_id)
        except ValueError:
            pass

    try:
        os_windows = query_kitty_ls(socket=socket)
        windows = extract_windows(os_windows)
        for win in windows:
            if win.get("is_active") or win.get("is_focused"):
                return int(win["id"])
    except (subprocess.SubprocessError, FileNotFoundError, json.JSONDecodeError):
        return None

    return None


def find_window_by_id(
    os_windows: Sequence[Mapping[str, Any]],
    window_id: int,
) -> Mapping[str, Any] | None:
    """Finds window mapping matching specified integer window ID.

    Args:
        os_windows: Parsed OS-windows structure.
        window_id: Integer window identifier.

    Returns:
        Matching window mapping or None.
    """
    windows = extract_windows(os_windows)
    for win in windows:
        if win.get("id") == window_id:
            return win
    return None


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parses command line arguments.

    Args:
        argv: Command line arguments.

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        description="Inspect and query Kitty terminal emulator state via JSON."
    )
    parser.add_argument(
        "--socket",
        "-s",
        help="Optional Kitty socket address (e.g. unix:/tmp/mykitty).",
    )
    parser.add_argument(
        "--list-tabs",
        action="store_true",
        help="List all active tabs across OS windows.",
    )
    parser.add_argument(
        "--list-windows",
        action="store_true",
        help="List all active windows (panes) across tabs.",
    )
    parser.add_argument(
        "--active-only",
        action="store_true",
        help="Filter results to only focused/active tabs or windows.",
    )
    parser.add_argument(
        "--find-window",
        type=int,
        help="Look up details for a specific window ID.",
    )
    parser.add_argument(
        "--current-id",
        action="store_true",
        help="Print the current or focused window ID.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw structured JSON.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Main CLI execution entry point for Kitty state inspection.

    Args:
        argv: Command line arguments.

    Returns:
        Exit code (0 for success, non-zero for error).
    """
    args = parse_arguments(argv)

    if args.current_id:
        curr_id = get_current_window_id(socket=args.socket)
        if curr_id is not None:
            print(curr_id)
            return 0
        sys.stderr.write("Error: Could not determine current Kitty window ID.\n")
        return 1

    try:
        os_windows = query_kitty_ls(socket=args.socket)
    except (subprocess.SubprocessError, FileNotFoundError) as exc:
        sys.stderr.write(f"Error querying kitty state: {exc}\n")
        return 1
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"Error parsing kitty JSON output: {exc}\n")
        return 1

    if args.find_window is not None:
        target = find_window_by_id(os_windows, args.find_window)
        if not target:
            sys.stderr.write(f"Window ID {args.find_window} not found.\n")
            return 1
        print(json.dumps(target, indent=2))
        return 0

    if args.list_tabs:
        tabs = extract_tabs(os_windows)
        if args.active_only:
            tabs = [t for t in tabs if t.get("is_active") or t.get("is_focused")]
        if args.json:
            print(json.dumps(tabs, indent=2))
        else:
            for t in tabs:
                active_flag = "*" if t.get("is_active") else " "
                print(f"[{active_flag}] Tab {t.get('id')}: {t.get('title')}")
        return 0

    if args.list_windows:
        windows = extract_windows(os_windows)
        if args.active_only:
            windows = [w for w in windows if w.get("is_active") or w.get("is_focused")]
        if args.json:
            print(json.dumps(windows, indent=2))
        else:
            for w in windows:
                active_flag = "*" if w.get("is_active") else " "
                title = w.get("title", "")
                cwd = w.get("cwd", "")
                print(
                    f"[{active_flag}] Window {w.get('id')} (Tab {w.get('tab_id')}): "
                    f"{title} ({cwd})"
                )
        return 0

    # Default: output formatted full hierarchy
    if args.json:
        print(json.dumps(os_windows, indent=2))
    else:
        windows = extract_windows(os_windows)
        print(f"Found {len(os_windows)} OS Window(s), {len(windows)} Window(s).")
        for w in windows:
            active = "*" if w.get("is_active") else " "
            print(
                f"[{active}] Win {w.get('id')} | Tab {w.get('tab_id')} | {w.get('title')}"
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())
