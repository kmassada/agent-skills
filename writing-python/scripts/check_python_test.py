#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Unit tests for check_python.py script."""

import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

# Ensure sibling scripts can be imported directly
sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_python import (
    check_pyright,
    check_ruff,
    get_uv_tool_cmd,
    main,
    run_command,
    run_tests,
)


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

    def test_run_command_nonexistent_binary(self):
        """Should return failure when binary does not exist on filesystem."""
        ok, out = run_command(["nonexistent_binary_xyz_123"], "missing")
        self.assertFalse(ok)
        self.assertIn("Failed to execute", out)

    def test_get_uv_tool_cmd_when_available(self):
        """Should build valid uv command when uv/uvx is installed."""
        cmd = get_uv_tool_cmd("ruff")
        self.assertIsNotNone(cmd)
        if cmd:
            self.assertIn("ruff", cmd)

    def test_get_uv_tool_cmd_when_missing(self):
        """Should return None when both uvx and uv are missing from PATH."""
        with mock.patch("shutil.which", return_value=None):
            cmd = get_uv_tool_cmd("ruff")
            self.assertIsNone(cmd)

    def test_check_ruff_missing_uv(self):
        """Should report failure when uv/uvx is missing for check_ruff."""
        with mock.patch("shutil.which", return_value=None):
            ok, msg = check_ruff(Path("."))
            self.assertFalse(ok)
            self.assertIn("not found in PATH", msg)

    def test_check_pyright_missing_uv(self):
        """Should report failure when uv/uvx is missing for check_pyright."""
        with mock.patch("shutil.which", return_value=None):
            ok, msg = check_pyright(Path("."))
            self.assertFalse(ok)
            self.assertIn("not found in PATH", msg)

    @mock.patch("check_python.check_pyright", return_value=(True, "Pyright clean"))
    @mock.patch("check_python.check_ruff", return_value=(True, "Ruff clean"))
    @mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_main_all_passed(
        self,
        mock_stdout: io.StringIO,
        mock_ruff: mock.MagicMock,
        mock_pyright: mock.MagicMock,
    ):
        """Should report success and exit 0 when all checks pass."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "sample_test.py"
            test_file.write_text(
                "import unittest\n"
                "class STest(unittest.TestCase):\n"
                "    def test_pass(self):\n"
                "        self.assertTrue(True)\n"
                "if __name__ == '__main__':\n"
                "    unittest.main()\n",
                encoding="utf-8",
            )
            with self.assertRaises(SystemExit) as cm:
                main([str(temp_dir)])
            self.assertEqual(cm.exception.code, 0)
            self.assertIn("All Python quality gates passed", mock_stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
