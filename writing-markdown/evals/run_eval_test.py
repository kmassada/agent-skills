#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Unit tests for writing-markdown/evals/run_eval.py."""

import json
import sys
import unittest
from pathlib import Path

# Ensure script can import run_eval directly
sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_eval import (
    DEFAULT_DATASET,
    check_markdown_expectation,
    evaluate_static_benchmark,
)


class RunEvalTest(unittest.TestCase):
    """Test suite covering markdown expectation verification and benchmark evaluation."""

    def test_md032_blank_around_lists(self):
        """Should detect proper blank line between preceding colon and list."""
        valid = "Header:\n\n* Item 1\n* Item 2\n"
        invalid = "Header:\n* Item 1\n* Item 2\n"

        passed, _ = check_markdown_expectation(
            valid, "A blank line is inserted between colon and list"
        )
        self.assertTrue(passed)

        failed, _ = check_markdown_expectation(
            invalid, "A blank line is inserted between colon and list"
        )
        self.assertFalse(failed)

    def test_md040_language_tag(self):
        """Should detect language tag on code fences."""
        valid = "```python\nprint('hi')\n```\n"
        invalid = "```\nprint('hi')\n```\n"

        passed, _ = check_markdown_expectation(valid, "language identifier declared")
        self.assertTrue(passed)

        failed, _ = check_markdown_expectation(invalid, "language identifier declared")
        self.assertFalse(failed)

    def test_nested_code_block_indentation(self):
        """Should detect 4-space indentation on code blocks inside lists."""
        valid = "1. Item:\n\n    ```bash\n    ls -la\n    ```\n"
        invalid = "1. Item:\n\n```bash\nls -la\n```\n"

        passed, _ = check_markdown_expectation(valid, "4 spaces indentation")
        self.assertTrue(passed)

        failed, _ = check_markdown_expectation(invalid, "4 spaces indentation")
        self.assertFalse(failed)

    def test_md013_line_length(self):
        """Should verify lines do not exceed 80 characters."""
        short_line = "A" * 79 + "\n"
        long_line = "A" * 85 + "\n"

        passed, _ = check_markdown_expectation(short_line, "80 characters limit")
        self.assertTrue(passed)

        failed, _ = check_markdown_expectation(long_line, "80 characters limit")
        self.assertFalse(failed)

    def test_ascii_hygiene_en_dash_and_em_dash(self):
        """Should verify en-dashes and em-dashes are cleanly replaced."""
        clean = "Word -- another - word.\n"
        dirty = "Word — another – word.\n"

        passed, _ = check_markdown_expectation(clean, "em-dash replaced")
        self.assertTrue(passed)

        failed, _ = check_markdown_expectation(dirty, "em-dash replaced")
        self.assertFalse(failed)

    def test_chevron_replacement(self):
        """Should verify heavy chevron ❯ is replaced with >."""
        clean = "Prompt: > command\n"
        dirty = "Prompt: ❯ command\n"

        passed, _ = check_markdown_expectation(clean, "u+276f replaced")
        self.assertTrue(passed)

        failed, _ = check_markdown_expectation(dirty, "u+276f replaced")
        self.assertFalse(failed)

    def test_gfm_alert_callout(self):
        """Should verify GitHub Flavored Markdown alert callouts."""
        valid = "> [!NOTE]\n> Info message\n"
        invalid = "> NOTE: Info message\n"

        passed, _ = check_markdown_expectation(valid, "callout alert syntax")
        self.assertTrue(passed)

        failed, _ = check_markdown_expectation(invalid, "callout alert syntax")
        self.assertFalse(failed)

    def test_all_dataset_benchmarks_pass_statically(self):
        """All 10 benchmark cases in evals.json should pass static evaluation."""
        self.assertTrue(DEFAULT_DATASET.is_file())
        dataset = json.loads(DEFAULT_DATASET.read_text(encoding="utf-8"))
        eval_cases = dataset.get("evals", [])
        self.assertEqual(len(eval_cases), 10)

        for case in eval_cases:
            passed, failures = evaluate_static_benchmark(case, verbose=False)
            self.assertTrue(passed, f"Case {case['id']} failed: {failures}")


if __name__ == "__main__":
    unittest.main()
