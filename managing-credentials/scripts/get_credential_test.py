#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Hermetic companion unit tests for get_credential.py."""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from unittest import mock

from get_credential import (
    list_secrets,
    main,
    resolve_all_secrets,
    resolve_from_bitwarden,
    resolve_from_doppler,
    resolve_from_gcp,
    resolve_from_pass,
    resolve_secret,
    run_command_with_injected_secrets,
    save_secret,
    save_to_pass,
    sync_to_doppler,
)


class TestGetCredential(unittest.TestCase):
    """Hermetic unit tests for multi-backend credential resolver."""

    @mock.patch("shutil.which", return_value="/usr/local/bin/bws")
    @mock.patch.dict(os.environ, {"BWS_ACCESS_TOKEN": "token-123"})
    @mock.patch("subprocess.run")
    def test_resolve_from_bitwarden_bws(
        self, mock_run: mock.MagicMock, mock_which: mock.MagicMock
    ) -> None:
        mock_run.return_value = mock.MagicMock(
            returncode=0,
            stdout=json.dumps([{"key": "MY_SECRET", "value": "secret_bws_val"}]),
        )
        val = resolve_from_bitwarden("MY_SECRET")
        self.assertEqual(val, "secret_bws_val")

    @mock.patch("shutil.which", return_value="/usr/local/bin/bws")
    @mock.patch.dict(os.environ, {"BWS_ACCESS_TOKEN": "token-123"})
    @mock.patch("subprocess.run")
    def test_resolve_from_bitwarden_bws_dot_path(
        self, mock_run: mock.MagicMock, mock_which: mock.MagicMock
    ) -> None:
        payload = json.dumps({"client_id": "test-id-123", "client_secret": "test-sec"})
        mock_run.return_value = mock.MagicMock(
            returncode=0,
            stdout=json.dumps([{"key": "gws_auth", "value": payload}]),
        )
        val = resolve_from_bitwarden("gws_auth.client_id")
        self.assertEqual(val, "test-id-123")

    @mock.patch("shutil.which")
    @mock.patch("subprocess.run")
    def test_resolve_from_bitwarden_bw_password(
        self, mock_run: mock.MagicMock, mock_which: mock.MagicMock
    ) -> None:
        mock_which.side_effect = lambda cmd: (
            "/usr/local/bin/bw" if cmd == "bw" else None
        )
        mock_run.return_value = mock.MagicMock(returncode=0, stdout="secret_pass\n")
        val = resolve_from_bitwarden("MY_SECRET")
        self.assertEqual(val, "secret_pass")

    @mock.patch("shutil.which")
    @mock.patch("subprocess.run")
    def test_resolve_from_bitwarden_bw_fields(
        self, mock_run: mock.MagicMock, mock_which: mock.MagicMock
    ) -> None:
        mock_which.side_effect = lambda cmd: (
            "/usr/local/bin/bw" if cmd == "bw" else None
        )
        mock_run.side_effect = [
            mock.MagicMock(returncode=1, stdout=""),
            mock.MagicMock(
                returncode=0,
                stdout=json.dumps(
                    {"fields": [{"name": "MY_SECRET", "value": "field_secret"}]}
                ),
            ),
        ]
        val = resolve_from_bitwarden("MY_SECRET")
        self.assertEqual(val, "field_secret")

    @mock.patch("shutil.which")
    @mock.patch("subprocess.run")
    def test_resolve_from_bitwarden_bw_notes_key_val(
        self, mock_run: mock.MagicMock, mock_which: mock.MagicMock
    ) -> None:
        mock_which.side_effect = lambda cmd: (
            "/usr/local/bin/bw" if cmd == "bw" else None
        )
        mock_run.side_effect = [
            mock.MagicMock(returncode=1, stdout=""),
            mock.MagicMock(
                returncode=0,
                stdout=json.dumps(
                    {
                        "notes": "OTHER_KEY=123\nSLACK_BOT_TOKEN=xoxb-notes-token\nFOO=bar"
                    }
                ),
            ),
        ]
        val = resolve_from_bitwarden("SLACK_BOT_TOKEN", item_name="slack")
        self.assertEqual(val, "xoxb-notes-token")

    @mock.patch("shutil.which")
    @mock.patch("subprocess.run")
    def test_resolve_from_bitwarden_bw_notes_json(
        self, mock_run: mock.MagicMock, mock_which: mock.MagicMock
    ) -> None:
        mock_which.side_effect = lambda cmd: (
            "/usr/local/bin/bw" if cmd == "bw" else None
        )
        mock_run.side_effect = [
            mock.MagicMock(returncode=1, stdout=""),
            mock.MagicMock(
                returncode=0,
                stdout=json.dumps(
                    {"notes": json.dumps({"SLACK_BOT_TOKEN": "xoxb-json-notes-token"})}
                ),
            ),
        ]
        val = resolve_from_bitwarden("SLACK_BOT_TOKEN", item_name="slack")
        self.assertEqual(val, "xoxb-json-notes-token")

    @mock.patch("shutil.which", return_value="/usr/local/bin/gcloud")
    @mock.patch("subprocess.run")
    def test_resolve_from_gcp_success(
        self, mock_run: mock.MagicMock, mock_which: mock.MagicMock
    ) -> None:
        mock_run.return_value = mock.MagicMock(
            returncode=0, stdout="gcp_secret_token\n"
        )
        val = resolve_from_gcp("SLACK_BOT_TOKEN", project_id="my-work-corp")
        self.assertEqual(val, "gcp_secret_token")
        mock_run.assert_called_once_with(
            [
                "gcloud",
                "secrets",
                "versions",
                "access",
                "latest",
                "--secret=SLACK_BOT_TOKEN",
                "--project=my-work-corp",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    @mock.patch("shutil.which", return_value="/usr/local/bin/doppler")
    @mock.patch("subprocess.run")
    def test_resolve_from_doppler_success(
        self, mock_run: mock.MagicMock, mock_which: mock.MagicMock
    ) -> None:
        mock_run.return_value = mock.MagicMock(returncode=0, stdout="dop_token\n")
        val = resolve_from_doppler("SLACK_BOT_TOKEN", project="ai-agents")
        self.assertEqual(val, "dop_token")

    @mock.patch.dict(os.environ, {"ENV_SECRET": "env_val"}, clear=True)
    def test_resolve_secret_env_priority(self) -> None:
        val = resolve_secret("ENV_SECRET")
        self.assertEqual(val, "env_val")

    @mock.patch("get_credential.resolve_from_bitwarden", return_value="bw_token")
    @mock.patch.dict(os.environ, {}, clear=True)
    def test_resolve_secret_bitwarden_fallback(self, mock_bw: mock.MagicMock) -> None:
        val = resolve_secret("MISSING_IN_ENV")
        self.assertEqual(val, "bw_token")
        mock_bw.assert_called_once_with("MISSING_IN_ENV", item_name=None)

    @mock.patch("shutil.which", return_value="/usr/local/bin/doppler")
    @mock.patch("subprocess.run")
    def test_sync_to_doppler_success(
        self, mock_run: mock.MagicMock, mock_which: mock.MagicMock
    ) -> None:
        mock_run.return_value = mock.MagicMock(returncode=0)
        ok = sync_to_doppler(
            {"SLACK_BOT_TOKEN": "xoxb-123", "SLACK_TEAM_ID": "T123"},
            project="ai-agents",
        )
        self.assertTrue(ok)
        mock_run.assert_called_once_with(
            [
                "doppler",
                "secrets",
                "set",
                "--silent",
                "--project",
                "ai-agents",
                "SLACK_BOT_TOKEN=xoxb-123",
                "SLACK_TEAM_ID=T123",
            ],
            capture_output=True,
            check=False,
        )

    @mock.patch("subprocess.run")
    def test_run_command_with_injected_secrets(self, mock_run: mock.MagicMock) -> None:
        mock_run.return_value = mock.MagicMock(returncode=0)
        code = run_command_with_injected_secrets(["echo", "hello"], {"INJECTED": "val"})
        self.assertEqual(code, 0)
        self.assertEqual(mock_run.call_args[1]["env"]["INJECTED"], "val")

    @mock.patch("get_credential.resolve_secret", return_value="my_resolved_val")
    def test_main_get_plain(self, mock_resolve: mock.MagicMock) -> None:
        with mock.patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            code = main(["get", "MY_KEY"])
            self.assertEqual(code, 0)
            self.assertEqual(mock_out.getvalue().strip(), "my_resolved_val")

    @mock.patch("get_credential.resolve_secret", return_value="my_resolved_val")
    def test_main_get_export(self, mock_resolve: mock.MagicMock) -> None:
        with mock.patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            code = main(["get", "MY_KEY", "--format", "export"])
            self.assertEqual(code, 0)
            self.assertEqual(
                mock_out.getvalue().strip(), 'export MY_KEY="my_resolved_val"'
            )

    @mock.patch("get_credential.resolve_secret", return_value="synced_val")
    @mock.patch("get_credential.sync_to_doppler", return_value=True)
    def test_main_sync_doppler(
        self, mock_sync: mock.MagicMock, mock_resolve: mock.MagicMock
    ) -> None:
        code = main(
            [
                "sync",
                "--upstream",
                "gcp",
                "--dest",
                "doppler",
                "--keys",
                "KEY1,KEY2",
            ]
        )
        self.assertEqual(code, 0)
        self.assertEqual(
            mock_sync.call_args[0][0], {"KEY1": "synced_val", "KEY2": "synced_val"}
        )

    @mock.patch("shutil.which", return_value="/usr/local/bin/bws")
    @mock.patch.dict(
        os.environ, {"BWS_ACCESS_TOKEN": "token", "BWS_PROJECT_ID": "proj-1"}
    )
    @mock.patch("subprocess.run")
    def test_save_secret_bws_new(
        self, mock_run: mock.MagicMock, mock_which: mock.MagicMock
    ) -> None:
        mock_run.side_effect = [
            mock.MagicMock(returncode=0, stdout="[]"),  # list secrets
            mock.MagicMock(returncode=0, stdout=""),  # create secret
        ]
        ok = save_secret("NEW_KEY", "new_val", provider="bitwarden", note="Test note")
        self.assertTrue(ok)
        self.assertEqual(mock_run.call_count, 2)
        mock_run.assert_called_with(
            [
                "bws",
                "secret",
                "create",
                "NEW_KEY",
                "new_val",
                "proj-1",
                "--note",
                "Test note",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    @mock.patch("shutil.which", return_value="/usr/local/bin/bws")
    @mock.patch.dict(
        os.environ, {"BWS_ACCESS_TOKEN": "token", "BWS_PROJECT_ID": "proj-1"}
    )
    @mock.patch("subprocess.run")
    def test_save_secret_bws_edit(
        self, mock_run: mock.MagicMock, mock_which: mock.MagicMock
    ) -> None:
        mock_run.side_effect = [
            mock.MagicMock(
                returncode=0, stdout=json.dumps([{"id": "sec-123", "key": "MY_KEY"}])
            ),
            mock.MagicMock(returncode=0, stdout=""),
        ]
        ok = save_secret("MY_KEY", "updated_val", provider="bitwarden")
        self.assertTrue(ok)
        mock_run.assert_called_with(
            ["bws", "secret", "edit", "sec-123", "--value", "updated_val"],
            capture_output=True,
            text=True,
            check=False,
        )

    @mock.patch("shutil.which", return_value="/usr/local/bin/bws")
    @mock.patch.dict(
        os.environ, {"BWS_ACCESS_TOKEN": "token", "BWS_PROJECT_ID": "proj-1"}
    )
    @mock.patch(
        "get_credential.resolve_secret", return_value=json.dumps({"old_k": "old_v"})
    )
    @mock.patch("subprocess.run")
    def test_save_secret_dot_path(
        self,
        mock_run: mock.MagicMock,
        mock_resolve: mock.MagicMock,
        mock_which: mock.MagicMock,
    ) -> None:
        mock_run.side_effect = [
            mock.MagicMock(
                returncode=0, stdout=json.dumps([{"id": "sec-123", "key": "app_cfg"}])
            ),
            mock.MagicMock(returncode=0, stdout=""),
        ]
        ok = save_secret("app_cfg.new_k", "new_v", provider="bitwarden")
        self.assertTrue(ok)
        # Verify JSON was merged
        edit_call_args = mock_run.call_args[0][0]
        self.assertEqual(edit_call_args[0:4], ["bws", "secret", "edit", "sec-123"])
        saved_json = json.loads(edit_call_args[5])
        self.assertEqual(saved_json, {"old_k": "old_v", "new_k": "new_v"})

    @mock.patch("shutil.which", return_value="/usr/local/bin/bws")
    @mock.patch.dict(
        os.environ, {"BWS_ACCESS_TOKEN": "token", "BWS_PROJECT_ID": "proj-1"}
    )
    @mock.patch("subprocess.run")
    def test_save_secret_from_file_with_delete_after(
        self, mock_run: mock.MagicMock, mock_which: mock.MagicMock
    ) -> None:
        mock_run.side_effect = [
            mock.MagicMock(returncode=0, stdout="[]"),
            mock.MagicMock(returncode=0, stdout=""),
        ]
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as tmp:
            tmp.write(
                json.dumps(
                    {
                        "installed": {
                            "client_id": "test.id",
                            "client_secret": "test.secret",
                            "project_id": "test-proj",
                        }
                    }
                )
            )
            tmp_path = tmp.name

        try:
            ok = save_secret(
                "gws_auth", provider="bitwarden", from_file=tmp_path, delete_after=True
            )
            self.assertTrue(ok)
            self.assertFalse(os.path.exists(tmp_path))
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    @mock.patch("shutil.which", return_value="/usr/local/bin/doppler")
    @mock.patch("get_credential.sync_to_doppler", return_value=True)
    def test_save_secret_doppler_json(
        self, mock_sync: mock.MagicMock, mock_which: mock.MagicMock
    ) -> None:
        ok = save_secret(
            "slack",
            value=json.dumps({"token": "xoxb-1", "team": "T1"}),
            provider="doppler",
        )
        self.assertTrue(ok)
        mock_sync.assert_called_once_with(
            {"SLACK_TOKEN": "xoxb-1", "SLACK_TEAM": "T1"}, project=None
        )

    @mock.patch("get_credential.resolve_secret", return_value="my_val")
    @mock.patch("get_credential.sync_to_doppler", return_value=True)
    def test_main_sync_with_destination_mapping(
        self, mock_sync: mock.MagicMock, mock_resolve: mock.MagicMock
    ) -> None:
        code = main(
            [
                "sync",
                "--upstream",
                "bitwarden",
                "--dest",
                "doppler",
                "--keys",
                "MY_CUSTOM_VAR:gws_auth.client_id",
            ]
        )
        self.assertEqual(code, 0)
        mock_resolve.assert_called_once_with(
            "gws_auth.client_id", provider="bitwarden", project_id=None
        )
        mock_sync.assert_called_once_with({"MY_CUSTOM_VAR": "my_val"}, project=None)

    @mock.patch("shutil.which", return_value="/usr/local/bin/bws")
    @mock.patch.dict(
        os.environ, {"BWS_ACCESS_TOKEN": "token", "BWS_PROJECT_ID": "proj-1"}
    )
    @mock.patch("subprocess.run")
    def test_resolve_all_secrets_bws(
        self, mock_run: mock.MagicMock, mock_which: mock.MagicMock
    ) -> None:
        mock_run.side_effect = [
            mock.MagicMock(
                returncode=0,
                stdout=json.dumps(
                    [
                        {"id": "id-1", "key": "slack_agents"},
                        {"id": "id-2", "key": "gws_auth"},
                    ]
                ),
            ),
            mock.MagicMock(
                returncode=0,
                stdout=json.dumps(
                    {
                        "value": json.dumps(
                            {
                                "service": "slack",
                                "bot_token": "xoxb-999",
                                "team_id": "T999",
                            }
                        )
                    }
                ),
            ),
            mock.MagicMock(
                returncode=0,
                stdout=json.dumps(
                    {
                        "value": json.dumps(
                            {
                                "service": "google_workspace",
                                "project_id": "kmassada-gws",
                                "client_id": "client-123",
                                "client_secret": "secret-123",
                            }
                        )
                    }
                ),
            ),
        ]
        res = resolve_all_secrets(provider="bitwarden")
        self.assertEqual(res["SLACK_BOT_TOKEN"], "xoxb-999")
        self.assertEqual(res["SLACK_TEAM_ID"], "T999")
        self.assertEqual(res["GOOGLE_WORKSPACE_PROJECT_ID"], "kmassada-gws")
        self.assertEqual(res["GOOGLE_WORKSPACE_CLI_CLIENT_ID"], "client-123")
        self.assertEqual(res["GOOGLE_WORKSPACE_CLI_CLIENT_SECRET"], "secret-123")

    @mock.patch(
        "get_credential.resolve_all_secrets",
        return_value={"SLACK_BOT_TOKEN": "xoxb-1"},
    )
    @mock.patch("get_credential.run_command_with_injected_secrets", return_value=0)
    def test_main_run_default_all(
        self, mock_run_cmd: mock.MagicMock, mock_all: mock.MagicMock
    ) -> None:
        with mock.patch("os.path.exists", return_value=False):
            code = main(["run", "--", "agy"])
        self.assertEqual(code, 0)
        mock_all.assert_called_once_with(
            provider="bitwarden", prefix="ai-agents", project_id=None
        )
        mock_run_cmd.assert_called_once_with(["agy"], {"SLACK_BOT_TOKEN": "xoxb-1"})

    @mock.patch("shutil.which", return_value="/usr/local/bin/pass")
    @mock.patch("subprocess.run")
    def test_resolve_from_pass(
        self, mock_run: mock.MagicMock, mock_which: mock.MagicMock
    ) -> None:
        mock_run.return_value = mock.MagicMock(returncode=0, stdout="my_pass_secret\n")
        val = resolve_from_pass("slack/bot_token")
        self.assertEqual(val, "my_pass_secret")

    @mock.patch("shutil.which", return_value="/usr/local/bin/pass")
    @mock.patch("subprocess.run")
    def test_save_to_pass(
        self, mock_run: mock.MagicMock, mock_which: mock.MagicMock
    ) -> None:
        mock_run.return_value = mock.MagicMock(returncode=0, stdout="", stderr="")
        ok = save_to_pass("slack/bot_token", value="xoxb-test")
        self.assertTrue(ok)
        mock_run.assert_called_once_with(
            ["pass", "insert", "-m", "-f", "ai-agents/slack/bot_token"],
            input="xoxb-test",
            text=True,
            capture_output=True,
            check=False,
        )

    @mock.patch("shutil.which", return_value="/usr/local/bin/pass")
    @mock.patch("subprocess.run")
    def test_list_secrets_pass(
        self, mock_run: mock.MagicMock, mock_which: mock.MagicMock
    ) -> None:

        mock_run.return_value = mock.MagicMock(returncode=0)
        code = list_secrets(provider="pass")
        self.assertEqual(code, 0)
        mock_run.assert_called_once_with(["pass", "ls", "ai-agents"], check=False)


if __name__ == "__main__":
    unittest.main()
