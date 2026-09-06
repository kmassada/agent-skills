#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""ASCII & Unicode hygiene linter and auto-fixer for Markdown documents.

Detects and replaces ambiguous characters, smart quotes, en/em-dashes,
and non-basic ASCII glyphs that trigger VS Code's unicodeHighlight warnings.
"""

import argparse
import sys
from pathlib import Path

REPLACEMENTS = {
    "\u2013": "-",  # En-dash (1–2s -> 1-2s)
    "\u2014": "--",  # Em-dash (word—word -> word--word)
    "\u2018": "'",  # Left single quote
    "\u2019": "'",  # Right single quote
    "\u201c": '"',  # Left double quote
    "\u201d": '"',  # Right double quote
    "\u2026": "...",  # Ellipsis
    "\u276f": ">",  # Heavy right-pointing angle (❯)
    "\u2192": "->",  # Right arrow (→)
    "\u2022": "*",  # Bullet (•)
    "\u00a0": " ",  # Non-breaking space
    "\u200b": "",  # Zero-width space
}

# Standard Unicode box-drawing characters (used in ASCII-art tree diagrams)
ALLOWED_BOX_DRAWING = set("─│┌┐└┘├┤┬┴┼═║╒╓╔╕╖╗╘╙╚╛╜╝╞╟╠╡╢╣╤╥╦╧╨╩╪╫╬")


def process_file(
    file_path: Path, fix: bool, check_all: bool = False
) -> tuple[int, list[str]]:
    """Inspects and optionally fixes non-basic ASCII characters in a file."""
    try:
        content = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return 1, [f"Failed to read {file_path}: {e}"]

    issues = []
    modified_content = []

    for line_num, line in enumerate(content.splitlines(keepends=True), 1):
        new_line = line

        for orig, repl in REPLACEMENTS.items():
            if orig in new_line:
                # Don't auto-replace inside rule definition lines explaining the characters
                if "U+276F" in new_line and orig == "\u276f":
                    continue
                if "U+2018" in new_line or "U+201C" in new_line or "U+2014" in new_line:
                    continue

                count = new_line.count(orig)
                char_name = f"U+{ord(orig):04X} ('{orig}')"
                issues.append(
                    f"{file_path}:{line_num}: Found {count}x {char_name} -> suggest '{repl}'"
                )
                if fix:
                    new_line = new_line.replace(orig, repl)

        if not fix:
            for col_num, ch in enumerate(line, 1):
                if ord(ch) > 127 and ch not in REPLACEMENTS:
                    if not check_all and ch in ALLOWED_BOX_DRAWING:
                        continue
                    issues.append(
                        f"{file_path}:{line_num}:{col_num}: Non-basic ASCII U+{ord(ch):04X} ('{ch}')"
                    )

        modified_content.append(new_line)

    if fix and issues:
        file_path.write_text("".join(modified_content), encoding="utf-8")

    return len(issues), issues


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Lint and fix non-basic ASCII characters in Markdown"
    )
    parser.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help="Files or directories to inspect",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Automatically replace common homoglyphs and dashes",
    )
    parser.add_argument(
        "--check-all",
        action="store_true",
        help="Also flag standard box-drawing tree characters",
    )
    args = parser.parse_args()

    total_issues = 0
    files_checked = 0

    for target in args.paths:
        if target.is_file() and target.suffix == ".md":
            files = [target]
        elif target.is_dir():
            files = [p for p in target.rglob("*.md") if ".git" not in p.parts]
        else:
            continue

        for f in files:
            files_checked += 1
            count, issues = process_file(f, fix=args.fix, check_all=args.check_all)
            total_issues += count
            for issue in issues:
                print(issue)

    action_str = "fixed" if args.fix else "flagged"
    if total_issues > 0:
        print(f"\n{total_issues} issue(s) {action_str} across {files_checked} file(s).")
        if not args.fix:
            sys.exit(1)
    else:
        print(f"Clean! Checked {files_checked} file(s) with zero ASCII issues.")


if __name__ == "__main__":
    main()
