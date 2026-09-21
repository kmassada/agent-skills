#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Calculates relative pane navigation in tmux based on geometry layout."""

import argparse
import os
import subprocess
import sys
from collections.abc import Sequence
from typing import TypedDict


class PaneGeometry(TypedDict):
    """Bounding box of a single tmux pane, in terminal cell coordinates."""

    id: str
    left: int
    top: int
    right: int
    bottom: int


def get_current_pane_id(*, socket: str | None = None) -> str | None:
    """Returns the current tmux pane ID from environment or display-message.

    Prefers ``$TMUX_PANE``, which is pinned to the pane this process was
    launched from. The ``display-message`` fallback is focus-volatile: it
    reports whichever pane the attached client has active right now, so it is
    only a last resort when the environment variable is absent.

    Args:
        socket: Optional tmux socket name.

    Returns:
        String identifier (e.g. '%1') or None if not running inside tmux.
    """
    pane_id = os.environ.get("TMUX_PANE")
    if pane_id:
        return pane_id
    try:
        cmd = ["tmux"]
        if socket:
            cmd.extend(["-L", socket])
        cmd.extend(["display-message", "-p", "#{pane_id}"])
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        return None


def list_panes(
    origin_id: str | None = None,
    *,
    socket: str | None = None,
) -> list[PaneGeometry]:
    """Queries tmux layout and returns the pane geometries of one window.

    Always targets ``origin_id`` explicitly. A target-less ``list-panes``
    reports whichever window the user happens to have active, so a pane living
    in any other window would resolve against the wrong layout.

    Args:
        origin_id: Pane ID whose window should be listed. When None, tmux falls
            back to the active window (focus-volatile; avoid where possible).
        socket: Optional tmux socket name.

    Returns:
        List of pane geometries with id, left, top, right, and bottom bounds.
    """
    cmd = ["tmux"]
    if socket:
        cmd.extend(["-L", socket])
    cmd.append("list-panes")
    if origin_id:
        cmd.extend(["-t", origin_id])
    cmd.extend(
        [
            "-F",
            "#{pane_id} #{pane_left} #{pane_top} #{pane_right} #{pane_bottom}",
        ]
    )
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    panes: list[PaneGeometry] = []
    for line in res.stdout.strip().splitlines():
        if not line:
            continue
        parts = line.split()
        if len(parts) == 5:
            try:
                panes.append(
                    PaneGeometry(
                        id=parts[0],
                        left=int(parts[1]),
                        top=int(parts[2]),
                        right=int(parts[3]),
                        bottom=int(parts[4]),
                    )
                )
            except ValueError:
                continue
    return panes


def find_target_pane(
    panes: Sequence[PaneGeometry], origin_id: str, direction: str
) -> str | None:
    """Finds the pane ID matching the relative direction from origin pane.

    Args:
        panes: Sequence of pane geometries.
        origin_id: Identifier of the starting pane (e.g. '%0').
        direction: Target direction ('left', 'right', 'above', or 'under').

    Returns:
        Target pane ID string or None if no adjacent pane exists in that direction.
    """
    origin: PaneGeometry | None = None
    for p in panes:
        if p["id"] == origin_id:
            origin = p
            break

    if not origin:
        return None

    candidates: list[tuple[float, str]] = []
    origin_bottom = origin["bottom"]
    origin_top = origin["top"]
    origin_right = origin["right"]
    origin_left = origin["left"]

    for p in panes:
        if p["id"] == origin_id:
            continue

        p_id = p["id"]
        p_bottom = p["bottom"]
        p_top = p["top"]
        p_right = p["right"]
        p_left = p["left"]

        v_overlap = max(0, min(origin_bottom, p_bottom) - max(origin_top, p_top))
        h_overlap = max(0, min(origin_right, p_right) - max(origin_left, p_left))

        if direction == "right" and p_left >= origin_right and v_overlap > 0:
            dist = p_left - origin_right
            candidates.append((dist - (v_overlap * 0.1), p_id))
        elif direction == "left" and p_right <= origin_left and v_overlap > 0:
            dist = origin_left - p_right
            candidates.append((dist - (v_overlap * 0.1), p_id))
        elif direction == "under" and p_top >= origin_bottom and h_overlap > 0:
            dist = p_top - origin_bottom
            candidates.append((dist - (h_overlap * 0.1), p_id))
        elif direction == "above" and p_bottom <= origin_top and h_overlap > 0:
            dist = origin_top - p_bottom
            candidates.append((dist - (h_overlap * 0.1), p_id))

    if not candidates:
        return None

    candidates.sort(key=lambda x: (x[0], x[1]))
    return candidates[0][1]


def main(argv: Sequence[str] | None = None) -> int:
    """Main CLI entry point for relative pane navigation script.

    Args:
        argv: Optional command-line argument sequence; defaults to sys.argv[1:].

    Returns:
        Integer exit code (0 for success, non-zero for failure).
    """
    parser = argparse.ArgumentParser(
        description="Find relative tmux pane by direction."
    )
    parser.add_argument(
        "--direction",
        required=True,
        choices=["left", "right", "above", "under"],
        help="Direction relative to origin pane.",
    )
    parser.add_argument(
        "--pane",
        default=None,
        help="Origin pane ID (defaults to $TMUX_PANE).",
    )
    parser.add_argument(
        "--select",
        action="store_true",
        help="Select the target pane automatically in tmux.",
    )
    parser.add_argument(
        "--socket",
        "-L",
        default=None,
        help="Optional tmux socket name.",
    )

    args = parser.parse_args(argv)

    origin_id = args.pane or get_current_pane_id(socket=args.socket)
    if not origin_id:
        print("Error: Could not determine origin pane ID.", file=sys.stderr)
        return 1

    panes = list_panes(origin_id, socket=args.socket)
    target_id = find_target_pane(panes, origin_id, args.direction)

    if not target_id:
        msg = f"No pane found to the {args.direction} of {origin_id}."
        print(msg, file=sys.stderr)
        return 1

    print(target_id)
    if args.select:
        select_cmd = ["tmux"]
        if args.socket:
            select_cmd.extend(["-L", args.socket])
        select_cmd.extend(["select-pane", "-t", target_id])
        subprocess.run(select_cmd, check=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
