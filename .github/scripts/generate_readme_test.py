#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Unit tests for generate_readme.py catalog generator."""

import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

# Ensure sibling scripts can be imported directly
sys.path.insert(0, str(Path(__file__).resolve().parent))

from generate_readme import (
    collect_skills,
    generate_details,
    generate_table,
    main,
    parse_frontmatter,
    sanitize_ascii,
    wrap_text,
)


class GenerateReadmeTest(unittest.TestCase):
    """Test suite for frontmatter parsing, text wrapping, and catalog generation."""

    def test_parse_frontmatter_simple(self):
        """Should parse simple key-value frontmatter."""
        content = "---\nname: my-skill\ndescription: A useful skill.\n---\n# My Skill\n"
        meta = parse_frontmatter(content)
        self.assertEqual(meta.get("name"), "my-skill")
        self.assertEqual(meta.get("description"), "A useful skill.")

    def test_parse_frontmatter_quoted(self):
        """Should strip single and double quotes from values."""
        content = "---\nname: \"my-skill\"\ndescription: 'A useful skill.'\n---\n"
        meta = parse_frontmatter(content)
        self.assertEqual(meta.get("name"), "my-skill")
        self.assertEqual(meta.get("description"), "A useful skill.")

    def test_parse_frontmatter_folded_block(self):
        """Should fold multiline block scalars (>-) into a single line."""
        content = (
            "---\n"
            "name: authoring-skills\n"
            "description: >-\n"
            "  First sentence.\n"
            "  Second sentence continuation.\n"
            "  Third sentence.\n"
            "---\n"
        )
        meta = parse_frontmatter(content)
        self.assertEqual(meta.get("name"), "authoring-skills")
        self.assertEqual(
            meta.get("description"),
            "First sentence. Second sentence continuation. Third sentence.",
        )

    def test_parse_frontmatter_missing(self):
        """Should return empty dict if no frontmatter delimiters exist."""
        content = "# Just a normal markdown document\nWith no frontmatter.\n"
        meta = parse_frontmatter(content)
        self.assertEqual(meta, {})

    def test_wrap_text(self):
        """Should wrap text at specified line width with optional prefix."""
        text = "This is a long sentence that should be wrapped across multiple lines cleanly."
        wrapped = wrap_text(text, width=30, prefix="> ")
        lines = wrapped.splitlines()
        self.assertTrue(all(len(line) <= 30 for line in lines))
        self.assertTrue(all(line.startswith("> ") for line in lines))

    def test_sanitize_ascii(self):
        """Should replace non-basic ASCII dashes, quotes, and glyphs."""
        input_text = "Wait 1–2s. “Hello” — ❯ command"
        expected = 'Wait 1-2s. "Hello" -- > command'
        self.assertEqual(sanitize_ascii(input_text), expected)

    def test_collect_skills(self):
        """Should discover skills, extract summary, and detect subcomponents."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)

            # Create mock skill 1 (with references and evals)
            skill1 = repo_root / "skill-one"
            skill1.mkdir()
            (skill1 / "SKILL.md").write_text(
                "---\n"
                "name: skill-one\n"
                "description: >-\n"
                "  Primary summary sentence. Additional trigger phrase details.\n"
                "---\n",
                encoding="utf-8",
            )
            refs_dir = skill1 / "references"
            refs_dir.mkdir()
            (refs_dir / "GUIDE.md").write_text("# Guide\n", encoding="utf-8")

            evals_dir = skill1 / "evals"
            evals_dir.mkdir()
            (evals_dir / "evals.json").write_text("{}", encoding="utf-8")

            # Create mock hidden directory (should be ignored)
            hidden = repo_root / ".github"
            hidden.mkdir()
            (hidden / "SKILL.md").write_text(
                "---\nname: hidden\n---\n", encoding="utf-8"
            )

            skills = collect_skills(repo_root)
            self.assertEqual(len(skills), 1)
            s = skills[0]
            self.assertEqual(s["name"], "skill-one")
            self.assertEqual(s["summary"], "Primary summary sentence.")
            self.assertIn("`references`", s["components"])
            self.assertIn("`evals`", s["components"])
            self.assertTrue(s["has_evals"])
            self.assertEqual(s["ref_files"], ["GUIDE.md"])

    def test_generate_table_alignment(self):
        """Should generate table with aligned pipes across all rows."""
        skills = [
            {
                "dir_name": "skill-a",
                "name": "skill-a",
                "summary": "Short summary.",
                "components": ["`references`"],
            },
            {
                "dir_name": "skill-b",
                "name": "skill-b",
                "summary": "A longer summary sentence that requires more width.",
                "components": ["`evals`", "`scripts`"],
            },
        ]
        table = generate_table(skills)
        lines = table.splitlines()

        # Check headers and separator
        self.assertIn("| Skill", lines[0])
        self.assertIn("| Summary", lines[0])
        self.assertIn("| Components", lines[0])
        self.assertTrue(lines[1].startswith("| :"))

        # Verify all lines have equal column delimiters
        pipe_counts = [line.count("|") for line in lines]
        self.assertTrue(all(c == 4 for c in pipe_counts))

    def test_generate_details_formatting(self):
        """Should generate detailed sections with blockquotes and links."""
        skills = [
            {
                "dir_name": "my-skill",
                "name": "my-skill",
                "description": "Full multi-sentence description.",
                "components": ["`references`", "`evals`"],
                "has_evals": True,
                "ref_files": ["REF1.md", "REF2.md"],
                "script_files": ["tool.py"],
            }
        ]
        details = generate_details(skills)
        self.assertIn("### [`my-skill`](my-skill/SKILL.md)", details)
        self.assertIn("> Full multi-sentence description.", details)
        self.assertIn(
            "- **Evaluations**: [`evals.json`](my-skill/evals/evals.json)",
            details,
        )
        self.assertIn("- **References**:", details)
        self.assertIn("  - [`REF1.md`](my-skill/references/REF1.md)", details)
        self.assertIn("- **Scripts**: [`tool.py`](my-skill/scripts/tool.py)", details)

    def test_parse_frontmatter_unclosed_block(self):
        """Should return empty dict when frontmatter is unclosed."""
        content = "---\nname: unclosed-skill\ndescription: Missing closing dashes\n"
        meta = parse_frontmatter(content)
        self.assertEqual(meta, {})

    @mock.patch("sys.stderr", new_callable=io.StringIO)
    def test_main_cli_check_missing_output(self, mock_stderr: io.StringIO):
        """Should exit 1 when check mode finds missing output file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            missing_out = Path(temp_dir) / "NONEXISTENT_README.md"
            with self.assertRaises(SystemExit) as cm:
                main(["--output", str(missing_out), "--check"])
            self.assertEqual(cm.exception.code, 1)
            self.assertIn("does not exist", mock_stderr.getvalue())

    @mock.patch("sys.stderr", new_callable=io.StringIO)
    @mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_main_cli_generation_and_check(
        self, mock_stdout: io.StringIO, mock_stderr: io.StringIO
    ):
        """Should generate README and verify it stays in sync via --check."""
        with tempfile.TemporaryDirectory() as temp_dir:
            sandbox = Path(temp_dir)
            out_file = sandbox / "README.md"

            # Create mock skill directory
            sk = sandbox / "dummy-skill"
            sk.mkdir()
            (sk / "SKILL.md").write_text(
                "---\nname: dummy-skill\ndescription: Dummy skill summary.\n---\n",
                encoding="utf-8",
            )

            # Generate README without external formatters
            main(
                [
                    "--repo-root",
                    str(sandbox),
                    "--output",
                    str(out_file),
                    "--no-format",
                ]
            )
            self.assertTrue(out_file.is_file())
            content = out_file.read_text(encoding="utf-8")
            self.assertIn("dummy-skill", content)

            # Verify --check passes when content matches
            with self.assertRaises(SystemExit) as cm:
                main(
                    [
                        "--repo-root",
                        str(sandbox),
                        "--output",
                        str(out_file),
                        "--check",
                        "--no-format",
                    ]
                )
            self.assertEqual(cm.exception.code, 0)

            # Modify output file to make it out of date
            out_file.write_text("Stale content\n", encoding="utf-8")
            with self.assertRaises(SystemExit) as cm:
                main(
                    [
                        "--repo-root",
                        str(sandbox),
                        "--output",
                        str(out_file),
                        "--check",
                        "--no-format",
                    ]
                )
            self.assertEqual(cm.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
