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
import unittest
from unittest import mock

from get_credential import (
    main,
    resolve_from_bitwarden,
    resolve_from_doppler,
    resolve_from_gcp,
    resolve_secret,
    run_command_with_injected_secrets,
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
            returncode=0, stdout=json.dumps({"value": "secret_bws_val"})
        )
        val = resolve_from_bitwarden("MY_SECRET")
        self.assertEqual(val, "secret_bws_val")
        mock_run.assert_called_once_with(
            ["bws", "secret", "get", "MY_SECRET"],
            capture_output=True,
            text=True,
            check=False,
        )

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
    def test_main_sync(
        self, mock_sync: mock.MagicMock, mock_resolve: mock.MagicMock
    ) -> None:
        code = main(["sync", "--upstream", "gcp", "--keys", "KEY1,KEY2"])
        self.assertEqual(code, 0)
        self.assertEqual(
            mock_sync.call_args[0][0], {"KEY1": "synced_val", "KEY2": "synced_val"}
        )


if __name__ == "__main__":
    unittest.main()
