#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Unit tests for the controlling-tmux evaluation runner (run_eval.py)."""

import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.resolve()))

from run_eval import (
    EVAL_SOCKET,
    assert_sandbox_socket,
    detect_backend,
    evaluate_commands,
    extract_commands,
    load_dataset,
    main,
    run_dry_test,
    run_live_case,
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
        self.assertEqual(len(cases), 20)

    def test_evaluate_commands_multiline_paste_patterns(self) -> None:
        """Should validate load-buffer/paste-buffer and forbid raw send-keys."""
        valid_cmds = [
            "tmux load-buffer /tmp/script.sql",
            "tmux paste-buffer -t %2",
        ]
        expected = ["tmux load-buffer", "tmux paste-buffer -t %2"]
        forbidden = ["tmux send-keys"]
        passed, failures = evaluate_commands(valid_cmds, expected, forbidden)
        self.assertTrue(passed)
        self.assertEqual(len(failures), 0)

        invalid_cmds = [
            "tmux load-buffer /tmp/script.sql",
            "tmux paste-buffer -t %2",
            "tmux send-keys -t %2 'SELECT 1;' C-m",
        ]
        passed, failures = evaluate_commands(invalid_cmds, expected, forbidden)
        self.assertFalse(passed)
        self.assertTrue(any("Triggered forbidden anti-pattern" in f for f in failures))

    def test_evaluate_commands_full_width_split_patterns(self) -> None:
        """Should validate full-width split flag -f and forbid new-window."""
        valid_cmds = ["tmux split-window -f -v -t \"$TMUX_PANE\" -P -F '#{pane_id}'"]
        expected = [r"tmux split-window -f -v.*-P -F ['\"]#\{pane_id\}['\"]"]
        forbidden = ["tmux new-window"]
        passed, failures = evaluate_commands(valid_cmds, expected, forbidden)
        self.assertTrue(passed)
        self.assertEqual(len(failures), 0)

        invalid_cmds = [
            "tmux new-window -n worker",
            "tmux split-window -f -v -t \"$TMUX_PANE\" -P -F '#{pane_id}'",
        ]
        passed, failures = evaluate_commands(invalid_cmds, expected, forbidden)
        self.assertFalse(passed)
        self.assertTrue(any("Triggered forbidden anti-pattern" in f for f in failures))

    def test_evaluate_commands_detached_session_patterns(self) -> None:
        """Should validate new-session -d -s and forbid new-window."""
        valid_cmds = ["tmux new-session -d -s worker"]
        expected = ["tmux new-session -d -s worker"]
        forbidden = ["tmux new-window"]
        passed, failures = evaluate_commands(valid_cmds, expected, forbidden)
        self.assertTrue(passed)
        self.assertEqual(len(failures), 0)

        invalid_cmds = ["tmux new-window -n worker"]
        passed, failures = evaluate_commands(invalid_cmds, expected, forbidden)
        self.assertFalse(passed)

    def test_evaluate_commands_resume_conversation_patterns(self) -> None:
        """Should validate detached window resume or dispatch_agent.py --continue."""
        valid_cmds_tmux = ["tmux new-window -d -n agy 'agy --continue'"]
        valid_cmds_script = ["python3 scripts/dispatch_agent.py --continue"]
        expected = [
            r"(tmux new-window.*agy.*--continue|dispatch_agent\.py.*--continue)"
        ]
        forbidden = [r"^agy --continue"]

        passed_tmux, _ = evaluate_commands(valid_cmds_tmux, expected, forbidden)
        self.assertTrue(passed_tmux)

        passed_script, _ = evaluate_commands(valid_cmds_script, expected, forbidden)
        self.assertTrue(passed_script)

        invalid_cmds = ["agy --continue"]
        passed, failures = evaluate_commands(invalid_cmds, expected, forbidden)
        self.assertFalse(passed)
        self.assertTrue(any("Triggered forbidden anti-pattern" in f for f in failures))

    def test_evaluate_commands_negative_query_patterns(self) -> None:
        """Should forbid any tmux invocation on non-tmux developer questions."""
        valid_cmds = ["git status"]
        expected: list[str] = []
        forbidden = ["tmux"]
        passed, failures = evaluate_commands(valid_cmds, expected, forbidden)
        self.assertTrue(passed)
        self.assertEqual(len(failures), 0)

        invalid_cmds = ["tmux display-message 'hello'"]
        passed, failures = evaluate_commands(invalid_cmds, expected, forbidden)
        self.assertFalse(passed)
        self.assertTrue(any("Triggered forbidden anti-pattern" in f for f in failures))

    def test_evaluate_commands_silent_read_focus_preservation_patterns(self) -> None:
        """Should validate capture-pane and strictly forbid select-pane/window."""
        valid_cmds = ["tmux capture-pane -t %2 -p"]
        expected = ["tmux capture-pane -t %2 -p"]
        forbidden = ["tmux select-pane", "tmux select-window"]

        passed, failures = evaluate_commands(valid_cmds, expected, forbidden)
        self.assertTrue(passed)
        self.assertEqual(len(failures), 0)

        invalid_cmds = [
            "tmux select-pane -t %2",
            "tmux capture-pane -t %2 -p",
        ]
        passed, failures = evaluate_commands(invalid_cmds, expected, forbidden)
        self.assertFalse(passed)
        self.assertTrue(any("Triggered forbidden anti-pattern" in f for f in failures))

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

    # --- Destructive-socket guard ---

    def test_assert_sandbox_socket_allows_dedicated_socket(self) -> None:
        """Should always permit the dedicated eval sandbox socket."""
        self.assertIsNone(assert_sandbox_socket(EVAL_SOCKET))

    @mock.patch("subprocess.run")
    def test_assert_sandbox_socket_refuses_live_server(
        self, mock_run: mock.MagicMock
    ) -> None:
        """Should refuse a non-sandbox socket that has live sessions."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="main: 3 windows\n", stderr=""
        )
        msg = assert_sandbox_socket("default")
        self.assertIsNotNone(msg)
        assert msg is not None
        self.assertIn("Refusing to reset socket 'default'", msg)

    @mock.patch("subprocess.run")
    def test_assert_sandbox_socket_allows_dead_socket(
        self, mock_run: mock.MagicMock
    ) -> None:
        """Should permit a non-sandbox socket with no server behind it."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="no server running"
        )
        self.assertIsNone(assert_sandbox_socket("scratch-sock"))

    # --- Command extraction robustness ---

    def test_extract_commands_tolerates_malformed_shapes(self) -> None:
        """Should never raise on unexpected field types in agent output."""
        for raw in (
            '{"type":"tool_use","name":"Bash","input":"not-a-dict"}',
            '{"tool_calls":[{"name":"run_command","args":"oops"}]}',
            '{"tool_calls":"not-a-list"}',
            '{"content":"not-a-list"}',
            '{"content":[null,7,"str"]}',
        ):
            with self.subTest(raw=raw):
                self.assertEqual(extract_commands(raw), [])

    def test_extract_commands_pretty_printed_object(self) -> None:
        """Should decode a whole-document JSON object spanning several lines."""
        raw = (
            "{\n"
            '  "type": "tool_use",\n'
            '  "name": "Bash",\n'
            '  "input": {"command": "tmux capture-pane -t %1 -p"}\n'
            "}\n"
        )
        self.assertEqual(extract_commands(raw), ["tmux capture-pane -t %1 -p"])

    def test_extract_commands_preserves_inner_quotes(self) -> None:
        """Should keep quoted arguments intact so eval patterns can match them."""
        raw = (
            '{"type":"tool_use","name":"Bash","input":{"command":'
            "\"tmux send-keys -t %2 'pytest tests/test_api.py' C-m\"}}"
        )
        cmds = extract_commands(raw)
        self.assertEqual(cmds, ["tmux send-keys -t %2 'pytest tests/test_api.py' C-m"])
        passed, _ = evaluate_commands(
            cmds,
            [r"tmux send-keys -t %2 ['\"]pytest tests/test_api\.py['\"] C-m"],
            [],
        )
        self.assertTrue(passed)

    def test_extract_commands_content_block(self) -> None:
        """Should parse tool_use blocks nested in a content array."""
        raw = (
            '{"content":[{"type":"tool_use","name":"bash",'
            '"input":{"command":"tmux list-windows"}}]}'
        )
        self.assertEqual(extract_commands(raw), ["tmux list-windows"])

    def test_extract_commands_regex_fallback_unescapes(self) -> None:
        """Should unescape the last-resort regex match rather than truncating it."""
        raw = 'trace: "command": "tmux send-keys -t %2 \\"echo hi\\" C-m" end'
        self.assertEqual(extract_commands(raw), ['tmux send-keys -t %2 "echo hi" C-m'])

    # --- Live-case scoring ---

    @mock.patch("subprocess.run")
    def test_run_live_case_fails_on_cli_error(self, mock_run: mock.MagicMock) -> None:
        """Should fail, not silently pass, when the CLI exits non-zero."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="auth error"
        )
        case = {"prompt": "p", "forbidden_command_patterns": ["tmux"]}
        passed, failures = run_live_case(case, "claude", "sock")
        self.assertFalse(passed)
        self.assertIn("exited 1", failures[0])

    @mock.patch("subprocess.run")
    def test_run_live_case_fails_on_empty_stdout(
        self, mock_run: mock.MagicMock
    ) -> None:
        """Should fail when the CLI produces nothing to score."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="   \n", stderr=""
        )
        passed, failures = run_live_case({"prompt": "p"}, "claude", "sock")
        self.assertFalse(passed)
        self.assertIn("no stdout", failures[0])

    @mock.patch("subprocess.run")
    def test_run_live_case_uses_stream_json_for_claude(
        self, mock_run: mock.MagicMock
    ) -> None:
        """Should request stream-json, the only claude format carrying tool calls."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="{}", stderr=""
        )
        run_live_case({"prompt": "p"}, "claude", "sock")
        argv = mock_run.call_args[0][0]
        self.assertEqual(argv[argv.index("--output-format") + 1], "stream-json")

    @mock.patch("subprocess.run")
    def test_run_live_case_detects_missing_activation(
        self, mock_run: mock.MagicMock
    ) -> None:
        """Should not accept a prompt echo as proof the skill activated."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout='{"type":"text","text":"I would use tmux send-keys here."}',
            stderr="",
        )
        case = {"prompt": "p", "expected_command_patterns": ["tmux send-keys"]}
        passed, failures = run_live_case(case, "claude", "sock")
        self.assertFalse(passed)
        self.assertTrue(any("did not activate" in f for f in failures))

    @mock.patch("subprocess.run")
    def test_run_live_case_flags_false_positive(self, mock_run: mock.MagicMock) -> None:
        """Should fail a negative prompt that nonetheless ran tmux."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout='{"name":"Bash","input":{"command":"tmux list-panes"}}',
            stderr="",
        )
        passed, failures = run_live_case({"prompt": "p"}, "claude", "sock")
        self.assertFalse(passed)
        self.assertTrue(any("false-positive" in f for f in failures))

    def test_run_live_case_unknown_backend(self) -> None:
        """Should reject an unrecognised backend name."""
        passed, failures = run_live_case({"prompt": "p"}, "gpt", "sock")
        self.assertFalse(passed)
        self.assertIn("Unknown backend", failures[0])

    @mock.patch(
        "subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=45),
    )
    def test_run_live_case_timeout(self, _mock_run: mock.MagicMock) -> None:
        """Should report a timeout rather than propagating the exception."""
        passed, failures = run_live_case({"prompt": "p"}, "claude", "sock")
        self.assertFalse(passed)
        self.assertIn("timed out", failures[0])

    @mock.patch("subprocess.run", side_effect=FileNotFoundError())
    def test_run_live_case_cli_missing(self, _mock_run: mock.MagicMock) -> None:
        """Should report a missing CLI binary cleanly."""
        passed, failures = run_live_case({"prompt": "p"}, "claude", "sock")
        self.assertFalse(passed)
        self.assertIn("not found in PATH", failures[0])

    # --- Dataset loading and backend detection ---

    def test_load_dataset_legacy_list(self) -> None:
        """Should accept a bare list of cases as the legacy schema."""
        path = Path(self.enterContext(tempfile.TemporaryDirectory())) / "legacy.json"
        path.write_text(json.dumps([{"id": 1}]), encoding="utf-8")
        skill_name, cases = load_dataset(path)
        self.assertEqual(skill_name, "legacy")
        self.assertEqual(len(cases), 1)

    def test_load_dataset_unrecognised_schema(self) -> None:
        """Should raise ValueError on an unrecognised top-level shape."""
        path = Path(self.enterContext(tempfile.TemporaryDirectory())) / "bad.json"
        path.write_text(json.dumps({"nope": True}), encoding="utf-8")
        with self.assertRaises(ValueError):
            load_dataset(path)

    @mock.patch("shutil.which", side_effect=lambda name: name == "claude")
    def test_detect_backend_prefers_available_cli(
        self, _mock_which: mock.MagicMock
    ) -> None:
        """Should fall through to claude when agy is not installed."""
        self.assertEqual(detect_backend(), "claude")

    @mock.patch("sys.stdout", new_callable=io.StringIO)
    @mock.patch("sys.stderr", new_callable=io.StringIO)
    def test_main_empty_dataset_exits_one(
        self, mock_stderr: io.StringIO, _mock_out: io.StringIO
    ) -> None:
        """Should exit 1 on an empty dataset rather than dividing by zero."""
        path = Path(self.enterContext(tempfile.TemporaryDirectory())) / "empty.json"
        path.write_text(json.dumps({"skill_name": "x", "evals": []}), encoding="utf-8")
        with self.assertRaises(SystemExit) as cm:
            main(["--dataset", str(path)])
        self.assertEqual(cm.exception.code, 1)
        self.assertIn("no eval cases", mock_stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
