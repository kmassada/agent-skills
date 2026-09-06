#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Unit tests for the authoring-skills evaluation runner (run_eval.py)."""

import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from run_eval import (
    check_authoring_expectation,
    evaluate_static_benchmark,
    main,
    run_agent_eval,
)


class RunEvalTest(unittest.TestCase):
    """Hermetic tests for authoring-skills eval harness."""

    def test_check_authoring_expectation_gerund(self) -> None:
        """Should detect gerund naming patterns."""
        content = "name: debugging-service\n"
        passed, _ = check_authoring_expectation(content, "Skill uses gerund naming")
        self.assertTrue(passed)

    def test_check_authoring_expectation_positive_trigger(self) -> None:
        """Should verify positive triggers in description."""
        content = "description: >-\n  Use when inspecting cluster pods.\n"
        passed, _ = check_authoring_expectation(
            content, "Contains positive trigger 'Use when'"
        )
        self.assertTrue(passed)

    def test_check_authoring_expectation_negative_guardrail(self) -> None:
        """Should verify negative guardrails in description."""
        content = "Don't use for generic application compilation."
        passed, _ = check_authoring_expectation(
            content, "Contains negative guardrail 'Don't use'"
        )
        self.assertTrue(passed)

    def test_check_authoring_expectation_focus_hijacking(self) -> None:
        """Should verify focus hijacking mitigations."""
        content = (
            "Use tmux capture-pane -p to silently read output without switching panes."
        )
        passed, _ = check_authoring_expectation(
            content, "Identifies focus hijacking and silent capture"
        )
        self.assertTrue(passed)

    def test_evaluate_static_benchmark_all_cases(self) -> None:
        """Should verify that all benchmark test cases pass deterministically."""
        evals_path = Path(__file__).parent / "evals.json"
        data = json.loads(evals_path.read_text(encoding="utf-8"))
        cases = data["evals"]

        for case in cases:
            passed, failures = evaluate_static_benchmark(case)
            self.assertTrue(
                passed,
                f"Eval case #{case['id']} failed static checks: {failures}",
            )

    @mock.patch("subprocess.run")
    def test_run_agent_eval_agy_mocked(self, mock_run: mock.MagicMock) -> None:
        """Should correctly format agy CLI invocation and parse output."""
        mock_proc = mock.create_autospec(
            subprocess.CompletedProcess(args=[], returncode=0),
            instance=True,
            spec_set=True,
        )
        mock_proc.returncode = 0
        mock_proc.stdout = (
            "name: inspecting-logs\ndescription: >-\n  Use when X. Don't use for Y."
        )
        mock_proc.stderr = ""
        mock_run.return_value = mock_proc

        case = {
            "id": 1,
            "prompt": "Create skill inspecting-logs",
            "expectations": [
                "Uses gerund naming",
                "Contains positive trigger 'Use when'",
            ],
        }
        passed, failures = run_agent_eval(case, backend="agy")
        self.assertTrue(passed, f"Expected pass, got: {failures}")
        mock_run.assert_called_once()
        args, _ = mock_run.call_args
        self.assertEqual(args[0][:2], ["agy", "--prompt"])

    @mock.patch("subprocess.run")
    def test_run_agent_eval_failure_handling(self, mock_run: mock.MagicMock) -> None:
        """Should handle execution failure gracefully."""
        mock_proc = mock.create_autospec(
            subprocess.CompletedProcess(args=[], returncode=0),
            instance=True,
            spec_set=True,
        )
        mock_proc.returncode = 1
        mock_proc.stdout = ""
        mock_proc.stderr = "Internal agent error occurred"
        mock_run.return_value = mock_proc

        case = {
            "id": 1,
            "prompt": "Create skill",
            "expectations": ["Uses gerund naming 'inspecting-logs'"],
        }
        passed, failures = run_agent_eval(case, backend="claude")
        self.assertFalse(passed)
        self.assertTrue(len(failures) > 0)

    def test_run_agent_eval_unsupported_backend(self) -> None:
        """Should return failure when unsupported backend is supplied."""
        case = {"id": 1, "prompt": "test"}
        passed, failures = run_agent_eval(case, backend="unsupported")
        self.assertFalse(passed)
        self.assertIn("Unsupported backend", failures[0])

    @mock.patch("sys.stderr", new_callable=io.StringIO)
    def test_main_cli_missing_file(self, mock_stderr: io.StringIO) -> None:
        """Should return code 1 when evals file does not exist."""
        code = main(["--evals-file", "/path/to/nonexistent/evals.json"])
        self.assertEqual(code, 1)
        self.assertIn("not found", mock_stderr.getvalue())

    @mock.patch("sys.stderr", new_callable=io.StringIO)
    def test_main_cli_corrupted_evals_file(self, mock_stderr: io.StringIO) -> None:
        """Should return code 1 when evals file contains invalid JSON."""
        with tempfile.TemporaryDirectory() as temp_dir:
            corrupt = Path(temp_dir) / "evals.json"
            corrupt.write_text("{corrupt: json", encoding="utf-8")
            code = main(["--evals-file", str(corrupt)])
            self.assertEqual(code, 1)
            self.assertIn("Error parsing evals file", mock_stderr.getvalue())

    @mock.patch("sys.stderr", new_callable=io.StringIO)
    def test_main_cli_nonexistent_eval_id(self, mock_stderr: io.StringIO) -> None:
        """Should return code 1 when requested eval ID is not found."""
        code = main(["--eval-id", "9999", "--static"])
        self.assertEqual(code, 1)
        self.assertIn("No test case found with id 9999", mock_stderr.getvalue())

    @mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_main_cli_static_run(self, mock_stdout: io.StringIO) -> None:
        """Should execute all static benchmark cases and return code 0."""
        code = main(["--static"])
        self.assertEqual(code, 0)
        self.assertIn("100.0%", mock_stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
