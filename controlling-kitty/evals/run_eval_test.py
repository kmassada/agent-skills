#!/usr/bin/env python3
"""Companion unit tests for run_eval.py in controlling-kitty."""

import io
import json
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

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

    # --- malformed agent output -------------------------------------------

    def test_extract_commands_tolerates_null_fields(self) -> None:
        """A null name or args must not abort extraction."""
        # A null name skips the structured branch; the regex fallback still
        # recovers the command, which is the intended degraded behaviour.
        self.assertEqual(
            run_eval.extract_commands(
                json.dumps({"name": None, "input": {"command": "kitty @ ls"}})
            ),
            ["kitty @ ls"],
        )
        # Null args yield nothing to extract, and must not raise.
        self.assertEqual(
            run_eval.extract_commands(
                json.dumps({"tool_calls": [{"name": "run_command", "args": None}]})
            ),
            [],
        )

    def test_extract_commands_skips_bad_lines_and_keeps_good(self) -> None:
        """One malformed line does not discard the rest of the stream."""
        raw = "\n".join(
            [
                "not json at all",
                json.dumps({"tool_calls": None}),
                json.dumps([1, 2, 3]),
                json.dumps(
                    {
                        "tool_calls": [
                            {
                                "name": "run_command",
                                "args": {"CommandLine": "kitty @ ls"},
                            }
                        ]
                    }
                ),
            ]
        )
        self.assertEqual(run_eval.extract_commands(raw), ["kitty @ ls"])

    def test_extract_commands_content_blocks(self) -> None:
        """Extracts commands from nested Claude content blocks."""
        raw = json.dumps(
            {
                "content": [
                    {"type": "text", "text": "thinking"},
                    {
                        "type": "tool_use",
                        "name": "Bash",
                        "input": {"command": "kitty @ get-text --match id:2"},
                    },
                ]
            }
        )
        self.assertEqual(
            run_eval.extract_commands(raw), ["kitty @ get-text --match id:2"]
        )

    # --- live-run trustworthiness -----------------------------------------

    def _case(self, **overrides: object) -> dict[str, object]:
        case: dict[str, object] = {
            "id": 1,
            "prompt": "p",
            "expected_output": "o",
            "expectations": ["e"],
            "expected_command_patterns": [],
            "forbidden_command_patterns": ["kitty @"],
        }
        case.update(overrides)
        return case

    def test_run_live_case_fails_on_nonzero_exit(self) -> None:
        """A failed CLI run must not score as a passing negative case."""
        proc = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="FATAL: auth error"
        )
        with mock.patch("run_eval.subprocess.run", return_value=proc):
            passed, failures = run_eval.run_live_case(self._case(), "claude")
        self.assertFalse(passed)
        self.assertIn("exited 1", failures[0])

    def test_run_live_case_fails_on_empty_stdout(self) -> None:
        """No output means nothing was evaluated, not that the case passed."""
        proc = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="   \n", stderr=""
        )
        with mock.patch("run_eval.subprocess.run", return_value=proc):
            passed, failures = run_eval.run_live_case(self._case(), "claude")
        self.assertFalse(passed)
        self.assertIn("no stdout", failures[0])

    def test_run_live_case_passes_clean_negative(self) -> None:
        """A real run with no kitty commands still passes a negative case."""
        proc = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(
                {
                    "type": "tool_use",
                    "name": "bash",
                    "input": {"command": "python3 -c 'print(1)'"},
                }
            ),
            stderr="",
        )
        with mock.patch("run_eval.subprocess.run", return_value=proc):
            passed, failures = run_eval.run_live_case(self._case(), "claude")
        self.assertTrue(passed, failures)

    def test_run_live_case_flags_forbidden_command(self) -> None:
        """Kitty usage on a negative prompt is reported as a false positive."""
        proc = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(
                {
                    "type": "tool_use",
                    "name": "bash",
                    "input": {"command": "kitty @ send-text --match id:2 'x\\r'"},
                }
            ),
            stderr="",
        )
        with mock.patch("run_eval.subprocess.run", return_value=proc):
            passed, failures = run_eval.run_live_case(self._case(), "claude")
        self.assertFalse(passed)
        self.assertTrue(any("false-positive" in f for f in failures))

    def test_run_live_case_unknown_backend(self) -> None:
        """An unrecognized backend fails rather than silently passing."""
        passed, failures = run_eval.run_live_case(self._case(), "nonesuch")
        self.assertFalse(passed)
        self.assertIn("Unknown backend", failures[0])

    def test_run_live_case_timeout(self) -> None:
        """A timeout is reported as a failure."""
        with mock.patch(
            "run_eval.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=45),
        ):
            passed, failures = run_eval.run_live_case(self._case(), "claude")
        self.assertFalse(passed)
        self.assertIn("timed out", failures[0])

    # --- schema validation -------------------------------------------------

    def test_run_dry_test_rejects_bad_regex(self) -> None:
        """Invalid regexes in the dataset are reported."""
        case = {
            "id": 1,
            "prompt": "p",
            "expected_output": "o",
            "expectations": ["e"],
            "expected_command_patterns": ["kitty @ ls("],
        }
        passed, errors = run_eval.run_dry_test(case)
        self.assertFalse(passed)
        self.assertTrue(any("Invalid regex" in e for e in errors))

    def test_run_dry_test_rejects_empty_expectations(self) -> None:
        """An empty expectations list is a schema error."""
        case = {
            "id": 1,
            "prompt": "p",
            "expected_output": "o",
            "expectations": [],
        }
        passed, errors = run_eval.run_dry_test(case)
        self.assertFalse(passed)
        self.assertTrue(any("non-empty list" in e for e in errors))

    # --- dataset + suite wiring -------------------------------------------

    def test_load_dataset_legacy_list(self) -> None:
        """A bare list dataset is accepted as the legacy schema."""
        with TemporaryDirectory() as tmpdir:
            fpath = Path(tmpdir) / "evals.json"
            fpath.write_text(json.dumps([{"id": 1}]), encoding="utf-8")
            name, cases = run_eval.load_dataset(fpath)
        self.assertEqual(name, "legacy")
        self.assertEqual(len(cases), 1)

    def test_load_dataset_rejects_unknown_schema(self) -> None:
        """An unrecognized top-level shape raises."""
        with TemporaryDirectory() as tmpdir:
            fpath = Path(tmpdir) / "evals.json"
            fpath.write_text(json.dumps({"nope": 1}), encoding="utf-8")
            with self.assertRaises(ValueError):
                run_eval.load_dataset(fpath)

    def test_main_requires_yes_for_live(self) -> None:
        """Live mode refuses to run without explicit confirmation."""
        with mock.patch("sys.stderr", new_callable=io.StringIO) as err:
            with self.assertRaises(SystemExit) as ctx:
                run_eval.main(["--live"])
        self.assertEqual(ctx.exception.code, 1)
        self.assertIn("Refusing to run --live", err.getvalue())

    def test_main_rejects_empty_dataset(self) -> None:
        """An eval file with no cases is an error, not a 0/0 pass."""
        with TemporaryDirectory() as tmpdir:
            fpath = Path(tmpdir) / "evals.json"
            fpath.write_text(json.dumps({"evals": []}), encoding="utf-8")
            with mock.patch("sys.stderr", new_callable=io.StringIO):
                with mock.patch("sys.stdout", new_callable=io.StringIO):
                    with self.assertRaises(SystemExit) as ctx:
                        run_eval.main(["--dataset", str(fpath)])
        self.assertEqual(ctx.exception.code, 1)

    def test_main_returns_zero_on_shipped_dataset(self) -> None:
        """The shipped evals.json passes schema conformance."""
        with mock.patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(run_eval.main([]), 0)


if __name__ == "__main__":
    unittest.main()
