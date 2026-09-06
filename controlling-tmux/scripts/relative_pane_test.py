#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Unit tests for relative_pane.py helper script using standard library unittest."""

import io
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

# Ensure script directory is on sys.path for direct or module execution
sys.path.insert(0, str(Path(__file__).resolve().parent))

from relative_pane import find_target_pane, get_current_pane_id, list_panes, main


class RelativePaneTest(unittest.TestCase):
    """Tests for finding relative target panes based on geometry."""

    def setUp(self) -> None:
        super().setUp()
        # 2x2 grid layout simulation:
        # %0: (left:0, top:0, right:50, bottom:25)  [top-left]
        # %1: (left:51, top:0, right:100, bottom:25) [top-right]
        # %2: (left:0, top:26, right:50, bottom:50)  [bottom-left]
        # %3: (left:51, top:26, right:100, bottom:50) [bottom-right]
        self.panes = [
            {"id": "%0", "left": 0, "top": 0, "right": 50, "bottom": 25},
            {"id": "%1", "left": 51, "top": 0, "right": 100, "bottom": 25},
            {"id": "%2", "left": 0, "top": 26, "right": 50, "bottom": 50},
            {"id": "%3", "left": 51, "top": 26, "right": 100, "bottom": 50},
        ]

    def test_find_target_right(self) -> None:
        """Should resolve adjacent pane to the right."""
        target = find_target_pane(self.panes, "%0", "right")
        self.assertEqual(target, "%1")

    def test_find_target_left(self) -> None:
        """Should resolve adjacent pane to the left."""
        target = find_target_pane(self.panes, "%1", "left")
        self.assertEqual(target, "%0")

    def test_find_target_under(self) -> None:
        """Should resolve adjacent pane below."""
        target = find_target_pane(self.panes, "%0", "under")
        self.assertEqual(target, "%2")

    def test_find_target_above(self) -> None:
        """Should resolve adjacent pane above."""
        target = find_target_pane(self.panes, "%2", "above")
        self.assertEqual(target, "%0")

    def test_no_target_out_of_bounds(self) -> None:
        """Should return None when no pane exists above top boundary."""
        target = find_target_pane(self.panes, "%0", "above")
        self.assertIsNone(target)

    def test_unknown_origin_id_returns_none(self) -> None:
        """Should return None when origin ID is not in panes list."""
        target = find_target_pane(self.panes, "%999", "right")
        self.assertIsNone(target)

    def test_full_width_pane_under(self) -> None:
        """Should correctly detect vertical overlap with full-width pane below."""
        # Layout: %0 and %1 side-by-side on top, %2 full width on bottom
        panes = [
            {"id": "%0", "left": 0, "top": 0, "right": 50, "bottom": 25},
            {"id": "%1", "left": 51, "top": 0, "right": 100, "bottom": 25},
            {"id": "%2", "left": 0, "top": 26, "right": 100, "bottom": 50},
        ]
        target_0 = find_target_pane(panes, "%0", "under")
        target_1 = find_target_pane(panes, "%1", "under")
        self.assertEqual(target_0, "%2")
        self.assertEqual(target_1, "%2")

    def test_origin_pane_not_found_in_layout(self) -> None:
        """Should return None when origin ID is absent from layout or layout is empty."""
        self.assertIsNone(find_target_pane(self.panes, "%999", "under"))
        self.assertIsNone(find_target_pane([], "%0", "right"))

    def test_find_target_tie_breaking_identical_distances(self) -> None:
        """Should deterministically break ties by pane ID when distances match."""
        panes = [
            {"id": "%0", "left": 0, "top": 0, "right": 50, "bottom": 50},
            {"id": "%2", "left": 51, "top": 0, "right": 100, "bottom": 50},
            {"id": "%1", "left": 51, "top": 0, "right": 100, "bottom": 50},
        ]
        target = find_target_pane(panes, "%0", "right")
        self.assertEqual(target, "%1")

    @mock.patch.dict("os.environ", {"TMUX_PANE": "%42"})
    def test_get_current_pane_id_from_env(self) -> None:
        """Should retrieve pane ID from TMUX_PANE environment variable."""
        self.assertEqual(get_current_pane_id(), "%42")

    @mock.patch.dict("os.environ", {}, clear=True)
    @mock.patch("subprocess.run")
    def test_get_current_pane_id_from_subprocess(
        self, mock_run: mock.MagicMock
    ) -> None:
        """Should query tmux display-message if TMUX_PANE is unset."""
        mock_proc = mock.create_autospec(subprocess.CompletedProcess, instance=True)
        mock_proc.stdout = "%7\n"
        mock_run.return_value = mock_proc

        self.assertEqual(get_current_pane_id(), "%7")
        mock_run.assert_called_once()

    @mock.patch.dict("os.environ", {}, clear=True)
    @mock.patch("subprocess.run")
    def test_get_current_pane_id_with_socket(self, mock_run: mock.MagicMock) -> None:
        """Should query tmux with socket flag when TMUX_PANE is unset."""
        mock_proc = mock.create_autospec(subprocess.CompletedProcess, instance=True)
        mock_proc.stdout = "%5\n"
        mock_run.return_value = mock_proc

        pane_id = get_current_pane_id(socket="custom_eval_sock")
        self.assertEqual(pane_id, "%5")
        mock_run.assert_called_once_with(
            ["tmux", "-L", "custom_eval_sock", "display-message", "-p", "#{pane_id}"],
            capture_output=True,
            text=True,
            check=True,
        )

    @mock.patch("subprocess.run")
    def test_list_panes_parsing(self, mock_run: mock.MagicMock) -> None:
        """Should parse tmux list-panes output correctly."""
        mock_proc = mock.create_autospec(subprocess.CompletedProcess, instance=True)
        mock_proc.stdout = "%0 0 0 80 24\n%1 81 0 160 24\n"
        mock_run.return_value = mock_proc

        panes = list_panes()
        self.assertEqual(len(panes), 2)
        self.assertEqual(panes[0]["id"], "%0")
        self.assertEqual(panes[1]["right"], 160)

    @mock.patch("subprocess.run")
    def test_list_panes_malformed_lines(self, mock_run: mock.MagicMock) -> None:
        """Should skip malformed geometry lines with non-integers or fewer parts."""
        mock_proc = mock.create_autospec(subprocess.CompletedProcess, instance=True)
        mock_proc.stdout = "%0 bad_coord 0 80 24\n%1 0 0 50\n%2 81 0 160 24\n"
        mock_run.return_value = mock_proc

        panes = list_panes()
        self.assertEqual(len(panes), 1)
        self.assertEqual(panes[0]["id"], "%2")

    @mock.patch("subprocess.run")
    def test_list_panes_empty_output(self, mock_run: mock.MagicMock) -> None:
        """Should return empty list when tmux list-panes output is empty."""
        mock_proc = mock.create_autospec(subprocess.CompletedProcess, instance=True)
        mock_proc.stdout = ""
        mock_run.return_value = mock_proc

        panes = list_panes()
        self.assertEqual(panes, [])

    @mock.patch.dict("os.environ", {}, clear=True)
    @mock.patch("relative_pane.get_current_pane_id", return_value=None)
    @mock.patch("sys.stderr", new_callable=io.StringIO)
    def test_main_cli_missing_origin_exits_one(
        self, mock_stderr: io.StringIO, mock_get_id: mock.MagicMock
    ) -> None:
        """Should exit 1 when origin pane ID cannot be determined."""
        with self.assertRaises(SystemExit) as cm:
            main(["--direction", "right"])
        self.assertEqual(cm.exception.code, 1)
        self.assertIn("Could not determine origin pane ID", mock_stderr.getvalue())

    @mock.patch("relative_pane.list_panes")
    @mock.patch("sys.stderr", new_callable=io.StringIO)
    def test_main_cli_target_not_found_exits_one(
        self, mock_stderr: io.StringIO, mock_list_panes: mock.MagicMock
    ) -> None:
        """Should exit 1 when no adjacent pane exists in target direction."""
        mock_list_panes.return_value = self.panes
        with self.assertRaises(SystemExit) as cm:
            main(["--direction", "above", "--pane", "%0"])
        self.assertEqual(cm.exception.code, 1)
        self.assertIn("No pane found to the above of %0", mock_stderr.getvalue())

    @mock.patch("relative_pane.list_panes")
    @mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_main_cli_success(
        self, mock_stdout: io.StringIO, mock_list_panes: mock.MagicMock
    ) -> None:
        """Should print target pane ID when navigation succeeds."""
        mock_list_panes.return_value = self.panes
        main(["--direction", "right", "--pane", "%0"])
        self.assertEqual(mock_stdout.getvalue().strip(), "%1")

    @mock.patch("subprocess.run")
    @mock.patch("relative_pane.list_panes")
    @mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_main_cli_with_select(
        self,
        mock_stdout: io.StringIO,
        mock_list_panes: mock.MagicMock,
        mock_run: mock.MagicMock,
    ) -> None:
        """Should invoke tmux select-pane when --select flag is passed."""
        mock_list_panes.return_value = self.panes
        main(["--direction", "right", "--pane", "%0", "--select"])
        mock_run.assert_called_once_with(
            ["tmux", "select-pane", "-t", "%1"], check=True
        )
        self.assertEqual(mock_stdout.getvalue().strip(), "%1")

    @mock.patch("subprocess.run")
    @mock.patch("relative_pane.list_panes")
    @mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_main_cli_with_socket(
        self,
        mock_stdout: io.StringIO,
        mock_list_panes: mock.MagicMock,
        mock_run: mock.MagicMock,
    ) -> None:
        """Should invoke tmux with -L flag when --socket is passed."""
        mock_list_panes.return_value = self.panes
        main(
            [
                "--direction",
                "right",
                "--pane",
                "%0",
                "--select",
                "--socket",
                "sock1",
            ]
        )
        mock_run.assert_called_once_with(
            ["tmux", "-L", "sock1", "select-pane", "-t", "%1"], check=True
        )
        self.assertEqual(mock_stdout.getvalue().strip(), "%1")


if __name__ == "__main__":
    unittest.main()
