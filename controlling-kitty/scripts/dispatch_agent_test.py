#!/usr/bin/env python3
"""Companion unit tests for dispatch_agent.py in controlling-kitty."""

import io
import json
import unittest
from pathlib import Path
from unittest import mock

import dispatch_agent


class TestDispatchAgent(unittest.TestCase):
    """Unit tests for Kitty agent dispatch helper."""

    def test_slugify_title(self) -> None:
        """Sanitizes text prompts into clean short slugs."""
        self.assertEqual(
            dispatch_agent.slugify_title("Refactor SQLite database models"),
            "refactor-sqlite-data",
        )
        self.assertEqual(dispatch_agent.slugify_title(""), "agent")
        self.assertEqual(dispatch_agent.slugify_title("!@#$%^"), "agent")
        self.assertEqual(dispatch_agent.slugify_title("simple test"), "simple-test")

    def test_build_agent_command_interactive(self) -> None:
        """Builds standard interactive launch command."""
        cmd = dispatch_agent.build_agent_command(prompt="Fix tests")
        self.assertEqual(cmd, "agy -i 'Fix tests'")

    def test_build_agent_command_with_options(self) -> None:
        """Builds command with conversation ID, model, and agent name."""
        cmd = dispatch_agent.build_agent_command(
            conversation_id="conv-123",
            agent_name="reviewer",
            model="flash",
        )
        self.assertEqual(
            cmd, "agy --conversation conv-123 --agent reviewer --model flash"
        )

    def test_build_agent_command_continue(self) -> None:
        """Builds command with --continue flag."""
        cmd = dispatch_agent.build_agent_command(continue_recent=True)
        self.assertEqual(cmd, "agy --continue")

    @mock.patch("dispatch_agent.run_command_safely")
    def test_create_api_conversation_success(self, mock_run: mock.MagicMock) -> None:
        """Extracts conversation ID from successful agentapi output."""
        mock_run.return_value = (0, '{"conversation_id": "abc-456"}', "")
        conv_id = dispatch_agent.create_api_conversation(
            prompt="Run audit",
            title="audit",
            model="pro",
        )
        self.assertEqual(conv_id, "abc-456")
        mock_run.assert_called_once()

    @mock.patch("dispatch_agent.run_command_safely")
    def test_create_api_conversation_failure(self, mock_run: mock.MagicMock) -> None:
        """Returns None when agentapi fails."""
        mock_run.return_value = (1, "", "Connection failed")
        with mock.patch("sys.stderr", new_callable=io.StringIO):
            conv_id = dispatch_agent.create_api_conversation(prompt="Run audit")
            self.assertIsNone(conv_id)

    def test_dispatch_to_kitty_dry_run_tab(self) -> None:
        """Generates dry run payload for tab dispatch."""
        res = dispatch_agent.dispatch_to_kitty(
            command_str="agy -i 'Hello'",
            title="hello-task",
            dispatch_mode="tab",
            dry_run=True,
            detached=True,
        )
        self.assertEqual(res["status"], "dry_run")
        self.assertIn("--type=tab", res["command"])
        self.assertIn("--keep-focus", res["command"])
        self.assertIn("--tab-title=hello-task", res["command"])

    def test_dispatch_to_kitty_dry_run_splits(self) -> None:
        """Generates dry run payload for split modes."""
        res_v = dispatch_agent.dispatch_to_kitty(
            command_str="agy -i 'Fix'",
            title="fix",
            dispatch_mode="split-v",
            target_window="101",
            dry_run=True,
        )
        self.assertIn("--location=vsplit", res_v["command"])
        self.assertIn("--match id:101", res_v["command"])

        res_h = dispatch_agent.dispatch_to_kitty(
            command_str="agy -i 'Fix'",
            title="fix",
            dispatch_mode="split-h",
            target_window="id:102",
            dry_run=True,
        )
        self.assertIn("--location=hsplit", res_h["command"])
        self.assertIn("--match id:102", res_h["command"])

    @mock.patch("dispatch_agent.run_command_safely")
    def test_dispatch_to_kitty_execution_success(
        self, mock_run: mock.MagicMock
    ) -> None:
        """Executes launch command and returns created window ID."""
        mock_run.return_value = (0, "15", "")
        res = dispatch_agent.dispatch_to_kitty(
            command_str="agy -i 'test'",
            title="test",
            dispatch_mode="tab",
            cwd=Path("/tmp"),
            dry_run=False,
        )
        self.assertEqual(res["status"], "created")
        self.assertEqual(res["window_id"], "15")

    @mock.patch("dispatch_agent.run_command_safely")
    def test_dispatch_to_kitty_execution_failure(
        self, mock_run: mock.MagicMock
    ) -> None:
        """Raises RuntimeError on launch failure."""
        mock_run.return_value = (1, "", "Socket connection refused")
        with self.assertRaises(RuntimeError):
            dispatch_agent.dispatch_to_kitty(
                command_str="agy -i 'test'",
                title="test",
                dry_run=False,
            )

    def test_main_missing_args(self) -> None:
        """Exits with code 1 if no action arguments provided."""
        with mock.patch("sys.stderr", new_callable=io.StringIO):
            exit_code = dispatch_agent.main([])
            self.assertEqual(exit_code, 1)

    def test_main_dry_run_json(self) -> None:
        """Outputs JSON result in dry run mode."""
        with mock.patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            exit_code = dispatch_agent.main(["--prompt=hello", "--dry-run", "--json"])
            self.assertEqual(exit_code, 0)
            data = json.loads(mock_stdout.getvalue())
            self.assertEqual(data["status"], "dry_run")
            self.assertEqual(data["dispatch_mode"], "tab")


if __name__ == "__main__":
    unittest.main()
