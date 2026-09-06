#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Auto-generates README.md catalog from skill frontmatter in agent-skills.

Zero-dependency Python script that:
1. Scans all skill directories for SKILL.md.
2. Extracts and parses YAML frontmatter (name, description, etc.).
3. Detects subcomponents (evals, references, scripts, templates).
4. Injects a formatted catalog table and detailed index into README.md.
5. Enforces 80-character line wrapping and strict basic ASCII hygiene.
"""

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


def parse_frontmatter(content: str) -> Mapping[str, Any]:
    """Parses YAML frontmatter without external dependencies.

    Args:
        content: Raw markdown text containing frontmatter between '---' markers.

    Returns:
        Mapping containing parsed key-value pairs and block scalars.
    """
    match = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n(.*)$", content, re.DOTALL)
    if not match:
        return {}

    frontmatter_text = match.group(1)
    data = {}
    lines = frontmatter_text.splitlines()

    current_key: str | None = None
    current_val_lines: list[str] = []
    block_mode: str | None = None

    def finalize_key():
        nonlocal current_key, current_val_lines, block_mode
        if not current_key:
            return
        if block_mode == "folded":
            folded = " ".join(line.strip() for line in current_val_lines)
            data[current_key] = folded.strip()
        elif block_mode == "literal":
            data[current_key] = "\n".join(current_val_lines).strip()
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

        key_match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if key_match and not line.startswith(" ") and not line.startswith("\t"):
            finalize_key()
            key = key_match.group(1)
            raw_val = key_match.group(2).strip()

            if raw_val in (">", ">-", ">+"):
                current_key = key
                block_mode = "folded"
                current_val_lines = []
            elif raw_val in ("|", "|-", "|+"):
                current_key = key
                block_mode = "literal"
                current_val_lines = []
            elif raw_val:
                current_key = key
                block_mode = None
                current_val_lines = [raw_val]
            else:
                current_key = key
                block_mode = None
                current_val_lines = []
        else:
            if current_key is not None:
                current_val_lines.append(line.strip())

    finalize_key()
    return data


def wrap_text(text: str, width: int = 80, prefix: str = "") -> str:
    """Hard-wraps text to a given width with an optional prefix.

    Args:
        text: Input text string to wrap.
        width: Maximum line length in characters.
        prefix: Line prefix string applied to wrapped lines.

    Returns:
        Hard-wrapped multiline string.
    """
    words = text.split()
    if not words:
        return prefix.rstrip()

    lines = []
    current_line = prefix

    for word in words:
        test_line = (
            f"{current_line} {word}".strip()
            if current_line != prefix
            else f"{prefix}{word}"
        )
        if len(test_line) <= width:
            current_line = test_line
        else:
            if current_line.strip():
                lines.append(current_line)
            current_line = f"{prefix}{word}"

    if current_line.strip():
        lines.append(current_line)

    return "\n".join(lines)


def sanitize_ascii(text: str) -> str:
    """Replaces Unicode quotes, dashes, and symbols with basic ASCII.

    Args:
        text: Text string potentially containing non-basic ASCII characters.

    Returns:
        Sanitized string containing only basic ASCII replacements.
    """
    replacements = {
        "\u2013": "-",
        "\u2014": "--",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2026": "...",
        "\u276f": ">",
        "\u2192": "->",
        "\u2022": "*",
        "\u00a0": " ",
        "\u200b": "",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text


def format_markdown(file_path: Path) -> None:
    """Formats a markdown file using prettier and markdownlint if available.

    Args:
        file_path: Target Markdown file path to format in place.
    """
    prettier_bin = shutil.which("prettier")
    npx_bin = shutil.which("npx")
    if prettier_bin:
        cmd = [
            prettier_bin,
            "--write",
            "--prose-wrap",
            "always",
            "--print-width",
            "80",
            str(file_path),
        ]
        subprocess.run(cmd, capture_output=True, text=True, check=False)
    elif npx_bin:
        cmd = [
            npx_bin,
            "prettier",
            "--write",
            "--prose-wrap",
            "always",
            "--print-width",
            "80",
            str(file_path),
        ]
        subprocess.run(cmd, capture_output=True, text=True, check=False)

    mdlint_bin = shutil.which("markdownlint")
    if mdlint_bin:
        config_args = []
        for candidate in [
            file_path.parent / "writing-markdown" / ".markdownlint.json",
            file_path.parent.parent / "writing-markdown" / ".markdownlint.json",
        ]:
            if candidate.is_file():
                config_args = ["--config", str(candidate)]
                break

        subprocess.run(
            [mdlint_bin, "--fix"] + config_args + [str(file_path)],
            capture_output=True,
            text=True,
            check=False,
        )


def collect_skills(repo_root: Path) -> Sequence[Mapping[str, Any]]:
    """Discovers all skills with SKILL.md in immediate subdirectories.

    Args:
        repo_root: Path to repository root directory.

    Returns:
        Sequence of mappings containing parsed skill metadata and component flags.
    """
    skills = []
    for item in sorted(repo_root.iterdir()):
        if not item.is_dir() or item.name.startswith((".", "_")):
            continue

        skill_md = item / "SKILL.md"
        if not skill_md.is_file():
            continue

        raw_content = skill_md.read_text(encoding="utf-8")
        meta = parse_frontmatter(raw_content)

        name = meta.get("name", item.name)
        description = meta.get("description", "").strip()

        has_evals = (item / "evals" / "evals.json").is_file()
        has_scripts = (item / "scripts").is_dir() and any((item / "scripts").iterdir())
        has_refs = (item / "references").is_dir() and any(
            (item / "references").iterdir()
        )
        has_templates = (item / "templates").is_dir() and any(
            (item / "templates").iterdir()
        )

        components = []
        if has_refs:
            components.append("`references`")
        if has_evals:
            components.append("`evals`")
        if has_scripts:
            components.append("`scripts`")
        if has_templates:
            components.append("`templates`")

        ref_files = []
        if (item / "references").is_dir():
            for ref in sorted((item / "references").glob("*.md")):
                ref_files.append(ref.name)

        script_files = []
        if (item / "scripts").is_dir():
            for script in sorted((item / "scripts").iterdir()):
                if (
                    script.is_file()
                    and not script.name.startswith(".")
                    and not script.name.endswith("_test.py")
                    and not script.name.startswith("test_")
                ):
                    script_files.append(script.name)

        skills.append(
            {
                "dir_name": item.name,
                "name": name,
                "description": description,
                "summary": (
                    re.split(r"(?<=[.!?])\s+", description)[0].strip()
                    if description
                    else ""
                ),
                "components": components,
                "ref_files": ref_files,
                "script_files": script_files,
                "has_evals": has_evals,
            }
        )

    return skills


def generate_table(skills: Sequence[Mapping[str, Any]]) -> str:
    """Generates an aligned, pretty-printed Markdown catalog table.

    Args:
        skills: Sequence of skill mappings.

    Returns:
        Aligned Markdown table string.
    """
    headers = ["Skill", "Summary", "Components"]
    rows = []
    for s in skills:
        link = f"[`{s['name']}`]({s['dir_name']}/SKILL.md)"
        comp_str = ", ".join(s["components"]) if s["components"] else "None"
        summary = s["summary"]
        rows.append([link, summary, comp_str])

    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(cell))

    header_line = (
        "| " + " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers)) + " |"
    )
    sep_parts = [":" + "-" * max(3, col_widths[i] - 1) for i in range(len(headers))]
    sep_line = "| " + " | ".join(sep_parts) + " |"

    lines = [header_line, sep_line]
    for row in rows:
        row_line = (
            "| "
            + " | ".join(row[i].ljust(col_widths[i]) for i in range(len(headers)))
            + " |"
        )
        lines.append(row_line)

    return "\n".join(lines)


def generate_details(skills: Sequence[Mapping[str, Any]]) -> str:
    """Generates the detailed breakdown sections for each skill.

    Args:
        skills: Sequence of skill mappings.

    Returns:
        Markdown string containing individual skill breakdown sections.
    """
    sections = []
    for s in skills:
        lines = []
        lines.append(f"### [`{s['name']}`]({s['dir_name']}/SKILL.md)")
        lines.append("")

        if s["description"]:
            wrapped_desc = wrap_text(s["description"], width=80, prefix="> ")
            lines.append(wrapped_desc)
            lines.append("")

        lines.append(f"- **Directory**: [`{s['dir_name']}/`]({s['dir_name']}/)")

        if s["has_evals"]:
            lines.append(
                f"- **Evaluations**: [`evals.json`]({s['dir_name']}/evals/evals.json)"
            )

        if s["ref_files"]:
            if len(s["ref_files"]) == 1:
                ref = s["ref_files"][0]
                lines.append(
                    f"- **References**: [`{ref}`]({s['dir_name']}/references/{ref})"
                )
            else:
                lines.append("- **References**:")
                for ref in s["ref_files"]:
                    lines.append(f"  - [`{ref}`]({s['dir_name']}/references/{ref})")

        if s["script_files"]:
            if len(s["script_files"]) == 1:
                sc = s["script_files"][0]
                lines.append(f"- **Scripts**: [`{sc}`]({s['dir_name']}/scripts/{sc})")
            else:
                lines.append("- **Scripts**:")
                for sc in s["script_files"]:
                    lines.append(f"  - [`{sc}`]({s['dir_name']}/scripts/{sc})")

        sections.append("\n".join(lines))

    return "\n\n".join(sections)


def get_default_template() -> str:
    """Provides fallback template if custom template does not exist.

    Returns:
        Canonical Markdown template string with replacement comment placeholders.
    """
    return textwrap.dedent("""\
        # Agent Skills

        A standardized suite of cross-platform skills for AI coding agents, fully
        compatible with both **Google Antigravity** and **Anthropic Claude Code**.

        ---

        ## Catalog (<!-- SKILLS_COUNT --> Skills)

        <!-- SKILLS_TABLE -->

        ---

        ## Skill Breakdown

        <!-- SKILLS_DETAILS -->

        ---

        ## Architectural Principles

        Every skill in this repository follows the strict architectural guidelines
        codified in [`authoring-skills`](authoring-skills/SKILL.md) and
        [`writing-markdown`](writing-markdown/SKILL.md):

        - **Cross-Platform Compatibility**: Fully functional in both Google
          Antigravity (`agy`) and Anthropic Claude Code (`claude`).
        - **Primary Dispatcher Pattern**: Top-level `SKILL.md` is lean (<100 lines) and
          acts as a dispatcher to focused guides in `references/`.
        - **Automated Evaluations**: Every skill contains benchmark scenarios defined
          in `evals/evals.json` run via deterministic test harnesses.
        - **Strict Formatting**: 80-character maximum line length (`MD013`), blank line
          fencing (`MD031`, `MD032`), and basic ASCII hygiene.

        ---

        ## Updating This Catalog

        To regenerate `README.md` after adding, updating, or removing skills:

        ```bash
        python3 .github/scripts/generate_readme.py
        ```

        To verify whether `README.md` is in sync (useful in CI or pre-commit hooks):

        ```bash
        python3 .github/scripts/generate_readme.py --check
        ```
    """)


def main(argv: Sequence[str] | None = None) -> None:
    """CLI entry point for README.md catalog generator.

    Args:
        argv: Optional command-line argument sequence; defaults to sys.argv[1:].
    """
    parser = argparse.ArgumentParser(
        description="Generate README.md catalog from skill frontmatter."
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parent.parent.parent,
        help="Path to repository root.",
    )
    parser.add_argument(
        "--template",
        type=Path,
        default=None,
        help="Optional custom template path.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output README path (defaults to <repo-root>/README.md).",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check if README.md is up to date and formatted. Exits 1 if not.",
    )
    parser.add_argument(
        "--lint",
        action="store_true",
        help="Run markdownlint on the generated README.",
    )
    parser.add_argument(
        "--no-format",
        action="store_true",
        help="Skip auto-formatting with prettier and markdownlint.",
    )
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    output_path = (args.output or (repo_root / "README.md")).resolve()

    template_path = args.template or (repo_root / ".github" / "README.template.md")
    if template_path.is_file():
        template_content = template_path.read_text(encoding="utf-8")
    else:
        template_content = get_default_template()

    skills = collect_skills(repo_root)
    table_md = generate_table(skills)
    details_md = generate_details(skills)

    readme_content = template_content
    readme_content = readme_content.replace("<!-- SKILLS_COUNT -->", str(len(skills)))
    readme_content = readme_content.replace("<!-- SKILLS_TABLE -->", table_md)
    readme_content = readme_content.replace("<!-- SKILLS_DETAILS -->", details_md)

    readme_content = sanitize_ascii(readme_content)

    if not readme_content.endswith("\n"):
        readme_content += "\n"

    if args.check:
        if not output_path.is_file():
            print(
                f"Error: Output file {output_path} does not exist.",
                file=sys.stderr,
            )
            sys.exit(1)
        current_content = output_path.read_text(encoding="utf-8")

        expected_content = readme_content
        if not args.no_format:
            with tempfile.NamedTemporaryFile("w+", suffix=".md", delete=False) as tf:
                tf.write(readme_content)
                tf_path = Path(tf.name)
            try:
                format_markdown(tf_path)
                expected_content = tf_path.read_text(encoding="utf-8")
            finally:
                if tf_path.is_file():
                    tf_path.unlink()

        if current_content != expected_content:
            print(
                f"Error: {output_path} is out of date or needs formatting. "
                "Run 'python3 .github/scripts/generate_readme.py' to update.",
                file=sys.stderr,
            )
            sys.exit(1)
        print(f"OK: {output_path} is up to date and correctly formatted.")
        sys.exit(0)

    output_path.write_text(readme_content, encoding="utf-8")
    if not args.no_format:
        format_markdown(output_path)
        print(f"Auto-formatted {output_path} with prettier & markdownlint.")

    print(f"Successfully generated catalog for {len(skills)} skills at {output_path}")

    if args.lint:
        mdlint_args = ["markdownlint"]
        custom_config = repo_root / "writing-markdown" / ".markdownlint.json"
        if custom_config.is_file():
            mdlint_args.extend(["--config", str(custom_config)])
        mdlint = subprocess.run(
            mdlint_args + [str(output_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if mdlint.returncode != 0:
            print("markdownlint issues found:", file=sys.stderr)
            print(mdlint.stderr or mdlint.stdout, file=sys.stderr)
            sys.exit(mdlint.returncode)
        print("markdownlint check passed.")


if __name__ == "__main__":
    main()
