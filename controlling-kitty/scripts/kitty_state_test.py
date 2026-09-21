#!/usr/bin/env python3
"""Companion unit tests for kitty_state.py."""

import io
import json
import os
import subprocess
import unittest
from unittest import mock

import kitty_state


class TestKittyState(unittest.TestCase):
    """Unit tests for kitty_state inspection helper functions."""

    def setUp(self) -> None:
        """Set up mock hierarchy data."""
        self.sample_hierarchy = [
            {
                "id": 1,
                "is_active": True,
                "is_focused": True,
                "tabs": [
                    {
                        "id": 10,
                        "title": "work",
                        "is_active": True,
                        "is_focused": True,
                        "windows": [
                            {
                                "id": 101,
                                "title": "zsh",
                                "cwd": "/home/user/project",
                                "is_active": True,
                                "is_focused": True,
                                "pid": 1234,
                            },
                            {
                                "id": 102,
                                "title": "pytest",
                                "cwd": "/home/user/project",
                                "is_active": False,
                                "is_focused": False,
                                "pid": 1235,
                            },
                        ],
                    },
                    {
                        "id": 11,
                        "title": "server",
                        "is_active": False,
                        "is_focused": False,
                        "windows": [
                            {
                                "id": 103,
                                "title": "node",
                                "cwd": "/home/user/server",
                                "is_active": False,
                                "is_focused": False,
                                "pid": 1236,
                            }
                        ],
                    },
                ],
            }
        ]

    def test_extract_tabs(self) -> None:
        """Extracts tabs correctly across OS windows."""
        tabs = kitty_state.extract_tabs(self.sample_hierarchy)
        self.assertEqual(len(tabs), 2)
        self.assertEqual(tabs[0]["id"], 10)
        self.assertEqual(tabs[0]["os_window_id"], 1)
        self.assertEqual(tabs[1]["id"], 11)

    def test_extract_windows(self) -> None:
        """Extracts windows correctly across all tabs."""
        windows = kitty_state.extract_windows(self.sample_hierarchy)
        self.assertEqual(len(windows), 3)
        self.assertEqual(windows[0]["id"], 101)
        self.assertEqual(windows[0]["tab_id"], 10)
        self.assertEqual(windows[0]["tab_title"], "work")
        self.assertEqual(windows[2]["id"], 103)
        self.assertEqual(windows[2]["tab_id"], 11)

    def test_find_window_by_id(self) -> None:
        """Finds matching window by its ID."""
        win = kitty_state.find_window_by_id(self.sample_hierarchy, 102)
        self.assertIsNotNone(win)
        self.assertEqual(win["title"], "pytest")  # pyright: ignore

        missing = kitty_state.find_window_by_id(self.sample_hierarchy, 999)
        self.assertIsNone(missing)

    @mock.patch("kitty_state.subprocess.run")
    def test_query_kitty_ls(self, mock_run: mock.MagicMock) -> None:
        """Queries `kitty @ ls` and parses JSON output."""
        mock_run.return_value = mock.MagicMock(
            stdout=json.dumps(self.sample_hierarchy),
            returncode=0,
        )
        res = kitty_state.query_kitty_ls(socket="unix:/tmp/test")
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["id"], 1)
        mock_run.assert_called_once_with(
            ["kitty", "@", "--to", "unix:/tmp/test", "ls"],
            capture_output=True,
            text=True,
            check=True,
        )

    def test_get_current_window_id_from_env(self) -> None:
        """Returns window ID from environment variable when present."""
        with mock.patch.dict(os.environ, {"KITTY_WINDOW_ID": "42"}):
            self.assertEqual(kitty_state.get_current_window_id(), 42)

    @mock.patch("kitty_state.query_kitty_ls")
    def test_get_current_window_id_from_active_query(
        self, mock_query: mock.MagicMock
    ) -> None:
        """Infers active window ID from query when env var is missing."""
        mock_query.return_value = self.sample_hierarchy
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(kitty_state.get_current_window_id(), 101)

    @mock.patch("kitty_state.query_kitty_ls")
    def test_main_list_tabs(self, mock_query: mock.MagicMock) -> None:
        """Lists tabs via CLI."""
        mock_query.return_value = self.sample_hierarchy
        with mock.patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            exit_code = kitty_state.main(["--list-tabs"])
            self.assertEqual(exit_code, 0)
            output = mock_stdout.getvalue()
            self.assertIn("Tab 10: work", output)
            self.assertIn("Tab 11: server", output)

    @mock.patch("kitty_state.query_kitty_ls")
    def test_main_list_windows_json(self, mock_query: mock.MagicMock) -> None:
        """Lists windows in structured JSON."""
        mock_query.return_value = self.sample_hierarchy
        with mock.patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            exit_code = kitty_state.main(["--list-windows", "--json"])
            self.assertEqual(exit_code, 0)
            data = json.loads(mock_stdout.getvalue())
            self.assertEqual(len(data), 3)
            self.assertEqual(data[0]["id"], 101)

    @mock.patch("kitty_state.query_kitty_ls")
    def test_main_find_window(self, mock_query: mock.MagicMock) -> None:
        """Finds window by ID via CLI."""
        mock_query.return_value = self.sample_hierarchy
        with mock.patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            exit_code = kitty_state.main(["--find-window", "101"])
            self.assertEqual(exit_code, 0)
            data = json.loads(mock_stdout.getvalue())
            self.assertEqual(data["title"], "zsh")

    @mock.patch("kitty_state.get_current_window_id")
    def test_main_current_id(self, mock_id: mock.MagicMock) -> None:
        """Prints current ID."""
        mock_id.return_value = 101
        with mock.patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            exit_code = kitty_state.main(["--current-id"])
            self.assertEqual(exit_code, 0)
            self.assertEqual(mock_stdout.getvalue().strip(), "101")

    @mock.patch("kitty_state.query_kitty_ls")
    def test_main_error_handling(self, mock_query: mock.MagicMock) -> None:
        """Handles subprocess failure gracefully."""
        mock_query.side_effect = subprocess.SubprocessError("Socket error")
        with mock.patch("sys.stderr", new_callable=io.StringIO):
            exit_code = kitty_state.main(["--list-tabs"])
            self.assertEqual(exit_code, 1)

    def test_get_current_window_id_survives_malformed_entries(self) -> None:
        """Skips active windows lacking a usable id instead of crashing."""
        hierarchy = [
            {
                "id": 1,
                "tabs": [
                    {
                        "id": 1,
                        "windows": [
                            {"is_active": True},
                            {"id": "not-a-number", "is_active": True},
                            {"id": 55, "is_active": True},
                        ],
                    }
                ],
            }
        ]
        with (
            mock.patch("kitty_state.query_kitty_ls", return_value=hierarchy),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            self.assertEqual(kitty_state.get_current_window_id(), 55)

    def test_get_current_window_id_returns_none_when_unusable(self) -> None:
        """Returns None when no active window carries a usable id."""
        hierarchy = [{"id": 1, "tabs": [{"id": 1, "windows": [{"is_active": True}]}]}]
        with (
            mock.patch("kitty_state.query_kitty_ls", return_value=hierarchy),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            self.assertIsNone(kitty_state.get_current_window_id())

    def test_get_current_window_id_ignores_non_numeric_env(self) -> None:
        """Falls through to querying when the env var is not an integer."""
        with (
            mock.patch.dict(os.environ, {"KITTY_WINDOW_ID": "not-a-number"}),
            mock.patch(
                "kitty_state.query_kitty_ls", return_value=self.sample_hierarchy
            ),
        ):
            self.assertEqual(kitty_state.get_current_window_id(), 101)

    def test_query_kitty_ls_without_socket_omits_to_flag(self) -> None:
        """Sends no --to when no socket is configured."""
        with (
            mock.patch("kitty_state.subprocess.run") as mock_run,
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            mock_run.return_value = mock.MagicMock(stdout="[]", returncode=0)
            kitty_state.query_kitty_ls()
            self.assertEqual(mock_run.call_args.args[0], ["kitty", "@", "ls"])

    def test_query_kitty_ls_socket_argument_wins_over_env(self) -> None:
        """An explicit socket takes precedence over $KITTY_LISTEN_ON."""
        with (
            mock.patch("kitty_state.subprocess.run") as mock_run,
            mock.patch.dict(os.environ, {"KITTY_LISTEN_ON": "unix:/tmp/env"}),
        ):
            mock_run.return_value = mock.MagicMock(stdout="[]", returncode=0)
            kitty_state.query_kitty_ls(socket="unix:/tmp/explicit")
            self.assertEqual(
                mock_run.call_args.args[0],
                ["kitty", "@", "--to", "unix:/tmp/explicit", "ls"],
            )

    def test_query_kitty_ls_rejects_non_list_payload(self) -> None:
        """Returns an empty sequence when kitty returns a non-list document."""
        with mock.patch("kitty_state.subprocess.run") as mock_run:
            mock_run.return_value = mock.MagicMock(stdout='{"error": "x"}')
            self.assertEqual(list(kitty_state.query_kitty_ls()), [])

    @mock.patch("kitty_state.query_kitty_ls")
    def test_main_active_only_filters_default_listing(
        self, mock_query: mock.MagicMock
    ) -> None:
        """--active-only narrows the default hierarchy output."""
        mock_query.return_value = self.sample_hierarchy
        with mock.patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            exit_code = kitty_state.main(["--active-only"])
            output = mock_stdout.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("Win 101", output)
        self.assertNotIn("Win 102", output)
        self.assertNotIn("Win 103", output)

    @mock.patch("kitty_state.query_kitty_ls")
    def test_main_active_only_filters_windows(self, mock_query: mock.MagicMock) -> None:
        """--active-only narrows --list-windows."""
        mock_query.return_value = self.sample_hierarchy
        with mock.patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            exit_code = kitty_state.main(["--list-windows", "--json", "--active-only"])
            data = json.loads(mock_stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual([w["id"] for w in data], [101])

    @mock.patch("kitty_state.query_kitty_ls")
    def test_main_rejects_active_only_with_find_window(
        self, mock_query: mock.MagicMock
    ) -> None:
        """--active-only is refused rather than silently ignored."""
        mock_query.return_value = self.sample_hierarchy
        with mock.patch("sys.stderr", new_callable=io.StringIO) as err:
            exit_code = kitty_state.main(["--find-window", "101", "--active-only"])
        self.assertEqual(exit_code, 1)
        self.assertIn("not meaningful", err.getvalue())

    @mock.patch("kitty_state.get_current_window_id")
    def test_main_current_id_unavailable(self, mock_id: mock.MagicMock) -> None:
        """Exits non-zero when the current window ID cannot be determined."""
        mock_id.return_value = None
        with mock.patch("sys.stderr", new_callable=io.StringIO):
            self.assertEqual(kitty_state.main(["--current-id"]), 1)

    @mock.patch("kitty_state.query_kitty_ls")
    def test_main_find_window_missing(self, mock_query: mock.MagicMock) -> None:
        """Exits non-zero when the requested window does not exist."""
        mock_query.return_value = self.sample_hierarchy
        with mock.patch("sys.stderr", new_callable=io.StringIO):
            self.assertEqual(kitty_state.main(["--find-window", "999"]), 1)

    @mock.patch("kitty_state.query_kitty_ls")
    def test_main_handles_malformed_json(self, mock_query: mock.MagicMock) -> None:
        """Reports a parse failure rather than raising."""
        mock_query.side_effect = json.JSONDecodeError("bad", "", 0)
        with mock.patch("sys.stderr", new_callable=io.StringIO) as err:
            exit_code = kitty_state.main(["--list-tabs"])
        self.assertEqual(exit_code, 1)
        self.assertIn("Error parsing kitty JSON output", err.getvalue())

    @mock.patch("kitty_state.query_kitty_ls")
    def test_main_handles_missing_kitty_binary(
        self, mock_query: mock.MagicMock
    ) -> None:
        """Reports a clear error when kitty is not installed."""
        mock_query.side_effect = FileNotFoundError("kitty")
        with mock.patch("sys.stderr", new_callable=io.StringIO) as err:
            exit_code = kitty_state.main(["--list-tabs"])
        self.assertEqual(exit_code, 1)
        self.assertIn("Error querying kitty state", err.getvalue())

    def test_extract_helpers_tolerate_empty_hierarchy(self) -> None:
        """Extraction helpers return empty sequences for an empty hierarchy."""
        self.assertEqual(list(kitty_state.extract_tabs([])), [])
        self.assertEqual(list(kitty_state.extract_windows([])), [])
        self.assertEqual(list(kitty_state.extract_tabs([{"id": 1}])), [])


if __name__ == "__main__":
    unittest.main()
