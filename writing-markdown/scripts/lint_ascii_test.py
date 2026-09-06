#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Unit tests for lint_ascii.py linter and fixer."""

import sys
import tempfile
import unittest
from pathlib import Path

# Ensure sibling scripts can be imported directly
sys.path.insert(0, str(Path(__file__).resolve().parent))

from lint_ascii import process_file


class LintAsciiTest(unittest.TestCase):
    """Test suite covering ASCII linting, character replacements, and box drawing."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_clean_file_passes(self):
        """Pure basic ASCII markdown file should produce zero issues."""
        test_file = self.dir_path / "clean.md"
        test_file.write_text("# Title\n\nThis is clean ASCII text.\n", encoding="utf-8")

        count, issues = process_file(test_file, fix=False)
        self.assertEqual(count, 0)
        self.assertEqual(issues, [])

    def test_detects_en_dash_and_em_dash(self):
        """Should detect en-dash and em-dash characters."""
        test_file = self.dir_path / "dashes.md"
        test_file.write_text("Wait 1–2s. Word—another word.\n", encoding="utf-8")

        count, issues = process_file(test_file, fix=False)
        self.assertEqual(count, 2)
        self.assertTrue(any("U+2013" in i for i in issues))
        self.assertTrue(any("U+2014" in i for i in issues))

    def test_detects_smart_quotes(self):
        """Should detect smart quotes (single and double)."""
        test_file = self.dir_path / "quotes.md"
        test_file.write_text("“Double quotes” and ‘single quotes’.\n", encoding="utf-8")

        count, _ = process_file(test_file, fix=False)
        self.assertEqual(count, 4)

    def test_detects_heavy_angle_bracket(self):
        """Should detect heavy angle bracket (❯ / U+276F)."""
        test_file = self.dir_path / "glyph.md"
        test_file.write_text("Prompt: ❯ run command\n", encoding="utf-8")

        count, issues = process_file(test_file, fix=False)
        self.assertEqual(count, 1)
        self.assertTrue(any("U+276F" in i for i in issues))

    def test_fix_mode_replaces_characters_on_disk(self):
        """Fix mode should replace ambiguous characters and save to disk."""
        test_file = self.dir_path / "fixable.md"
        original = "“Hello world” — wait 1–2s ❯ run\n"
        test_file.write_text(original, encoding="utf-8")

        count, _ = process_file(test_file, fix=True)
        self.assertEqual(count, 5)

        fixed_content = test_file.read_text(encoding="utf-8")
        expected = '"Hello world" -- wait 1-2s > run\n'
        self.assertEqual(fixed_content, expected)

    def test_box_drawing_characters_allowed_by_default(self):
        """Standard tree diagram box-drawing characters should be allowed by default."""
        test_file = self.dir_path / "tree.md"
        test_file.write_text("├── dir\n└── file.txt\n", encoding="utf-8")

        count, issues = process_file(test_file, fix=False, check_all=False)
        self.assertEqual(count, 0)
        self.assertEqual(issues, [])

    def test_box_drawing_characters_flagged_with_check_all(self):
        """When check_all is True, box-drawing characters should be flagged."""
        test_file = self.dir_path / "tree_strict.md"
        test_file.write_text("├── dir\n└── file.txt\n", encoding="utf-8")

        count, issues = process_file(test_file, fix=False, check_all=True)
        self.assertGreater(count, 0)
        self.assertTrue(
            any("U+251C" in i or "U+2500" in i or "U+2514" in i for i in issues)
        )

    def test_rule_explanation_line_exemption(self):
        """Lines explaining rule definitions should be exempt."""
        test_file = self.dir_path / "rule_doc.md"
        test_file.write_text(
            "Rule: Replace U+276F ❯ with > in shell prompts.\n",
            encoding="utf-8",
        )

        count, _ = process_file(test_file, fix=True)
        self.assertEqual(count, 0)
        self.assertIn("❯", test_file.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
