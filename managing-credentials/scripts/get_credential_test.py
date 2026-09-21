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
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

import get_credential
from get_credential import (
    extract_json_field,
    is_bootstrap_entry,
    list_secrets,
    main,
    normalize_pass_payload,
    purge_source_file,
    resolve_all_secrets,
    resolve_from_bitwarden,
    resolve_from_doppler,
    resolve_from_gcp,
    resolve_from_pass,
    resolve_secret,
    run_command_with_injected_secrets,
    safe_inject,
    save_secret,
    save_to_pass,
    sync_to_doppler,
)


class TestGetCredential(unittest.TestCase):
    """Hermetic unit tests for multi-backend credential resolver."""

    def setUp(self) -> None:
        """Isolates every test from the developer's real environment and files.

        Two escape hatches exist otherwise: `_load_bw_key_file` mutates
        `os.environ` in place (leaking state into later tests), and it reads
        `~/.local/bw_key.zsh` from the real home directory.
        """
        env_patch = mock.patch.dict(os.environ, {}, clear=True)
        env_patch.start()
        self.addCleanup(env_patch.stop)

        self._tmp_home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self._tmp_home, ignore_errors=True)
        key_patch = mock.patch.object(
            get_credential,
            "BW_KEY_FILE_PATH",
            os.path.join(self._tmp_home, "absent_bw_key.zsh"),
        )
        key_patch.start()
        self.addCleanup(key_patch.stop)

        # The CLI writes progress lines to stdout; keep test output readable.
        out_patch = mock.patch("sys.stdout", new_callable=io.StringIO)
        self.stdout = out_patch.start()
        self.addCleanup(out_patch.stop)

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
                mock_out.getvalue().strip(), "export MY_KEY=my_resolved_val"
            )

    @mock.patch(
        "get_credential.resolve_secret", return_value='a"b$(whoami)`id` ;rm -rf .'
    )
    def test_main_get_export_quotes_hostile_value(
        self, mock_resolve: mock.MagicMock
    ) -> None:
        """A secret containing shell metacharacters must not execute on eval."""
        with mock.patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            code = main(["get", "MY_KEY", "--format", "export"])
        self.assertEqual(code, 0)
        line = mock_out.getvalue().strip()
        self.assertEqual(line, """export MY_KEY='a"b$(whoami)`id` ;rm -rf .'""")
        # Round-trip through a real shell: the value must survive verbatim.
        echoed = subprocess.run(
            ["/bin/sh", "-c", f'{line}; printf "%s" "$MY_KEY"'],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(echoed.stdout, 'a"b$(whoami)`id` ;rm -rf .')

    @mock.patch("get_credential.resolve_secret", return_value="tok")
    def test_main_get_export_normalizes_store_path(
        self, mock_resolve: mock.MagicMock
    ) -> None:
        """Store paths are not shell identifiers and must be rendered as such."""
        with mock.patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            main(["get", "slack/bot_token", "--format", "export"])
        self.assertEqual(mock_out.getvalue().strip(), "export SLACK_BOT_TOKEN=tok")

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

    @mock.patch("getpass.getpass", return_value="hidden_secret_val")
    @mock.patch("sys.stdin.isatty", return_value=True)
    @mock.patch("get_credential.save_secret", return_value=True)
    def test_main_set_hidden_prompt(
        self,
        mock_save: mock.MagicMock,
        mock_isatty: mock.MagicMock,
        mock_getpass: mock.MagicMock,
    ) -> None:
        code = main(["set", "slack/bot_token", "--provider", "pass"])
        self.assertEqual(code, 0)
        mock_getpass.assert_called_once()
        mock_save.assert_called_once()
        self.assertEqual(mock_save.call_args[1]["value"], "hidden_secret_val")

    @mock.patch("sys.stdin.isatty", return_value=False)
    @mock.patch("sys.stdin.read", return_value="piped_secret_val\n")
    @mock.patch("get_credential.save_secret", return_value=True)
    def test_main_set_piped_stdin(
        self,
        mock_save: mock.MagicMock,
        mock_read: mock.MagicMock,
        mock_isatty: mock.MagicMock,
    ) -> None:
        code = main(["set", "slack/bot_token", "--provider", "pass"])
        self.assertEqual(code, 0)
        mock_read.assert_called_once()
        mock_save.assert_called_once()
        self.assertEqual(mock_save.call_args[1]["value"], "piped_secret_val")

    # --- Payload integrity ---------------------------------------------------

    def test_normalize_pass_payload_preserves_multiline(self) -> None:
        pem = "-----BEGIN KEY-----\nMIIB\nAgEA\n-----END KEY-----\n"
        self.assertEqual(normalize_pass_payload(pem), pem.rstrip("\n"))
        self.assertEqual(normalize_pass_payload("  token  \n"), "token")

    @mock.patch("shutil.which", return_value="/usr/local/bin/pass")
    @mock.patch("subprocess.run")
    def test_resolve_from_pass_returns_full_pem(
        self, mock_run: mock.MagicMock, mock_which: mock.MagicMock
    ) -> None:
        """Multi-line secrets must not be truncated to their first line."""
        pem = "-----BEGIN PRIVATE KEY-----\nLINE2\nLINE3\n-----END PRIVATE KEY-----\n"
        mock_run.return_value = mock.MagicMock(returncode=0, stdout=pem)
        self.assertEqual(resolve_from_pass("svc/key"), pem.rstrip("\n"))

    @mock.patch("shutil.which", return_value="/usr/local/bin/pass")
    @mock.patch("subprocess.run")
    def test_resolve_from_pass_json_blob_not_truncated(
        self, mock_run: mock.MagicMock, mock_which: mock.MagicMock
    ) -> None:
        """A pretty-printed JSON secret must not collapse to '{'."""
        blob = json.dumps({"client_id": "cid", "client_secret": "csec"}, indent=2)
        mock_run.return_value = mock.MagicMock(returncode=0, stdout=blob)
        self.assertEqual(resolve_from_pass("gws"), blob)

    @mock.patch("shutil.which", return_value="/usr/local/bin/pass")
    @mock.patch("subprocess.run")
    def test_resolve_from_pass_dot_path_reads_json_field(
        self, mock_run: mock.MagicMock, mock_which: mock.MagicMock
    ) -> None:
        blob = json.dumps({"client_id": "cid"}, indent=2)
        mock_run.return_value = mock.MagicMock(returncode=0, stdout=blob)
        self.assertEqual(resolve_from_pass("gws.client_id"), "cid")

    def test_extract_json_field(self) -> None:
        blob = json.dumps({"Client_ID": "cid"})
        self.assertEqual(extract_json_field(blob, "client_id"), "cid")
        self.assertIsNone(extract_json_field(blob, "missing"))
        self.assertIsNone(extract_json_field("not json", "client_id"))

    # --- Injection scope and blast radius ------------------------------------

    def test_is_bootstrap_entry(self) -> None:
        self.assertTrue(is_bootstrap_entry("bitwarden/access_token"))
        self.assertTrue(is_bootstrap_entry("bws/token"))
        self.assertFalse(is_bootstrap_entry("slack/bot_token"))

    @mock.patch("shutil.which", return_value="/usr/local/bin/pass")
    @mock.patch("subprocess.run")
    @mock.patch("os.walk")
    @mock.patch("os.path.exists", return_value=True)
    def test_resolve_all_secrets_pass_excludes_bootstrap_token(
        self,
        mock_exists: mock.MagicMock,
        mock_walk: mock.MagicMock,
        mock_run: mock.MagicMock,
        mock_which: mock.MagicMock,
    ) -> None:
        """`cred run` must never hand the upstream vault key to a child process."""
        store = os.path.expanduser("~/.password-store")
        mock_walk.return_value = [
            (os.path.join(store, "ai-agents", "bitwarden"), [], ["access_token.gpg"]),
            (os.path.join(store, "ai-agents", "slack"), [], ["bot_token.gpg"]),
        ]
        mock_run.return_value = mock.MagicMock(returncode=0, stdout="xoxb-1\n")

        res = resolve_all_secrets(provider="pass")

        self.assertEqual(res["SLACK_BOT_TOKEN"], "xoxb-1")
        self.assertNotIn("BITWARDEN_ACCESS_TOKEN", res)
        # The bootstrap entry is skipped before it is ever decrypted.
        self.assertEqual(mock_run.call_count, 1)

    def test_safe_inject_refuses_reserved_names(self) -> None:
        target: dict[str, str] = {}
        with mock.patch("sys.stderr", new_callable=io.StringIO):
            safe_inject(target, "PATH", "/evil/bin")
            safe_inject(target, "home", "/tmp/evil")
            safe_inject(target, "SLACK_BOT_TOKEN", "xoxb-1")
        self.assertEqual(target, {"SLACK_BOT_TOKEN": "xoxb-1"})

    @mock.patch("subprocess.run")
    def test_run_command_refuses_reserved_env_override(
        self, mock_run: mock.MagicMock
    ) -> None:
        """An explicit --keys mapping must not be able to hijack the child."""
        mock_run.return_value = mock.MagicMock(returncode=0)
        with mock.patch.dict(os.environ, {"PATH": "/usr/bin"}, clear=True):
            with mock.patch("sys.stderr", new_callable=io.StringIO):
                run_command_with_injected_secrets(
                    ["agy"], {"PATH": "/evil/bin", "SLACK_BOT_TOKEN": "xoxb-1"}
                )
        env = mock_run.call_args[1]["env"]
        self.assertEqual(env["PATH"], "/usr/bin")
        self.assertEqual(env["SLACK_BOT_TOKEN"], "xoxb-1")

    def test_load_bw_key_file_ignores_non_bootstrap_keys(self) -> None:
        """The legacy shell file must not be able to redefine PATH."""
        key_file = os.path.join(self._tmp_home, "bw_key.zsh")
        with open(key_file, "w", encoding="utf-8") as handle:
            handle.write("export BWS_ACCESS_TOKEN=tok-1\nexport PATH=/evil/bin\n")

        with (
            mock.patch.object(get_credential, "BW_KEY_FILE_PATH", key_file),
            mock.patch("shutil.which", return_value=None),
        ):
            get_credential._load_bw_key_file()

        self.assertEqual(os.environ.get("BWS_ACCESS_TOKEN"), "tok-1")
        self.assertNotIn("PATH", os.environ)

    # --- Source-file lifecycle -----------------------------------------------

    def test_purge_source_file_overwrites_and_removes(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, dir=self._tmp_home
        ) as tmp:
            tmp.write("super-secret-token")
            path = tmp.name
        self.assertTrue(purge_source_file(path))
        self.assertFalse(os.path.exists(path))

    @mock.patch("shutil.which", return_value="/usr/local/bin/bws")
    @mock.patch.dict(
        os.environ, {"BWS_ACCESS_TOKEN": "token", "BWS_PROJECT_ID": "proj-1"}
    )
    @mock.patch("subprocess.run")
    def test_delete_after_retains_source_when_vault_write_fails(
        self, mock_run: mock.MagicMock, mock_which: mock.MagicMock
    ) -> None:
        """A failed upstream write must not destroy the only copy of the secret."""
        mock_run.return_value = mock.MagicMock(
            returncode=1, stdout="", stderr="auth failed"
        )
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".json", dir=self._tmp_home
        ) as tmp:
            tmp.write(json.dumps({"installed": {"client_id": "cid"}}))
            path = tmp.name

        ok = save_secret(
            "gws_auth", provider="bitwarden", from_file=path, delete_after=True
        )

        self.assertFalse(ok)
        self.assertTrue(os.path.exists(path))

    @mock.patch("shutil.which", return_value="/usr/local/bin/bws")
    @mock.patch.dict(
        os.environ, {"BWS_ACCESS_TOKEN": "token", "BWS_PROJECT_ID": "proj-1"}
    )
    @mock.patch("subprocess.run")
    def test_delete_after_purges_source_on_success(
        self, mock_run: mock.MagicMock, mock_which: mock.MagicMock
    ) -> None:
        mock_run.side_effect = [
            mock.MagicMock(returncode=0, stdout="[]"),
            mock.MagicMock(returncode=0, stdout=""),
        ]
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".json", dir=self._tmp_home
        ) as tmp:
            tmp.write(json.dumps({"installed": {"client_id": "cid"}}))
            path = tmp.name

        ok = save_secret(
            "gws_auth", provider="bitwarden", from_file=path, delete_after=True
        )

        self.assertTrue(ok)
        self.assertFalse(os.path.exists(path))

    # --- Sync result reporting -----------------------------------------------

    @mock.patch("get_credential.resolve_secret", return_value="xoxb-secret")
    @mock.patch("get_credential.save_to_pass", return_value=False)
    def test_main_sync_reports_failure_when_writes_fail(
        self, mock_save: mock.MagicMock, mock_resolve: mock.MagicMock
    ) -> None:
        """A sync whose destination writes all failed must not report success."""
        with mock.patch("sys.stderr", new_callable=io.StringIO) as err:
            code = main(
                [
                    "sync",
                    "--upstream",
                    "bitwarden",
                    "--dest",
                    "pass",
                    "--keys",
                    "slack_bot_token",
                ]
            )
        self.assertEqual(code, 1)
        self.assertIn("failed", err.getvalue())
        self.assertNotIn("Successfully synced", self.stdout.getvalue())

    @mock.patch("get_credential.resolve_secret", return_value="xoxb-secret")
    @mock.patch("get_credential.save_to_pass", return_value=True)
    def test_main_sync_reports_success_when_writes_succeed(
        self, mock_save: mock.MagicMock, mock_resolve: mock.MagicMock
    ) -> None:
        code = main(
            [
                "sync",
                "--upstream",
                "bitwarden",
                "--dest",
                "pass",
                "--keys",
                "slack_bot_token",
            ]
        )
        self.assertEqual(code, 0)
        self.assertIn("Successfully synced", self.stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
