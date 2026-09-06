#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Companion unit tests for dispatch_agent.py."""

import json
import unittest
from collections.abc import Sequence
from pathlib import Path
from unittest import mock

from dispatch_agent import (
    build_agent_command,
    create_api_conversation,
    dispatch_to_tmux,
    main,
    parse_arguments,
    run_command_safely,
    slugify_title,
)


class TestDispatchAgent(unittest.TestCase):
    """Unit tests for agent dispatch helpers and CLI."""

    def test_slugify_title_normal(self) -> None:
        """Should convert standard prompt strings into kebab slugs."""
        slug = slugify_title("Run Pytest on API Module")
        self.assertEqual(slug, "run-pytest-on-api-mo")

    def test_slugify_title_special_chars(self) -> None:
        """Should strip punctuation and special characters."""
        slug = slugify_title("Fix #123: [Bug] Can't parse (yaml)?!")
        self.assertEqual(slug, "fix-123-bug-can-t-pa")

    def test_slugify_title_empty(self) -> None:
        """Should fallback to 'agent' when input contains no alphanumeric characters."""
        self.assertEqual(slugify_title(""), "agent")
        self.assertEqual(slugify_title("   ??? !!!  "), "agent")

    def test_build_agent_command_interactive(self) -> None:
        """Should construct agy invocation with prompt flag."""
        cmd = build_agent_command(prompt="Investigate bug")
        self.assertEqual(cmd, "agy -i 'Investigate bug'")

    def test_build_agent_command_conversation(self) -> None:
        """Should construct agy invocation with conversation ID."""
        cmd = build_agent_command(conversation_id="conv-98765")
        self.assertEqual(cmd, "agy --conversation conv-98765")

    def test_build_agent_command_continue(self) -> None:
        """Should construct agy invocation with --continue."""
        cmd = build_agent_command(continue_recent=True)
        self.assertEqual(cmd, "agy --continue")

    def test_build_agent_command_with_agent_and_model(self) -> None:
        """Should include agent and model flags."""
        cmd = build_agent_command(
            prompt="Refactor database schema",
            agent_name="reviewer",
            model="flash",
        )
        self.assertIn("--agent reviewer", cmd)
        self.assertIn("--model flash", cmd)
        self.assertIn("-i 'Refactor database schema'", cmd)

    def test_build_agent_command_extra_flags(self) -> None:
        """Should append extra flags."""
        extra: Sequence[str] = ["--add-dir", "/tmp/project"]
        cmd = build_agent_command(prompt="Task", extra_flags=extra)
        self.assertIn("--add-dir /tmp/project", cmd)

    def test_run_command_safely(self) -> None:
        """Should run a pure subprocess command safely."""
        code, stdout, stderr = run_command_safely(["echo", "hello world"])
        self.assertEqual(code, 0)
        self.assertEqual(stdout, "hello world")
        self.assertEqual(stderr, "")

    @mock.patch("dispatch_agent.run_command_safely")
    def test_create_api_conversation_json_success(
        self, mock_run: mock.MagicMock
    ) -> None:
        """Should parse JSON conversationId from agentapi output."""
        mock_run.return_value = (
            0,
            json.dumps({"conversationId": "c-12345"}),
            "",
        )
        conv_id = create_api_conversation(
            "Start conversation",
            title="test-title",
            model="pro",
        )
        self.assertEqual(conv_id, "c-12345")
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        self.assertIn("--model=pro", args)
        self.assertIn("--title=test-title", args)

    @mock.patch("dispatch_agent.run_command_safely")
    def test_create_api_conversation_plain_text_success(
        self, mock_run: mock.MagicMock
    ) -> None:
        """Should parse plain string conversation ID from agentapi output."""
        mock_run.return_value = (0, "c-plain-67890\n", "")
        conv_id = create_api_conversation("Start conversation")
        self.assertEqual(conv_id, "c-plain-67890")

    @mock.patch("dispatch_agent.run_command_safely")
    def test_create_api_conversation_failure(self, mock_run: mock.MagicMock) -> None:
        """Should return None on non-zero exit code."""
        mock_run.return_value = (1, "", "API connection error")
        conv_id = create_api_conversation("Failing task")
        self.assertIsNone(conv_id)

    @mock.patch("dispatch_agent.run_command_safely")
    def test_dispatch_to_tmux_window_success(self, mock_run: mock.MagicMock) -> None:
        """Should dispatch to a new window and parse IDs."""
        mock_run.return_value = (0, "@15 %42", "")
        res = dispatch_to_tmux(
            command_str="agy -i 'Task'",
            title="my-window",
            dispatch_mode="window",
            cwd=Path("/tmp"),
            detached=True,
        )
        self.assertEqual(res["status"], "created")
        self.assertEqual(res["window_id"], "@15")
        self.assertEqual(res["pane_id"], "%42")
        self.assertEqual(res["title"], "my-window")

    @mock.patch("dispatch_agent.run_command_safely")
    def test_dispatch_to_tmux_split_h_success(self, mock_run: mock.MagicMock) -> None:
        """Should dispatch to horizontal split pane."""
        mock_run.return_value = (0, "%43", "")
        res = dispatch_to_tmux(
            command_str="agy -i 'Task'",
            title="split-task",
            dispatch_mode="split-h",
            target_pane="%10",
        )
        self.assertEqual(res["status"], "created")
        self.assertEqual(res["pane_id"], "%43")

    @mock.patch("dispatch_agent.run_command_safely")
    def test_dispatch_to_tmux_split_v_success(self, mock_run: mock.MagicMock) -> None:
        """Should dispatch to vertical split pane."""
        mock_run.return_value = (0, "%44", "")
        res = dispatch_to_tmux(
            command_str="agy -i 'Task'",
            title="split-task",
            dispatch_mode="split-v",
            target_pane="%10",
        )
        self.assertEqual(res["status"], "created")
        self.assertEqual(res["pane_id"], "%44")

    def test_dispatch_to_tmux_invalid_mode(self) -> None:
        """Should raise ValueError on invalid dispatch mode."""
        with self.assertRaises(ValueError):
            dispatch_to_tmux(
                command_str="agy",
                title="test",
                dispatch_mode="unsupported",
            )

    @mock.patch("dispatch_agent.run_command_safely")
    def test_dispatch_to_tmux_failure(self, mock_run: mock.MagicMock) -> None:
        """Should raise RuntimeError when tmux exits with non-zero code."""
        mock_run.return_value = (1, "", "tmux: no server running")
        with self.assertRaises(RuntimeError):
            dispatch_to_tmux(
                command_str="agy",
                title="test",
                dispatch_mode="window",
            )

    def test_dispatch_to_tmux_dry_run(self) -> None:
        """Should return planned command in dry run without invoking tmux."""
        res = dispatch_to_tmux(
            command_str="agy -i 'Hello'",
            title="dry-window",
            dispatch_mode="window",
            dry_run=True,
        )
        self.assertEqual(res["status"], "dry_run")
        self.assertIn("tmux new-window", res["command"])

    def test_parse_arguments_defaults(self) -> None:
        """Should parse default flags correctly."""
        args = parse_arguments(["--prompt", "Do something"])
        self.assertEqual(args.prompt, "Do something")
        self.assertEqual(args.mode, "window")
        self.assertEqual(args.method, "interactive")
        self.assertFalse(args.focus)

    def test_main_missing_required_args(self) -> None:
        """Should exit with 1 when no prompt, conversation, or continue is provided."""
        code = main([])
        self.assertEqual(code, 1)

    @mock.patch("dispatch_agent.dispatch_to_tmux")
    def test_main_success_flow(self, mock_dispatch: mock.MagicMock) -> None:
        """Should execute full dispatch flow cleanly."""
        mock_dispatch.return_value = {
            "status": "created",
            "window_id": "@20",
            "pane_id": "%50",
            "title": "audit",
        }
        code = main(["--prompt", "Audit repo", "--title", "audit", "--json"])
        self.assertEqual(code, 0)
        mock_dispatch.assert_called_once()

    def test_dispatch_to_tmux_with_socket(self) -> None:
        """Should include -L flag when socket is specified."""
        res = dispatch_to_tmux(
            command_str="agy -i 'Hello'",
            title="sock-window",
            dispatch_mode="window",
            dry_run=True,
            socket="mysocket",
        )
        self.assertEqual(res["status"], "dry_run")
        self.assertIn("tmux -L mysocket new-window", res["command"])

    def test_parse_arguments_socket(self) -> None:
        """Should parse --socket and -L flags."""
        args = parse_arguments(["--prompt", "Hi", "--socket", "custom_sock"])
        self.assertEqual(args.socket, "custom_sock")

    def test_main_dry_run_json(self) -> None:
        """Should output dry run JSON cleanly."""
        code = main(["--prompt", "Run build", "--dry-run", "--json"])
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
