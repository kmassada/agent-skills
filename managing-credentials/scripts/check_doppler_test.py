#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Companion unit tests for check_doppler utility."""

import json
import subprocess
import unittest
from unittest.mock import MagicMock, patch

from check_doppler import (
    check_auth_status,
    get_project_config,
    is_doppler_installed,
    list_secret_keys,
    main,
    run_doppler_command,
    verify_setup,
)


class TestCheckDoppler(unittest.TestCase):
    """Hermetic unit tests for Doppler verification functions."""

    @patch("shutil.which")
    def test_is_doppler_installed_true(self, mock_which: MagicMock) -> None:
        mock_which.return_value = "/opt/homebrew/bin/doppler"
        self.assertTrue(is_doppler_installed())
        mock_which.assert_called_once_with("doppler")

    @patch("shutil.which")
    def test_is_doppler_installed_false(self, mock_which: MagicMock) -> None:
        mock_which.return_value = None
        self.assertFalse(is_doppler_installed())

    @patch("subprocess.run")
    def test_run_doppler_command(self, mock_run: MagicMock) -> None:
        mock_proc = subprocess.CompletedProcess(
            args=["doppler", "me"],
            returncode=0,
            stdout="user@example.com",
            stderr="",
        )
        mock_run.return_value = mock_proc
        res = run_doppler_command(["me"])
        self.assertEqual(res.returncode, 0)
        self.assertEqual(res.stdout, "user@example.com")
        mock_run.assert_called_once_with(
            ["doppler", "me"],
            capture_output=True,
            text=True,
            check=False,
        )

    @patch("check_doppler.run_doppler_command")
    def test_check_auth_status_success(self, mock_cmd: MagicMock) -> None:
        mock_cmd.return_value = subprocess.CompletedProcess(
            args=["doppler", "me", "--json"], returncode=0, stdout="{}", stderr=""
        )
        self.assertTrue(check_auth_status())

    @patch("check_doppler.run_doppler_command")
    def test_check_auth_status_failure(self, mock_cmd: MagicMock) -> None:
        mock_cmd.return_value = subprocess.CompletedProcess(
            args=["doppler", "me", "--json"],
            returncode=1,
            stdout="",
            stderr="Unauthorized",
        )
        self.assertFalse(check_auth_status())

    @patch("check_doppler.run_doppler_command")
    def test_get_project_config_success(self, mock_cmd: MagicMock) -> None:
        payload = {"project": "ai-agents", "config": "dev"}
        mock_cmd.return_value = subprocess.CompletedProcess(
            args=["doppler", "configure", "get", "--json"],
            returncode=0,
            stdout=json.dumps(payload),
            stderr="",
        )
        config = get_project_config()
        self.assertEqual(config.get("project"), "ai-agents")
        self.assertEqual(config.get("config"), "dev")

    @patch("check_doppler.run_doppler_command")
    def test_get_project_config_invalid_json(self, mock_cmd: MagicMock) -> None:
        mock_cmd.return_value = subprocess.CompletedProcess(
            args=["doppler", "configure", "get", "--json"],
            returncode=0,
            stdout="invalid-json",
            stderr="",
        )
        self.assertEqual(get_project_config(), {})

    @patch("check_doppler.run_doppler_command")
    def test_list_secret_keys_success(self, mock_cmd: MagicMock) -> None:
        mock_cmd.return_value = subprocess.CompletedProcess(
            args=["doppler", "secrets", "--names", "--json"],
            returncode=0,
            stdout=json.dumps(["SLACK_BOT_TOKEN", "SLACK_TEAM_ID"]),
            stderr="",
        )
        keys = list_secret_keys()
        self.assertEqual(keys, ["SLACK_BOT_TOKEN", "SLACK_TEAM_ID"])

    @patch("check_doppler.is_doppler_installed", return_value=False)
    def test_verify_setup_not_installed(self, _mock_inst: MagicMock) -> None:
        passed, msgs = verify_setup()
        self.assertFalse(passed)
        self.assertTrue(any("not installed" in m for m in msgs))

    @patch("check_doppler.check_auth_status", return_value=False)
    @patch("check_doppler.is_doppler_installed", return_value=True)
    def test_verify_setup_not_logged_in(
        self, _mock_inst: MagicMock, _mock_auth: MagicMock
    ) -> None:
        passed, msgs = verify_setup()
        self.assertFalse(passed)
        self.assertTrue(any("not logged in" in m for m in msgs))

    @patch("check_doppler.get_project_config", return_value={})
    @patch("check_doppler.check_auth_status", return_value=True)
    @patch("check_doppler.is_doppler_installed", return_value=True)
    def test_verify_setup_no_config(
        self, _mock_inst: MagicMock, _mock_auth: MagicMock, _mock_cfg: MagicMock
    ) -> None:
        passed, msgs = verify_setup()
        self.assertFalse(passed)
        self.assertTrue(any("No project/config" in m for m in msgs))

    @patch("check_doppler.list_secret_keys", return_value=["SLACK_BOT_TOKEN"])
    @patch(
        "check_doppler.get_project_config",
        return_value={"project": "ai-agents", "config": "dev"},
    )
    @patch("check_doppler.check_auth_status", return_value=True)
    @patch("check_doppler.is_doppler_installed", return_value=True)
    def test_verify_setup_missing_required_key(
        self,
        _mock_inst: MagicMock,
        _mock_auth: MagicMock,
        _mock_cfg: MagicMock,
        _mock_keys: MagicMock,
    ) -> None:
        passed, msgs = verify_setup(required_keys=["SLACK_BOT_TOKEN", "MISSING_KEY"])
        self.assertFalse(passed)
        self.assertTrue(any("Missing required secrets" in m for m in msgs))

    @patch(
        "check_doppler.list_secret_keys",
        return_value=["SLACK_BOT_TOKEN", "SLACK_TEAM_ID"],
    )
    @patch(
        "check_doppler.get_project_config",
        return_value={"project": "ai-agents", "config": "dev"},
    )
    @patch("check_doppler.check_auth_status", return_value=True)
    @patch("check_doppler.is_doppler_installed", return_value=True)
    def test_verify_setup_success(
        self,
        _mock_inst: MagicMock,
        _mock_auth: MagicMock,
        _mock_cfg: MagicMock,
        _mock_keys: MagicMock,
    ) -> None:
        passed, msgs = verify_setup(required_keys=["SLACK_BOT_TOKEN", "SLACK_TEAM_ID"])
        self.assertTrue(passed)
        self.assertTrue(any("All 2 required secret" in m for m in msgs))

    @patch("builtins.print")
    @patch("check_doppler.verify_setup", return_value=(True, ["OK"]))
    def test_main_success(self, mock_verify: MagicMock, _mock_print: MagicMock) -> None:
        code = main(["--require", "SLACK_BOT_TOKEN"])
        self.assertEqual(code, 0)
        mock_verify.assert_called_once_with(required_keys=["SLACK_BOT_TOKEN"])

    @patch("builtins.print")
    @patch("check_doppler.verify_setup", return_value=(False, ["ERROR"]))
    def test_main_failure(
        self, _mock_verify: MagicMock, _mock_print: MagicMock
    ) -> None:
        code = main([])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
