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
from collections.abc import Mapping, Sequence
from typing import Any


def get_current_pane_id(socket: str | None = None) -> str | None:
    """Returns the current tmux pane ID from environment or display-message.

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


def list_panes(socket: str | None = None) -> Sequence[Mapping[str, Any]]:
    """Queries tmux layout and returns sequence of pane geometries.

    Args:
        socket: Optional tmux socket name.

    Returns:
        Sequence of dictionaries with id, left, top, right, and bottom bounds.
    """
    cmd = ["tmux"]
    if socket:
        cmd.extend(["-L", socket])
    cmd.extend(
        [
            "list-panes",
            "-F",
            "#{pane_id} #{pane_left} #{pane_top} #{pane_right} #{pane_bottom}",
        ]
    )
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    panes: list[dict[str, Any]] = []
    for line in res.stdout.strip().splitlines():
        if not line:
            continue
        parts = line.split()
        if len(parts) == 5:
            panes.append(
                {
                    "id": parts[0],
                    "left": int(parts[1]),
                    "top": int(parts[2]),
                    "right": int(parts[3]),
                    "bottom": int(parts[4]),
                }
            )
    return panes


def find_target_pane(
    panes: Sequence[Mapping[str, Any]], origin_id: str, direction: str
) -> str | None:
    """Finds the pane ID matching the relative direction from origin pane.

    Args:
        panes: Sequence of pane geometry mappings.
        origin_id: Identifier of the starting pane (e.g. '%0').
        direction: Target direction ('left', 'right', 'above', or 'under').

    Returns:
        Target pane ID string or None if no adjacent pane exists in that direction.
    """
    origin: Mapping[str, Any] | None = None
    for p in panes:
        if p.get("id") == origin_id:
            origin = p
            break

    if not origin:
        return None

    candidates: list[tuple[float, str]] = []
    origin_bottom = int(origin["bottom"])
    origin_top = int(origin["top"])
    origin_right = int(origin["right"])
    origin_left = int(origin["left"])

    for p in panes:
        if p.get("id") == origin_id:
            continue

        p_id = str(p["id"])
        p_bottom = int(p["bottom"])
        p_top = int(p["top"])
        p_right = int(p["right"])
        p_left = int(p["left"])

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

    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]


def main(argv: Sequence[str] | None = None) -> None:
    """Main CLI entry point for relative pane navigation script.

    Args:
        argv: Optional command-line argument sequence; defaults to sys.argv[1:].
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

    origin_id = args.pane or get_current_pane_id(args.socket)
    if not origin_id:
        print("Error: Could not determine origin pane ID.", file=sys.stderr)
        sys.exit(1)

    panes = list_panes(args.socket)
    target_id = find_target_pane(panes, origin_id, args.direction)

    if not target_id:
        msg = f"No pane found to the {args.direction} of {origin_id}."
        print(msg, file=sys.stderr)
        sys.exit(1)

    print(target_id)
    if args.select:
        select_cmd = ["tmux"]
        if args.socket:
            select_cmd.extend(["-L", args.socket])
        select_cmd.extend(["select-pane", "-t", target_id])
        subprocess.run(select_cmd, check=True)


if __name__ == "__main__":
    main()
