#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Unit tests for the skill auditor script (audit_skill.py)."""

import io
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

from audit_skill import (
    AuditResult,
    audit_frontmatter,
    audit_markdown_content,
    audit_skill,
    main,
    parse_frontmatter,
)


class AuditSkillTest(unittest.TestCase):
    """Hermetic unit tests for audit_skill functions and CLI orchestrator."""

    def test_parse_frontmatter_valid(self) -> None:
        """Should parse folded scalar frontmatter correctly."""
        content = textwrap.dedent("""\
            ---
            name: testing-skill
            description: >-
                Validates test cases. Use when running tests.
                Don't use for generic compilation.
            ---
            # Testing Skill
        """)
        meta, raw_text, errors = parse_frontmatter(content)
        self.assertEqual(len(errors), 0)
        self.assertEqual(meta.get("name"), "testing-skill")
        self.assertIn("Validates test cases.", meta.get("description", ""))

    def test_parse_frontmatter_unclosed(self) -> None:
        """Should return error when frontmatter delimiter is not closed."""
        content = "---\nname: broken-skill\ndescription: missing end dashes\n"
        meta, raw_text, errors = parse_frontmatter(content)
        self.assertTrue(any("unclosed" in e for e in errors))
        self.assertEqual(meta, {})

    def test_parse_frontmatter_missing_delimiter(self) -> None:
        """Should return error when file does not start with frontmatter."""
        content = "# Just Markdown\nNo frontmatter here.\n"
        meta, raw_text, errors = parse_frontmatter(content)
        self.assertTrue(any("delimiter" in e for e in errors))

    def test_audit_frontmatter_name_validation(self) -> None:
        """Should flag invalid skill names (uppercase, spaces, length)."""
        result = AuditResult()
        audit_frontmatter(
            "",
            {
                "name": "Invalid_Name_Skill",
                "description": "Use when X. Don't use for Y.",
            },
            result,
        )
        self.assertTrue(any("lowercase alphanumeric" in e for e in result.errors))

    def test_audit_frontmatter_missing_triggers(self) -> None:
        """Should warn when positive or negative triggers are omitted."""
        result = AuditResult()
        meta = {
            "name": "testing-skill",
            "description": "A very plain description without any guidance.",
        }
        audit_frontmatter("", meta, result)
        self.assertTrue(any("positive triggers" in w for w in result.warnings))
        self.assertTrue(any("negative guardrails" in w for w in result.warnings))

    def test_audit_markdown_broken_code_block(self) -> None:
        """Should detect code blocks opened with fewer than 3 backticks."""
        result = AuditResult()
        content = textwrap.dedent("""\
            # Broken Block
            `python
            print('hello')
            ```
        """)
        audit_markdown_content(content, Path("/tmp"), result)
        self.assertTrue(any("Malformed code block" in e for e in result.errors))

    def test_audit_markdown_missing_h1(self) -> None:
        """Should require a top-level H1 header in markdown body."""
        result = AuditResult()
        content = "## Only H2\nSome content without H1.\n"
        audit_markdown_content(content, Path("/tmp"), result)
        self.assertTrue(any("top-level '# [Skill Name]'" in e for e in result.errors))

    def test_audit_markdown_broken_relative_links(self) -> None:
        """Should flag relative markdown links that point to nonexistent files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            skill_dir = Path(temp_dir)
            result = AuditResult()
            content = textwrap.dedent("""\
                # Link Test
                See [missing file](./references/NONEXISTENT.md) for details.
            """)
            audit_markdown_content(content, skill_dir, result)
            self.assertTrue(any("Broken relative link" in e for e in result.errors))

    def test_audit_skill_clean_pass(self) -> None:
        """Should pass completely for a fully compliant skill directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            skill_dir = Path(temp_dir)
            ref_dir = skill_dir / "references"
            ref_dir.mkdir()
            (ref_dir / "GUIDE.md").write_text("# Guide\n", encoding="utf-8")

            skill_md = textwrap.dedent("""\
                ---
                name: testing-skill
                description: >-
                    Executes automated checks. Use when running tests.
                    Don't use for generic compilation.
                ---

                # Testing Skill

                Overview text.

                - See [guide](./references/GUIDE.md) for details.
            """)
            (skill_dir / "SKILL.md").write_text(skill_md, encoding="utf-8")

            result = audit_skill(skill_dir)
            self.assertTrue(result.passed)
            self.assertEqual(len(result.errors), 0)

    @mock.patch("sys.stderr", new_callable=io.StringIO)
    def test_main_cli_nonexistent_directory(self, mock_stderr: io.StringIO) -> None:
        """Should return code 1 when invoked with non-existent directory."""
        code = main(["/path/to/nonexistent/skill/dir"])
        self.assertEqual(code, 1)
        self.assertIn("does not exist", mock_stderr.getvalue())

    @mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_main_cli_successful_audit(self, mock_stdout: io.StringIO) -> None:
        """Should return code 0 and output success message for clean skill."""
        with tempfile.TemporaryDirectory() as temp_dir:
            skill_dir = Path(temp_dir)
            skill_md = textwrap.dedent("""\
                ---
                name: verifying-skill
                description: >-
                    Verifies configurations. Use when validating setup.
                    Don't use for code generation.
                ---

                # Verifying Skill

                Verification instructions.
            """)
            (skill_dir / "SKILL.md").write_text(skill_md, encoding="utf-8")

            code = main([str(skill_dir)])
            self.assertEqual(code, 0)
            self.assertIn("Audit", mock_stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
