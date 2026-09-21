#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Companion unit tests for dispatch_agent.py."""

import io
import json
import sys
import unittest
from collections.abc import Sequence
from pathlib import Path
from unittest import mock

# Ensure script directory is on sys.path for direct or module execution
sys.path.insert(0, str(Path(__file__).resolve().parent))

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

    def test_build_agent_command_conversation_with_agent_and_model(self) -> None:
        """Should include agent and model flags when resuming conversation."""
        cmd = build_agent_command(
            conversation_id="conv-12345",
            agent_name="db-specialist",
            model="pro",
        )
        self.assertIn("--conversation conv-12345", cmd)
        self.assertIn("--agent db-specialist", cmd)
        self.assertIn("--model pro", cmd)

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
    def test_create_api_conversation_malformed_json_fallback(
        self, mock_run: mock.MagicMock
    ) -> None:
        """Should fall back to plain text when agentapi outputs malformed JSON."""
        mock_run.return_value = (0, "not-json-conv-12345\n", "")
        conv_id = create_api_conversation("Start conversation")
        self.assertEqual(conv_id, "not-json-conv-12345")

    @mock.patch("sys.stderr", new_callable=io.StringIO)
    @mock.patch("dispatch_agent.run_command_safely")
    def test_create_api_conversation_empty_stdout(
        self, mock_run: mock.MagicMock, _mock_err: io.StringIO
    ) -> None:
        """Should return None when agentapi outputs empty stdout."""
        mock_run.return_value = (0, "", "")
        conv_id = create_api_conversation("Start conversation")
        self.assertIsNone(conv_id)

    @mock.patch("sys.stderr", new_callable=io.StringIO)
    @mock.patch("dispatch_agent.run_command_safely")
    def test_create_api_conversation_failure(
        self, mock_run: mock.MagicMock, _mock_err: io.StringIO
    ) -> None:
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

    def test_dispatch_to_tmux_custom_cwd_resolution(self) -> None:
        """Should resolve custom --cwd directory into full path in tmux command."""
        target_dir = Path("/tmp")
        res = dispatch_to_tmux(
            command_str="agy -i 'Task'",
            title="cwd-window",
            dispatch_mode="window",
            cwd=target_dir,
            dry_run=True,
        )
        resolved = str(target_dir.resolve())
        self.assertIn(f"-c {resolved}", res["command"])

    def test_dispatch_to_tmux_focus_omits_detached_flag(self) -> None:
        """Should omit detached flag -d when focus is requested."""
        res = dispatch_to_tmux(
            command_str="agy -i 'Task'",
            title="focused-window",
            dispatch_mode="window",
            detached=False,
            dry_run=True,
        )
        tokens = res["command"].split()
        self.assertNotIn("-d", tokens)

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

    @mock.patch("sys.stderr", new_callable=io.StringIO)
    def test_main_missing_required_args(self, _mock_err: io.StringIO) -> None:
        """Should exit with 1 when no prompt, conversation, or continue is provided."""
        code = main([])
        self.assertEqual(code, 1)

    @mock.patch("sys.stdout", new_callable=io.StringIO)
    @mock.patch("dispatch_agent.dispatch_to_tmux")
    def test_main_success_flow(
        self, mock_dispatch: mock.MagicMock, _mock_out: io.StringIO
    ) -> None:
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

    @mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_main_dry_run_json(self, _mock_out: io.StringIO) -> None:
        """Should output dry run JSON cleanly."""
        code = main(["--prompt", "Run build", "--dry-run", "--json"])
        self.assertEqual(code, 0)

    # --- Conversation-ID parsing contract ---

    @mock.patch("sys.stderr", new_callable=io.StringIO)
    @mock.patch("dispatch_agent.run_command_safely")
    def test_create_api_conversation_json_without_id_returns_none(
        self, mock_run: mock.MagicMock, _mock_err: io.StringIO
    ) -> None:
        """Should return None, not an empty string, for JSON lacking an ID key."""
        mock_run.return_value = (0, json.dumps({"convo": "abc-123"}), "")
        self.assertIsNone(create_api_conversation("Start conversation"))

    @mock.patch("dispatch_agent.run_command_safely")
    def test_create_api_conversation_snake_case_key(
        self, mock_run: mock.MagicMock
    ) -> None:
        """Should accept the snake_case conversation_id spelling."""
        mock_run.return_value = (0, json.dumps({"conversation_id": "c-77"}), "")
        self.assertEqual(create_api_conversation("Start"), "c-77")

    @mock.patch("dispatch_agent.run_command_safely")
    def test_create_api_conversation_ends_options_before_prompt(
        self, mock_run: mock.MagicMock
    ) -> None:
        """Should pass -- so a prompt starting with '-' is not read as a flag."""
        mock_run.return_value = (0, "c-1", "")
        create_api_conversation("--profile=/etc/passwd")
        argv = list(mock_run.call_args[0][0])
        self.assertEqual(argv[-2:], ["--", "--profile=/etc/passwd"])

    @mock.patch("dispatch_agent.run_command_safely")
    def test_create_api_conversation_forwards_profile(
        self, mock_run: mock.MagicMock
    ) -> None:
        """Should forward the profile flag to agentapi."""
        mock_run.return_value = (0, "c-1", "")
        create_api_conversation("Start", profile="sandbox")
        self.assertIn("--profile=sandbox", mock_run.call_args[0][0])

    def test_run_command_safely_honours_cwd(self) -> None:
        """Should execute the subprocess in the requested working directory."""
        code, stdout, _ = run_command_safely(["pwd"], cwd=Path("/"))
        self.assertEqual(code, 0)
        self.assertEqual(stdout, "/")

    # --- Split anchoring (focus safety) ---

    def test_dispatch_to_tmux_split_requires_anchor(self) -> None:
        """Should refuse to split without an anchor rather than hit focused pane."""
        for mode in ("split-h", "split-v"):
            with self.subTest(mode=mode), self.assertRaises(ValueError) as ctx:
                dispatch_to_tmux(
                    command_str="agy",
                    title="test",
                    dispatch_mode=mode,
                    target_pane=None,
                    dry_run=True,
                )
            self.assertIn("anchor pane", str(ctx.exception))

    def test_dispatch_to_tmux_split_includes_target_flag(self) -> None:
        """Should anchor the split to the supplied pane with -t."""
        res = dispatch_to_tmux(
            command_str="agy",
            title="test",
            dispatch_mode="split-h",
            target_pane="%10",
            dry_run=True,
        )
        self.assertIn("-t %10", res["command"])

    @mock.patch.dict("os.environ", {}, clear=True)
    @mock.patch("sys.stderr", new_callable=io.StringIO)
    def test_main_split_without_tmux_pane_exits_one(
        self, mock_err: io.StringIO
    ) -> None:
        """Should fail cleanly when a split is asked for outside tmux."""
        code = main(["--prompt", "Task", "--mode", "split-h", "--dry-run"])
        self.assertEqual(code, 1)
        self.assertIn("anchor pane", mock_err.getvalue())

    # --- Window-title sanitisation ---

    @mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_main_sanitises_explicit_title(self, mock_out: io.StringIO) -> None:
        """Should slug an explicit --title so control characters cannot reach tmux."""
        main(
            ["--prompt", "hi", "--title", "evil; rm -rf ~\nbad", "--dry-run", "--json"]
        )
        planned = json.loads(mock_out.getvalue())["command"]
        self.assertNotIn(";", planned.split("-c ")[0])
        self.assertNotIn("\n", planned.split("-c ")[0])

    @mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_main_derives_title_from_conversation(self, mock_out: io.StringIO) -> None:
        """Should derive a slugged window title from the conversation ID."""
        main(["--conversation", "d202f5d4-f6b7-4b75", "--dry-run", "--json"])
        self.assertIn("conv-d202f5d4", mock_out.getvalue())

    # --- Dry-run fidelity ---

    @mock.patch("sys.stdout", new_callable=io.StringIO)
    @mock.patch("dispatch_agent.create_api_conversation")
    def test_main_dry_run_api_does_not_call_agentapi(
        self, mock_create: mock.MagicMock, mock_out: io.StringIO
    ) -> None:
        """Should show a placeholder conversation instead of a prompt-less agy."""
        code = main(["--prompt", "Audit", "--method", "api", "--dry-run", "--json"])
        self.assertEqual(code, 0)
        mock_create.assert_not_called()
        payload = json.loads(mock_out.getvalue())
        self.assertIn("--conversation", payload["inner_command"])
        self.assertIn("note", payload)

    @mock.patch("sys.stdout", new_callable=io.StringIO)
    @mock.patch("dispatch_agent.dispatch_to_tmux")
    @mock.patch("dispatch_agent.create_api_conversation", return_value="c-501")
    def test_main_api_method_creates_conversation(
        self,
        mock_create: mock.MagicMock,
        mock_dispatch: mock.MagicMock,
        _mock_out: io.StringIO,
    ) -> None:
        """Should create a conversation then launch agy against it."""
        mock_dispatch.return_value = {"status": "created", "pane_id": "%9"}
        code = main(["--prompt", "Audit", "--method", "api", "--json"])
        self.assertEqual(code, 0)
        mock_create.assert_called_once()
        self.assertIn(
            "--conversation c-501", mock_dispatch.call_args.kwargs["command_str"]
        )

    @mock.patch("sys.stderr", new_callable=io.StringIO)
    @mock.patch("dispatch_agent.create_api_conversation", return_value=None)
    def test_main_api_method_failure_exits_one(
        self, _mock_create: mock.MagicMock, _mock_err: io.StringIO
    ) -> None:
        """Should exit 1 when the conversation cannot be created."""
        self.assertEqual(main(["--prompt", "Audit", "--method", "api"]), 1)

    @mock.patch("sys.stderr", new_callable=io.StringIO)
    @mock.patch(
        "dispatch_agent.dispatch_to_tmux", side_effect=RuntimeError("no server")
    )
    def test_main_dispatch_failure_exits_one(
        self, _mock_dispatch: mock.MagicMock, mock_err: io.StringIO
    ) -> None:
        """Should report dispatch failures and exit 1 rather than raising."""
        self.assertEqual(main(["--prompt", "Task"]), 1)
        self.assertIn("Dispatch error", mock_err.getvalue())

    # --- Previously unreachable CLI surface ---

    @mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_main_extra_flags_reach_agy(self, mock_out: io.StringIO) -> None:
        """Should forward repeated --extra-flag values into the agy command."""
        main(
            [
                "--prompt",
                "Task",
                "--extra-flag=--add-dir",
                "--extra-flag=/tmp/project",
                "--dry-run",
                "--json",
            ]
        )
        inner = json.loads(mock_out.getvalue())["inner_command"]
        self.assertIn("--add-dir /tmp/project", inner)

    def test_parse_arguments_profile_and_extra_flags(self) -> None:
        """Should expose profile and extra-flag on the CLI."""
        args = parse_arguments(
            ["--prompt", "Hi", "--profile", "sandbox", "--extra-flag=-x"]
        )
        self.assertEqual(args.profile, "sandbox")
        self.assertEqual(args.extra_flags, ["-x"])


if __name__ == "__main__":
    unittest.main()
