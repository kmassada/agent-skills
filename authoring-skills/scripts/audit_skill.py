#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Audits an agent skill directory against cross-platform quality rules.

Validates frontmatter standards, markdown structure, relative link integrity,
eval schemas, and script conventions for Google Antigravity and Claude Code.

Usage:
    python3 audit_skill.py <path/to/skill_directory> [--markdown-only] [--strict]
"""

import argparse
import ast
import json
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

NAME_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MAX_NAME_LENGTH = 64
MAX_DESC_LENGTH = 1024
MAX_SKILL_MD_LINES = 500


@dataclass
class AuditResult:
    """Holds audit findings including errors, warnings, and recommendations."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """Returns True if there are zero blocking errors."""
        return len(self.errors) == 0


def parse_frontmatter(
    content: str,
) -> tuple[Mapping[str, Any], str, Sequence[str]]:
    """Extracts and parses YAML frontmatter without external YAML dependencies.

    Args:
        content: Raw markdown text containing frontmatter between '---' markers.

    Returns:
        Tuple of (parsed_mapping, raw_frontmatter_text, errors_sequence).
    """
    errors: list[str] = []
    if not content.startswith("---"):
        errors.append("SKILL.md does not start with YAML frontmatter delimiter '---'.")
        return {}, "", errors

    parts = re.split(r"^---\r?\n", content, flags=re.MULTILINE)
    if len(parts) < 3:
        errors.append("SKILL.md frontmatter is unclosed (missing second '---' line).")
        return {}, "", errors

    frontmatter_text = parts[1]
    data: dict[str, Any] = {}
    lines = frontmatter_text.splitlines()

    current_key: str | None = None
    current_val_lines: list[str] = []
    block_mode: str | None = None

    def finalize_key() -> None:
        nonlocal current_key, current_val_lines, block_mode
        if not current_key:
            return
        if block_mode in ("folded", "literal"):
            joined = (
                " ".join(line.strip() for line in current_val_lines)
                if block_mode == "folded"
                else "\n".join(current_val_lines).strip()
            )
            data[current_key] = joined.strip()
        else:
            val_str = " ".join(line.strip() for line in current_val_lines).strip()
            if (val_str.startswith('"') and val_str.endswith('"')) or (
                val_str.startswith("'") and val_str.endswith("'")
            ):
                val_str = val_str[1:-1]
            data[current_key] = val_str

        current_key = None
        current_val_lines = []
        block_mode = None

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        key_match = re.match(r"^([a-zA-Z0-9_-]+):\s*(.*)$", line)
        if key_match and not line.startswith(" "):
            finalize_key()
            current_key = key_match.group(1)
            raw_val = key_match.group(2).strip()
            if raw_val in (">-", ">"):
                block_mode = "folded"
            elif raw_val in ("|-", "|"):
                block_mode = "literal"
            elif raw_val:
                current_val_lines.append(raw_val)
        elif current_key and (line.startswith("  ") or line.startswith("\t")):
            current_val_lines.append(stripped)

    finalize_key()
    return data, frontmatter_text, errors


def audit_frontmatter(
    raw_frontmatter: str, meta: Mapping[str, Any], result: AuditResult
) -> None:
    """Audits YAML frontmatter syntax, name conventions, and trigger descriptions.

    Args:
        raw_frontmatter: Unparsed frontmatter text.
        meta: Parsed metadata mapping.
        result: AuditResult container to populate findings.
    """
    # Check frontmatter line length (MD013)
    for idx, line in enumerate(raw_frontmatter.splitlines(), start=1):
        if len(line) > 80:
            result.errors.append(
                f"Frontmatter line {idx} exceeds 80 characters ({len(line)} cols). "
                "Format YAML frontmatter manually."
            )

    # 1. Skill Name
    name = meta.get("name")
    if not name or not isinstance(name, str):
        result.errors.append("Missing or non-string 'name' in frontmatter.")
    else:
        if len(name) > MAX_NAME_LENGTH:
            result.errors.append(
                f"Skill name '{name}' exceeds {MAX_NAME_LENGTH} characters "
                f"({len(name)} chars)."
            )
        if not NAME_PATTERN.match(name):
            result.errors.append(
                f"Skill name '{name}' must be lowercase alphanumeric with single "
                "hyphens (regex: ^[a-z0-9]+(-[a-z0-9]+)*$)."
            )
        elif not (
            name.endswith("ing") or "-ing" in name or name.split("-")[0].endswith("ing")
        ):
            result.recommendations.append(
                f"Skill name '{name}' does not appear to use the Gerund form "
                "(verb + -ing, e.g., 'authoring-skills')."
            )

    # 2. Description
    desc = meta.get("description")
    if not desc or not isinstance(desc, str):
        result.errors.append("Missing or non-string 'description' in frontmatter.")
        return

    desc_clean = desc.strip()
    if len(desc_clean) > MAX_DESC_LENGTH:
        result.errors.append(
            f"Description exceeds {MAX_DESC_LENGTH} characters "
            f"({len(desc_clean)} chars)."
        )

    if re.search(r"<[^>]+>", desc_clean):
        result.errors.append(
            "Description contains XML/HTML angle brackets, which may corrupt routing."
        )

    lower_desc = desc_clean.lower()
    first_word = desc_clean.split()[0] if desc_clean.split() else ""
    if first_word.lower() in ("i", "you", "we", "this"):
        result.warnings.append(
            f"Description starts with '{first_word}'. Descriptions should start with "
            "a third-person capability verb phrase (e.g., 'Guides the creation...')."
        )

    pos_triggers = ("use when", "use for", "use this", "trigger when", "designed to")
    if not any(t in lower_desc for t in pos_triggers):
        result.warnings.append(
            "Description should explicitly specify positive triggers ('Use when...')."
        )

    neg_triggers = (
        "don't use",
        "do not use",
        "never use",
        "not intended for",
        "not for",
    )
    if not any(t in lower_desc for t in neg_triggers):
        result.warnings.append(
            "Description should explicitly specify negative guardrails "
            "('Don't use for...')."
        )


def audit_markdown_content(content: str, skill_dir: Path, result: AuditResult) -> None:
    """Audits markdown document layout, code blocks, lists, and relative links.

    Args:
        content: Complete markdown text of SKILL.md.
        skill_dir: Directory containing the skill.
        result: AuditResult container to populate findings.
    """
    lines = content.splitlines()

    # 1. Line Budget Check
    if len(lines) > MAX_SKILL_MD_LINES:
        result.warnings.append(
            f"SKILL.md exceeds {MAX_SKILL_MD_LINES} lines ({len(lines)} lines). "
            "Offload reference documentation to references/ to respect context budget."
        )

    # 2. Document Title
    body_lines = [line for line in lines if not line.startswith("---")]
    h1_found = any(line.startswith("# ") for line in body_lines)
    if not h1_found:
        result.errors.append(
            "SKILL.md must contain a top-level '# [Skill Name]' heading."
        )

    # 3. Redundant Frontmatter Markers
    for idx, line in enumerate(lines, start=1):
        if re.match(r"^\s*\*\*(Name|Description):\*\*", line):
            result.warnings.append(
                f"Line {idx}: Redundant '**{line.strip()}**' in markdown body. "
                "Frontmatter is the single source of truth."
            )

    # 4. Code Blocks and List Spacing
    in_code_block = False
    in_list = False
    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            in_list = False
            continue

        if in_code_block:
            continue

        if not stripped:
            in_list = False
            continue

        # Broken code block detection (e.g. `python or ``python instead of ```python)
        if re.match(r"^`{1,2}[a-zA-Z0-9_-]+$", stripped):
            result.errors.append(
                f"Line {idx}: Malformed code block opening '{stripped}'. "
                "Code blocks must begin with three backticks (```)."
            )

        is_list_item = bool(re.match(r"^(\*|-|\d+\.)\s+", stripped))
        if is_list_item:
            if not in_list and idx > 1:
                prev_line = lines[idx - 2].strip()
                if prev_line and not bool(
                    re.match(r"^(\*|-|\d+\.|#|>|---|\|)", prev_line)
                ):
                    result.warnings.append(
                        f"Line {idx}: List item '{stripped[:30]}...' immediately "
                        "follows text without a blank separating line. "
                        "This may cause markdown compression."
                    )
            in_list = True

    # 5. Link Integrity (Verify relative markdown links point to existing files)
    link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
    for idx, line in enumerate(lines, start=1):
        for match in link_pattern.finditer(line):
            link_target = match.group(2).split("#")[0].strip()
            if not link_target or link_target.startswith(
                ("http://", "https://", "mailto:")
            ):
                continue

            target_path = (skill_dir / link_target).resolve()
            if not target_path.exists():
                result.errors.append(
                    f"Line {idx}: Broken relative link '{link_target}' "
                    "target does not exist."
                )


def audit_scripts(skill_dir: Path, result: AuditResult) -> None:
    """Audits helper scripts in scripts/ and evals/ for executable shebang and syntax.

    Args:
        skill_dir: Directory containing the skill.
        result: AuditResult container to populate findings.
    """
    for folder_name in ("scripts", "evals"):
        folder = skill_dir / folder_name
        if not folder.is_dir():
            continue

        for script_path in folder.iterdir():
            if not script_path.is_file() or script_path.name.startswith("."):
                continue
            if script_path.suffix not in (".py", ".sh"):
                continue

            rel_path = script_path.relative_to(skill_dir)
            try:
                content = script_path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError) as e:
                result.warnings.append(
                    f"Script '{rel_path}' could not be read as UTF-8 text: {e}"
                )
                continue

            if script_path.suffix == ".py":
                lines = content.splitlines()
                if not lines or not lines[0].startswith("#!/usr/bin/env python3"):
                    result.warnings.append(
                        f"Script '{rel_path}' missing standard shebang "
                        "'#!/usr/bin/env python3' on line 1."
                    )
                try:
                    ast.parse(content, filename=str(script_path))
                except SyntaxError as e:
                    result.errors.append(
                        f"Python script '{rel_path}' contains syntax error: {e}"
                    )

            elif script_path.suffix == ".sh":
                lines = content.splitlines()
                if not lines or not lines[0].startswith(
                    ("#!/bin/bash", "#!/usr/bin/env bash", "#!/bin/sh")
                ):
                    result.warnings.append(
                        f"Shell script '{rel_path}' missing standard shebang "
                        "'#!/usr/bin/env bash' on line 1."
                    )


def audit_evals_json(
    skill_dir: Path, skill_name: str | None, result: AuditResult
) -> None:
    """Audits evals/evals.json against schema conventions if present.

    Args:
        skill_dir: Directory containing the skill.
        skill_name: Expected skill name from SKILL.md.
        result: AuditResult container to populate findings.
    """
    evals_file = skill_dir / "evals" / "evals.json"
    if not evals_file.is_file():
        result.recommendations.append(
            "No evals/evals.json benchmark suite found. "
            "Consider adding automated evaluation cases."
        )
        return

    try:
        data = json.loads(evals_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        result.errors.append(f"evals/evals.json is not valid JSON: {e}")
        return

    if not isinstance(data, dict):
        result.errors.append("evals/evals.json root must be a JSON object.")
        return

    json_skill_name = data.get("skill_name")
    if skill_name and json_skill_name != skill_name:
        result.errors.append(
            f"evals/evals.json skill_name '{json_skill_name}' "
            f"does not match SKILL.md name '{skill_name}'."
        )

    cases = data.get("evals")
    if not isinstance(cases, list) or not cases:
        result.errors.append("evals/evals.json must contain a non-empty 'evals' array.")
        return

    for idx, case in enumerate(cases, start=1):
        if not isinstance(case, dict):
            result.errors.append(f"evals/evals.json case #{idx} is not an object.")
            continue

        for req_field in ("id", "prompt", "expected_output", "expectations"):
            if req_field not in case:
                result.errors.append(
                    f"evals/evals.json case #{idx} is missing required field "
                    f"'{req_field}'."
                )

        prompt = case.get("prompt", "")
        if isinstance(prompt, str):
            lower_prompt = prompt.lower()
            if any(
                tool in lower_prompt
                for tool in ("run_command", "view_file", "write_to_file")
            ):
                cid = case.get("id", idx)
                result.warnings.append(
                    f"evals/evals.json case #{cid}: Prompt mentions specific "
                    "tool names. Evals should describe the authentic task "
                    "outcome, not dictate tool usage."
                )


def audit_skill(skill_dir: Path, markdown_only: bool = False) -> AuditResult:
    """Executes full quality audit across a target skill directory.

    Args:
        skill_dir: Path to the skill directory to audit.
        markdown_only: If True, skips script and evals validation.

    Returns:
        Populated AuditResult instance.
    """
    result = AuditResult()
    skill_file = skill_dir / "SKILL.md"

    if not skill_file.is_file():
        result.errors.append(
            f"Target directory '{skill_dir}' missing required SKILL.md file."
        )
        return result

    content = skill_file.read_text(encoding="utf-8")
    meta, raw_frontmatter, fm_errors = parse_frontmatter(content)
    result.errors.extend(fm_errors)

    if meta:
        audit_frontmatter(raw_frontmatter, meta, result)

    audit_markdown_content(content, skill_dir, result)

    if not markdown_only:
        audit_scripts(skill_dir, result)
        audit_evals_json(skill_dir, meta.get("name"), result)

    return result


def main(argv: Sequence[str] | None = None) -> int:
    """CLI orchestrator for skill auditing.

    Args:
        argv: Optional command-line argument sequence.

    Returns:
        Exit code: 0 if passed, 1 if blocking errors found.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Audit an agent skill directory against quality and formatting standards."
        )
    )
    parser.add_argument("skill_dir", help="Path to the skill directory to audit.")
    parser.add_argument(
        "--markdown-only",
        action="store_true",
        help="Audit only SKILL.md, skipping scripts and evals.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as blocking errors.",
    )
    args = parser.parse_args(argv)

    target_dir = Path(args.skill_dir).resolve()
    if not target_dir.is_dir():
        print(f"Error: Directory '{target_dir}' does not exist.", file=sys.stderr)
        return 1

    print(f"Auditing skill in: {target_dir}")
    print("=" * 80)

    result = audit_skill(target_dir, markdown_only=args.markdown_only)

    if result.errors:
        print("\n❌ Errors (must fix):")
        for err in result.errors:
            print(f"  • {err}")

    if result.warnings:
        print("\n⚠️ Warnings:")
        for warn in result.warnings:
            print(f"  • {warn}")

    if result.recommendations:
        print("\n💡 Recommendations:")
        for rec in result.recommendations:
            print(f"  • {rec}")

    is_failure = (not result.passed) or (args.strict and bool(result.warnings))

    if not is_failure:
        status_msg = "passed with warnings" if result.warnings else "perfectly clean"
        print(f"\n✅ Audit {status_msg}! All standards satisfied.")
        return 0

    print(f"\n❌ Audit failed with {len(result.errors)} error(s).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
