#!/usr/bin/env python3
"""Companion unit tests for dispatch_agent.py in controlling-kitty."""

import io
import json
import os
import unittest
from pathlib import Path
from unittest import mock

import dispatch_agent


class TestDispatchAgent(unittest.TestCase):
    """Unit tests for Kitty agent dispatch helper."""

    def setUp(self) -> None:
        """Isolates tests from any real Kitty session in the environment.

        dispatch_to_kitty falls back to $KITTY_LISTEN_ON and main() falls back
        to $KITTY_WINDOW_ID, so running inside a live Kitty would otherwise
        change the commands under assertion.
        """
        clean_env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("KITTY_LISTEN_ON", "KITTY_WINDOW_ID")
        }
        patcher = mock.patch.dict(os.environ, clean_env, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

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
        self.assertEqual(cmd, ["agy", "-i", "Fix tests"])

    def test_build_agent_command_keeps_prompt_unquoted(self) -> None:
        """Passes shell metacharacters through verbatim as a single argv item."""
        prompt = "fix $PATH and `date` and 'quotes'"
        cmd = dispatch_agent.build_agent_command(prompt=prompt)
        self.assertEqual(cmd, ["agy", "-i", prompt])

    def test_build_agent_command_with_options(self) -> None:
        """Builds command with conversation ID, model, and agent name."""
        cmd = dispatch_agent.build_agent_command(
            conversation_id="conv-123",
            agent_name="reviewer",
            model="flash",
        )
        self.assertEqual(
            cmd,
            [
                "agy",
                "--conversation",
                "conv-123",
                "--agent",
                "reviewer",
                "--model",
                "flash",
            ],
        )

    def test_build_agent_command_continue(self) -> None:
        """Builds command with --continue flag."""
        cmd = dispatch_agent.build_agent_command(continue_recent=True)
        self.assertEqual(cmd, ["agy", "--continue"])

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
            command_args=["agy", "-i", "Hello"],
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
            command_args=["agy", "-i", "Fix"],
            title="fix",
            dispatch_mode="split-v",
            target_window="101",
            dry_run=True,
        )
        self.assertIn("--location=vsplit", res_v["command"])
        self.assertIn("--match id:101", res_v["command"])

        res_h = dispatch_agent.dispatch_to_kitty(
            command_args=["agy", "-i", "Fix"],
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
            command_args=["agy", "-i", "test"],
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
                command_args=["agy", "-i", "test"],
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

    # --- socket resolution -------------------------------------------------

    def test_dispatch_omits_to_flag_without_socket(self) -> None:
        """Sends no --to when neither argument nor environment supplies one."""
        res = dispatch_agent.dispatch_to_kitty(
            command_args=["agy"], title="t", dry_run=True
        )
        self.assertNotIn("--to", res["command"])

    def test_dispatch_uses_socket_argument(self) -> None:
        """Explicit socket argument becomes --to."""
        res = dispatch_agent.dispatch_to_kitty(
            command_args=["agy"],
            title="t",
            dry_run=True,
            socket="unix:/run/user/1000/kitty-1",
        )
        self.assertIn("--to unix:/run/user/1000/kitty-1", res["command"])

    def test_dispatch_falls_back_to_listen_on_env(self) -> None:
        """Falls back to $KITTY_LISTEN_ON when no socket is given."""
        with mock.patch.dict(os.environ, {"KITTY_LISTEN_ON": "unix:/tmp/env-sock"}):
            res = dispatch_agent.dispatch_to_kitty(
                command_args=["agy"], title="t", dry_run=True
            )
        self.assertIn("--to unix:/tmp/env-sock", res["command"])

    def test_socket_argument_wins_over_environment(self) -> None:
        """An explicit socket takes precedence over the inherited one."""
        with mock.patch.dict(os.environ, {"KITTY_LISTEN_ON": "unix:/tmp/env-sock"}):
            res = dispatch_agent.dispatch_to_kitty(
                command_args=["agy"],
                title="t",
                dry_run=True,
                socket="unix:/tmp/explicit",
            )
        self.assertIn("--to unix:/tmp/explicit", res["command"])
        self.assertNotIn("env-sock", res["command"])

    # --- target window validation -----------------------------------------

    def test_resolve_match_expression_accepts_plain_and_prefixed_ids(self) -> None:
        """Normalizes both '14' and 'id:14' to a narrow match."""
        self.assertEqual(dispatch_agent.resolve_match_expression("14"), "id:14")
        self.assertEqual(dispatch_agent.resolve_match_expression("id:14"), "id:14")
        self.assertEqual(dispatch_agent.resolve_match_expression(" 14 "), "id:14")

    def test_resolve_match_expression_rejects_widening(self) -> None:
        """Rejects anchors that would broaden the match beyond one window."""
        for hostile in (
            "1 or title:.*",
            "all",
            "id:all",
            "title:.*",
            "recent:0",
            "-1",
            "",
        ):
            with self.subTest(target=hostile):
                with self.assertRaises(ValueError):
                    dispatch_agent.resolve_match_expression(hostile)

    def test_dispatch_rejects_hostile_target_window(self) -> None:
        """A widening anchor fails the dispatch rather than matching broadly."""
        with self.assertRaises(ValueError):
            dispatch_agent.dispatch_to_kitty(
                command_args=["agy"],
                title="t",
                dispatch_mode="split-v",
                target_window="1 or title:.*",
                dry_run=True,
            )

    # --- remaining dispatch surfaces --------------------------------------

    def test_dispatch_overlay_mode(self) -> None:
        """Builds an anchored overlay launch."""
        res = dispatch_agent.dispatch_to_kitty(
            command_args=["agy"],
            title="ov",
            dispatch_mode="overlay",
            target_window="7",
            dry_run=True,
        )
        self.assertIn("--type=overlay", res["command"])
        self.assertIn("--title=ov", res["command"])
        self.assertIn("--match id:7", res["command"])

    def test_dispatch_os_window_mode_is_not_anchored(self) -> None:
        """os-window ignores the anchor, which does not apply to a new window."""
        res = dispatch_agent.dispatch_to_kitty(
            command_args=["agy"],
            title="worker",
            dispatch_mode="os-window",
            target_window="7",
            dry_run=True,
        )
        self.assertIn("--type=os-window", res["command"])
        self.assertIn("--title=worker", res["command"])
        self.assertNotIn("--match", res["command"])

    def test_dispatch_rejects_unknown_mode(self) -> None:
        """Raises on an unrecognized dispatch surface."""
        with self.assertRaises(ValueError):
            dispatch_agent.dispatch_to_kitty(
                command_args=["agy"], title="t", dispatch_mode="teleport", dry_run=True
            )

    def test_dispatch_rejects_empty_command(self) -> None:
        """Refuses to launch with no program to run."""
        with self.assertRaises(ValueError):
            dispatch_agent.dispatch_to_kitty(command_args=[], title="t", dry_run=True)

    def test_dispatch_keeps_focus_unless_detached_is_false(self) -> None:
        """--keep-focus is present only when detached."""
        attached = dispatch_agent.dispatch_to_kitty(
            command_args=["agy"], title="t", dry_run=True, detached=False
        )
        self.assertNotIn("--keep-focus", attached["command"])

    # --- conversation parsing ---------------------------------------------

    @mock.patch("dispatch_agent.run_command_safely")
    def test_create_api_conversation_camel_case_and_id(
        self, mock_run: mock.MagicMock
    ) -> None:
        """Accepts each documented ID field name."""
        mock_run.return_value = (0, '{"conversationId": "camel-1"}', "")
        self.assertEqual(dispatch_agent.create_api_conversation(prompt="p"), "camel-1")
        mock_run.return_value = (0, '{"id": "plain-1"}', "")
        self.assertEqual(dispatch_agent.create_api_conversation(prompt="p"), "plain-1")

    @mock.patch("dispatch_agent.run_command_safely")
    def test_create_api_conversation_bare_id_line(
        self, mock_run: mock.MagicMock
    ) -> None:
        """Falls back to the first line when output is not JSON."""
        mock_run.return_value = (0, "bare-id-789\nnoise", "")
        self.assertEqual(
            dispatch_agent.create_api_conversation(prompt="p"), "bare-id-789"
        )

    @mock.patch("dispatch_agent.run_command_safely")
    def test_create_api_conversation_rejects_non_object_json(
        self, mock_run: mock.MagicMock
    ) -> None:
        """Does not pass non-object JSON off as a conversation ID."""
        for payload in ("[1, 2, 3]", "42", '"just-a-string"'):
            with self.subTest(payload=payload):
                mock_run.return_value = (0, payload, "")
                with mock.patch("sys.stderr", new_callable=io.StringIO):
                    self.assertIsNone(
                        dispatch_agent.create_api_conversation(prompt="p")
                    )

    @mock.patch("dispatch_agent.run_command_safely")
    def test_create_api_conversation_rejects_object_without_id(
        self, mock_run: mock.MagicMock
    ) -> None:
        """Returns None when the object carries no recognizable ID."""
        mock_run.return_value = (0, '{"status": "queued"}', "")
        with mock.patch("sys.stderr", new_callable=io.StringIO):
            self.assertIsNone(dispatch_agent.create_api_conversation(prompt="p"))

    # --- main() wiring -----------------------------------------------------

    def test_main_rejects_prompt_with_resume_flags(self) -> None:
        """A prompt alongside a resume flag is an error, not a silent drop."""
        for resume in ("--continue", "--conversation=abc123"):
            with self.subTest(resume=resume):
                with mock.patch("sys.stderr", new_callable=io.StringIO) as err:
                    code = dispatch_agent.main(["--prompt=x", resume, "--dry-run"])
                self.assertEqual(code, 1)
                self.assertIn("cannot be combined", err.getvalue())

    def test_main_rejects_profile_without_api_method(self) -> None:
        """--profile only applies to the agentapi path."""
        with mock.patch("sys.stderr", new_callable=io.StringIO) as err:
            code = dispatch_agent.main(["--prompt=x", "--profile=audit", "--dry-run"])
        self.assertEqual(code, 1)
        self.assertIn("--profile requires --method=api", err.getvalue())

    def test_main_api_dry_run_keeps_command_shape(self) -> None:
        """An api dry run previews a conversation launch, not a bare agy."""
        with mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            code = dispatch_agent.main(
                ["--method=api", "--prompt=hello", "--dry-run", "--json"]
            )
        self.assertEqual(code, 0)
        data = json.loads(out.getvalue())
        self.assertIn("--conversation", data["inner_command"])
        self.assertIn("conversation_id", data)

    @mock.patch("dispatch_agent.create_api_conversation")
    def test_main_api_mode_does_not_repeat_model(
        self, mock_create: mock.MagicMock
    ) -> None:
        """Model is bound at conversation creation, not again on the agy side."""
        mock_create.return_value = "conv-xyz"
        with (
            mock.patch("dispatch_agent.run_command_safely", return_value=(0, "9", "")),
            mock.patch("sys.stdout", new_callable=io.StringIO) as out,
        ):
            code = dispatch_agent.main(
                ["--method=api", "--prompt=hello", "--model=pro", "--json"]
            )
        self.assertEqual(code, 0)
        self.assertEqual(mock_create.call_args.kwargs["model"], "pro")
        self.assertEqual(json.loads(out.getvalue())["conversation_id"], "conv-xyz")

    def test_main_uses_kitty_window_id_as_default_anchor(self) -> None:
        """Split modes anchor to $KITTY_WINDOW_ID when no target is given."""
        with mock.patch.dict(os.environ, {"KITTY_WINDOW_ID": "33"}):
            with mock.patch("sys.stdout", new_callable=io.StringIO) as out:
                code = dispatch_agent.main(
                    ["--prompt=x", "--mode=split-v", "--dry-run", "--json"]
                )
        self.assertEqual(code, 0)
        self.assertIn("--match id:33", json.loads(out.getvalue())["command"])

    def test_main_reports_invalid_target_window(self) -> None:
        """A rejected anchor surfaces as a dispatch error, not a traceback."""
        with mock.patch("sys.stderr", new_callable=io.StringIO) as err:
            code = dispatch_agent.main(
                ["--prompt=x", "--mode=split-v", "--target-window=all", "--dry-run"]
            )
        self.assertEqual(code, 1)
        self.assertIn("Dispatch error", err.getvalue())


if __name__ == "__main__":
    unittest.main()
