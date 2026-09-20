#!/usr/bin/env python3
"""Companion unit tests for run_eval.py in controlling-kitty."""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import run_eval


class TestRunEval(unittest.TestCase):
    """Unit tests for Kitty skill evaluation suite logic."""

    def test_evaluate_commands_success(self) -> None:
        """Passes when expected patterns match and forbidden do not."""
        commands = [
            "kitty @ send-text --match id:2 'pytest tests/test_api.py\\r'",
            "kitty @ get-text --match id:2",
        ]
        expected = ["kitty @ send-text.*pytest"]
        forbidden = ["^pytest tests/"]
        passed, failures = run_eval.evaluate_commands(commands, expected, forbidden)
        self.assertTrue(passed)
        self.assertEqual(len(failures), 0)

    def test_evaluate_commands_forbidden_triggered(self) -> None:
        """Fails when forbidden pattern is matched."""
        commands = ["pytest tests/test_api.py"]
        expected = []
        forbidden = ["^pytest tests/"]
        passed, failures = run_eval.evaluate_commands(commands, expected, forbidden)
        self.assertFalse(passed)
        self.assertEqual(len(failures), 1)
        self.assertIn("Triggered forbidden anti-pattern", failures[0])

    def test_evaluate_commands_missing_expected(self) -> None:
        """Fails when expected pattern is missing."""
        commands = ["kitty @ ls"]
        expected = ["kitty @ launch"]
        forbidden = []
        passed, failures = run_eval.evaluate_commands(commands, expected, forbidden)
        self.assertFalse(passed)
        self.assertIn("Missing expected command pattern", failures[0])

    def test_extract_commands_json_tool_calls(self) -> None:
        """Extracts CommandLine from agy tool_calls structure."""
        raw = json.dumps(
            {
                "tool_calls": [
                    {
                        "name": "run_command",
                        "args": {"CommandLine": "kitty @ ls"},
                    }
                ]
            }
        )
        cmds = run_eval.extract_commands(raw)
        self.assertEqual(cmds, ["kitty @ ls"])

    def test_extract_commands_claude_tool_use(self) -> None:
        """Extracts command from Claude tool_use structure."""
        raw = json.dumps(
            {
                "type": "tool_use",
                "name": "bash",
                "input": {"command": "kitty @ launch --type=tab"},
            }
        )
        cmds = run_eval.extract_commands(raw)
        self.assertEqual(cmds, ["kitty @ launch --type=tab"])

    def test_run_dry_test_valid(self) -> None:
        """Validates valid test case conforms to Claude schema."""
        case = {
            "id": 1,
            "prompt": "List windows",
            "expected_output": "Lists windows",
            "expectations": ["Must call kitty @ ls"],
            "expected_command_patterns": ["kitty @ ls"],
            "forbidden_command_patterns": [],
        }
        passed, errors = run_eval.run_dry_test(case)
        self.assertTrue(passed)
        self.assertEqual(len(errors), 0)

    def test_run_dry_test_missing_keys(self) -> None:
        """Detects missing required Claude schema fields."""
        case = {"id": 1}
        passed, errors = run_eval.run_dry_test(case)
        self.assertFalse(passed)
        self.assertTrue(any("Missing Claude-schema" in err for err in errors))

    def test_load_dataset(self) -> None:
        """Loads dataset from JSON file."""
        with TemporaryDirectory() as tmpdir:
            fpath = Path(tmpdir) / "evals.json"
            fpath.write_text(
                json.dumps(
                    {
                        "skill_name": "controlling-kitty",
                        "evals": [{"id": 1, "prompt": "test"}],
                    }
                ),
                encoding="utf-8",
            )
            name, cases = run_eval.load_dataset(fpath)
            self.assertEqual(name, "controlling-kitty")
            self.assertEqual(len(cases), 1)


if __name__ == "__main__":
    unittest.main()
