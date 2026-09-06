#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "google-cloud-storage",
# ]
# ///
"""Unit tests for the snip utility script."""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add the scripts directory to sys.path to allow importing snip
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from snip import main


class TestSnip(unittest.TestCase):
    """Test suite for the sharing-snips main process."""

    @patch("snip.quota_guard.enforce_free_tier")
    @patch("snip.sys.argv", ["snip.py"])
    @patch("snip.subprocess")
    @patch("snip.os.path.isfile")
    def test_main(self, mock_isfile, mock_subprocess, mock_enforce):
        """Verify the screen capture, upload, and clipboard copying logic."""
        mock_storage = MagicMock()
        mock_client = MagicMock()
        mock_storage.Client.return_value = mock_client
        mock_client.project = "test-project"

        with patch.dict(
            "sys.modules",
            {
                "google": MagicMock(),
                "google.cloud": MagicMock(),
                "google.cloud.storage": mock_storage,
            },
        ):
            # Mock file verification to return True (screenshot taken successfully)
            mock_isfile.return_value = True

            # Execute main, ensuring it runs through successfully without raising
            try:
                main()
            except Exception as e:  # noqa: BLE001
                self.fail(f"main() raised {type(e).__name__} unexpectedly!")

            # Verify subprocess was called for screen capture
            mock_subprocess.run.assert_called_once()

            # Verify we attempt to copy to clipboard via subprocess Popen/check_output
            mock_subprocess.Popen.assert_called_once()
            mock_subprocess.check_output.assert_called_once()


if __name__ == "__main__":
    unittest.main()
