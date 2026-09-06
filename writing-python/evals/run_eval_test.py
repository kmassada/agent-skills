#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Unit tests for writing-python/evals/run_eval.py."""

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
    check_python_expectation,
    evaluate_static_benchmark,
    main,
    run_agent_eval,
)


class RunEvalTest(unittest.TestCase):
    """Test suite for Python quality expectations and benchmark evaluation."""

    def test_collections_abc_check(self):
        """Should detect collections.abc abstractions."""
        valid = "from collections.abc import Sequence\ndef f(x: Sequence[str]): pass"
        invalid = "def f(x: list[str]): pass"

        passed, _ = check_python_expectation(valid, "uses collections.abc")
        self.assertTrue(passed)

        failed, _ = check_python_expectation(invalid, "from collections.abc import")
        self.assertFalse(failed)

    def test_legacy_typing_ban(self):
        """Should fail when deprecated typing.List/Dict are used."""
        dirty = "from typing import List, Dict\nx: List[str] = []"
        clean = "from collections.abc import Sequence\nx: list[str] = []"

        passed, _ = check_python_expectation(clean, "no legacy typing")
        self.assertTrue(passed)

        failed, _ = check_python_expectation(dirty, "no legacy typing")
        self.assertFalse(failed)

    def test_subprocess_check_parameter(self):
        """Should detect explicit check parameter in subprocess.run."""
        valid = "subprocess.run(['git'], check=False)"
        invalid = "subprocess.run(['git'])"

        passed, _ = check_python_expectation(valid, "check=False parameter")
        self.assertTrue(passed)

        failed, _ = check_python_expectation(invalid, "check=False parameter")
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
            "expected_output": "def f(x: list[str]): pass",
            "expectations": ["Uses collections.abc abstractions"],
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
            bad_file = Path(temp_dir) / "corrupt.json"
            bad_file.write_text("{bad: json", encoding="utf-8")
            with self.assertRaises(SystemExit) as cm:
                main(["--dataset", str(bad_file)])
            self.assertEqual(cm.exception.code, 1)
            self.assertIn("Error reading JSON dataset", mock_stderr.getvalue())

    @mock.patch("sys.stderr", new_callable=io.StringIO)
    def test_main_nonexistent_eval_id_exits_one(self, mock_stderr: io.StringIO):
        """Should exit with 1 when requested eval ID is not found."""
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
        """Should handle subprocess timeout or failure gracefully."""
        case = {"id": 1, "prompt": "test"}
        with mock.patch("shutil.which", return_value="/bin/dummy"):
            with mock.patch("subprocess.run", side_effect=OSError("Process failed")):
                passed, failures = run_agent_eval(case, backend="agy")
                self.assertFalse(passed)
                self.assertIn("Backend execution error", failures[0])

    def test_check_python_expectation_additional_rules(self):
        """Should verify type narrowing, PEP 604, exceptions, and uv init rules."""
        ok_narrow, _ = check_python_expectation(
            "if x is None: return", "type narrowing"
        )
        self.assertTrue(ok_narrow)

        ok_union, _ = check_python_expectation("x: str | None = None", "T | None")
        self.assertTrue(ok_union)

        ok_exc, _ = check_python_expectation(
            "try:\n  pass\nexcept (OSError, UnicodeDecodeError): pass",
            "specific expected exceptions",
        )
        self.assertTrue(ok_exc)

        ok_init, _ = check_python_expectation(
            "uv init --bare --no-readme --vcs none my_pkg", "uv init"
        )
        self.assertTrue(ok_init)


if __name__ == "__main__":
    unittest.main()
