#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Unit tests for check_python.py script."""

import sys
import tempfile
import unittest
from pathlib import Path

# Ensure sibling scripts can be imported directly
sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_python import run_command, run_tests


class CheckPythonTest(unittest.TestCase):
    """Test suite for check_python helper functions."""

    def test_run_command_success(self):
        """Should return success and output for a valid command."""
        ok, out = run_command([sys.executable, "-c", "print('hello')"], "echo test")
        self.assertTrue(ok)
        self.assertEqual(out, "hello")

    def test_run_command_failure(self):
        """Should return failure when exit code is non-zero."""
        ok, _ = run_command(
            [sys.executable, "-c", "import sys; sys.exit(1)"], "fail test"
        )
        self.assertFalse(ok)

    def test_run_tests_with_passing_suite(self):
        """Should pass when companion test file succeeds."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "dummy_test.py"
            test_file.write_text(
                "import unittest\n"
                "class DummyTest(unittest.TestCase):\n"
                "    def test_ok(self):\n"
                "        self.assertTrue(True)\n"
                "if __name__ == '__main__':\n"
                "    unittest.main()\n",
                encoding="utf-8",
            )
            ok, failures = run_tests([test_file])
            self.assertTrue(ok)
            self.assertEqual(len(failures), 0)

    def test_run_tests_with_failing_suite(self):
        """Should detect failures when test suite exits non-zero."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "failing_test.py"
            test_file.write_text(
                "import unittest\n"
                "class FailingTest(unittest.TestCase):\n"
                "    def test_fail(self):\n"
                "        self.fail('intentional failure')\n"
                "if __name__ == '__main__':\n"
                "    unittest.main()\n",
                encoding="utf-8",
            )
            ok, failures = run_tests([test_file])
            self.assertFalse(ok)
            self.assertEqual(len(failures), 1)
            self.assertIn("intentional failure", failures[0])


if __name__ == "__main__":
    unittest.main()
