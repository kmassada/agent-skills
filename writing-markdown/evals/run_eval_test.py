#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Unit tests for writing-markdown/evals/run_eval.py."""

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

# Ensure script can import run_eval directly
sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_eval import (
    DEFAULT_DATASET,
    check_markdown_expectation,
    evaluate_static_benchmark,
    main,
    run_agent_eval,
)


class RunEvalTest(unittest.TestCase):
    """Test suite for markdown expectation checks and benchmark evaluation."""

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

    def test_evaluate_static_benchmark_failure(self):
        """Should report failure when test case expectations are not satisfied."""
        failing_case = {
            "id": 999,
            "expected_output": "Non compliant text\n* item 1",
            "expectations": ["A blank line is inserted between colon and list"],
        }
        passed, failures = evaluate_static_benchmark(failing_case)
        self.assertFalse(passed)
        self.assertEqual(len(failures), 1)

    def test_run_agent_eval_unknown_backend(self):
        """Should return failure when invalid backend name is supplied."""
        case = {"id": 1, "prompt": "test"}
        passed, failures = run_agent_eval(case, backend="unknown")
        self.assertFalse(passed)
        self.assertIn("Unknown backend: unknown", failures[0])

    def test_run_agent_eval_missing_binary(self):
        """Should fail cleanly when agent CLI binary is absent."""
        case = {"id": 1, "prompt": "test"}
        with mock.patch("shutil.which", return_value=None):
            passed, failures = run_agent_eval(case, backend="agy")
            self.assertFalse(passed)
            self.assertIn("not found in PATH", failures[0])

    @mock.patch("sys.stderr", new_callable=io.StringIO)
    def test_main_missing_dataset_exits_one(self, mock_stderr: io.StringIO):
        """Should exit with 1 when dataset file does not exist."""
        with self.assertRaises(SystemExit) as cm:
            main(["--dataset", "/nonexistent/path/evals.json"])
        self.assertEqual(cm.exception.code, 1)
        self.assertIn("Dataset not found", mock_stderr.getvalue())

    @mock.patch("sys.stderr", new_callable=io.StringIO)
    def test_main_corrupted_json_dataset_exits_one(self, mock_stderr: io.StringIO):
        """Should exit with 1 when dataset contains invalid JSON."""
        with tempfile.TemporaryDirectory() as temp_dir:
            bad_json = Path(temp_dir) / "corrupted.json"
            bad_json.write_text("{invalid_json: true", encoding="utf-8")
            with self.assertRaises(SystemExit) as cm:
                main(["--dataset", str(bad_json)])
            self.assertEqual(cm.exception.code, 1)
            self.assertIn("Error reading JSON dataset", mock_stderr.getvalue())

    @mock.patch("sys.stderr", new_callable=io.StringIO)
    def test_main_nonexistent_eval_id_exits_one(self, mock_stderr: io.StringIO):
        """Should exit with 1 when requested eval ID is not in dataset."""
        with self.assertRaises(SystemExit) as cm:
            main(["--eval-id", "9999", "--backend", "static"])
        self.assertEqual(cm.exception.code, 1)
        self.assertIn("No test case found with id 9999", mock_stderr.getvalue())

    @mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_main_static_execution_single_test(self, mock_stdout: io.StringIO):
        """CLI execution of single static test should pass cleanly."""
        with self.assertRaises(SystemExit) as cm:
            main(["--eval-id", "1", "--backend", "static"])
        self.assertEqual(cm.exception.code, 0)
        self.assertIn("Test 01", mock_stdout.getvalue())
        self.assertIn("1/1 passed", mock_stdout.getvalue())

    def test_run_agent_eval_subprocess_error(self):
        """Should report failure when backend subprocess execution fails."""
        case = {"id": 1, "prompt": "test"}
        with mock.patch("shutil.which", return_value="/bin/dummy"):
            with mock.patch("subprocess.run", side_effect=OSError("Exec failed")):
                passed, failures = run_agent_eval(case, backend="agy")
                self.assertFalse(passed)
                self.assertIn("Backend execution error", failures[0])


if __name__ == "__main__":
    unittest.main()
