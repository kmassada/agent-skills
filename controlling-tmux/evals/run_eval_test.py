#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Unit tests for the controlling-tmux evaluation runner (run_eval.py)."""

import io
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.resolve()))

from run_eval import (  # noqa: E402
    evaluate_commands,
    extract_commands,
    load_dataset,
    main,
    run_dry_test,
    setup_dummy_tmux,
    teardown_dummy_tmux,
)


class RunEvalTest(unittest.TestCase):
    """Hermetic unit tests for controlling-tmux run_eval harness."""

    def test_evaluate_commands_expected_matched(self) -> None:
        """Should return pass when all expected patterns match commands."""
        commands = ["tmux send-keys -t %2 'pytest' C-m", "tmux capture-pane -t %2 -p"]
        expected = ["tmux send-keys -t %2", "capture-pane"]
        forbidden = ["select-pane"]

        passed, failures = evaluate_commands(commands, expected, forbidden)
        self.assertTrue(passed)
        self.assertEqual(len(failures), 0)

    def test_evaluate_commands_missing_expected(self) -> None:
        """Should fail when an expected pattern is absent."""
        commands = ["tmux send-keys -t %2 'pytest' C-m"]
        expected = ["tmux new-window"]
        forbidden = []

        passed, failures = evaluate_commands(commands, expected, forbidden)
        self.assertFalse(passed)
        self.assertTrue(any("Missing expected command pattern" in f for f in failures))

    def test_evaluate_commands_forbidden_matched(self) -> None:
        """Should fail when a forbidden anti-pattern is executed."""
        commands = ["tmux select-pane -t %2", "tmux capture-pane -t %2 -p"]
        expected = ["capture-pane"]
        forbidden = ["select-pane"]

        passed, failures = evaluate_commands(commands, expected, forbidden)
        self.assertFalse(passed)
        self.assertTrue(any("Triggered forbidden anti-pattern" in f for f in failures))

    def test_extract_commands_antigravity_format(self) -> None:
        """Should parse tool_calls in Antigravity JSON output."""
        raw = (
            '{"tool_calls": [{"name": "run_command", '
            '"args": {"CommandLine": "tmux list-panes"}}]}\n'
        )
        cmds = extract_commands(raw)
        self.assertEqual(cmds, ["tmux list-panes"])

    def test_extract_commands_claude_tool_use(self) -> None:
        """Should parse Claude tool_use format."""
        raw = (
            '{"type": "tool_use", "name": "Bash", '
            '"input": {"command": "tmux capture-pane -t %1 -p"}}\n'
        )
        cmds = extract_commands(raw)
        self.assertEqual(cmds, ["tmux capture-pane -t %1 -p"])

    def test_run_dry_test_valid_case(self) -> None:
        """Should pass schema validation for valid case."""
        case = {
            "id": 1,
            "prompt": "Test prompt",
            "expected_output": "Expected output",
            "expectations": ["Must do X"],
            "expected_command_patterns": ["^tmux"],
            "forbidden_command_patterns": ["^rm"],
        }
        passed, errors = run_dry_test(case)
        self.assertTrue(passed)
        self.assertEqual(len(errors), 0)

    def test_run_dry_test_missing_field(self) -> None:
        """Should detect missing required schema fields."""
        case = {
            "id": 1,
            "prompt": "Test prompt",
            "expectations": ["Must do X"],
        }
        passed, errors = run_dry_test(case)
        self.assertFalse(passed)
        self.assertTrue(any("expected_output" in e for e in errors))

    def test_run_dry_test_invalid_regex(self) -> None:
        """Should detect invalid regex patterns."""
        case = {
            "id": 1,
            "prompt": "Test prompt",
            "expected_output": "Expected output",
            "expectations": ["Must do X"],
            "expected_command_patterns": ["[unclosed-bracket"],
        }
        passed, errors = run_dry_test(case)
        self.assertFalse(passed)
        self.assertTrue(any("Invalid regex" in e for e in errors))

    def test_load_dataset_valid(self) -> None:
        """Should load canonical evals.json format."""
        evals_path = Path(__file__).parent / "evals.json"
        skill_name, cases = load_dataset(evals_path)
        self.assertEqual(skill_name, "controlling-tmux")
        self.assertEqual(len(cases), 12)

    @mock.patch("subprocess.run")
    def test_setup_dummy_tmux_mocked(self, mock_run: mock.MagicMock) -> None:
        """Should invoke tmux session creation."""
        mock_proc = mock.create_autospec(subprocess.CompletedProcess, instance=True)
        mock_proc.stdout = "%0\n"
        mock_run.return_value = mock_proc

        ok, pane = setup_dummy_tmux("test-sock")
        self.assertTrue(ok)
        self.assertEqual(pane, "%0")

    @mock.patch("subprocess.run")
    def test_teardown_dummy_tmux(self, mock_run: mock.MagicMock) -> None:
        """Should invoke tmux kill-server."""
        teardown_dummy_tmux("test-sock")
        mock_run.assert_called_once()

    @mock.patch("sys.stderr", new_callable=io.StringIO)
    def test_main_cli_missing_dataset(self, mock_stderr: io.StringIO) -> None:
        """Should exit 1 when dataset file does not exist."""
        with self.assertRaises(SystemExit) as cm:
            main(["--dataset", "/path/to/nonexistent/evals.json"])
        self.assertEqual(cm.exception.code, 1)
        self.assertIn("Dataset not found", mock_stderr.getvalue())

    @mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_main_cli_dry_run(self, mock_stdout: io.StringIO) -> None:
        """Should execute dry schema validation and return cleanly."""
        main(["--case", "1"])
        self.assertIn("Eval #1", mock_stdout.getvalue())
        self.assertIn("1/1 Passed", mock_stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
