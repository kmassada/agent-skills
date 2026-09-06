#!/usr/bin/env python3
"""Unit tests for the quota_guard module."""

import datetime
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add the scripts directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import quota_guard


class TestQuotaGuard(unittest.TestCase):
    """Test suite for the local Free Tier quota protection constraints."""

    @patch("quota_guard.QUOTA_FILE")
    def test_get_quota_data_new_file(self, mock_quota_file):
        """Test retrieving quota when no file exists."""
        mock_quota_file.is_file.return_value = False

        data = quota_guard._get_quota_data()
        self.assertEqual(data["uploads"], 0)
        self.assertIn("month", data)

    @patch("quota_guard.QUOTA_FILE")
    def test_enforce_free_tier_under_limit(self, mock_quota_file):
        """Test enforcing tier under limit correctly increments."""
        mock_quota_file.is_file.return_value = True

        # Setup mock file reading
        mock_open = MagicMock()
        mock_quota_file.open.return_value.__enter__.return_value = mock_open

        now = datetime.datetime.now()
        current_month = f"{now.year}-{now.month:02d}"

        # Mock json load
        with (
            patch("quota_guard.json.load") as mock_json_load,
            patch("quota_guard.json.dump") as mock_json_dump,
        ):
            mock_json_load.return_value = {"month": current_month, "uploads": 4499}

            # Execute
            try:
                quota_guard.enforce_free_tier()
            except SystemExit:
                self.fail("enforce_free_tier raised SystemExit unexpectedly on 4499")

            # Verify the file was written back with 4500
            mock_json_dump.assert_called_once()
            written_data = mock_json_dump.call_args[0][0]
            self.assertEqual(written_data["uploads"], 4500)

    @patch("quota_guard.QUOTA_FILE")
    def test_enforce_free_tier_over_limit_blocks(self, mock_quota_file):
        """Test enforcing tier safely exits when hit limit."""
        mock_quota_file.is_file.return_value = True
        mock_open = MagicMock()
        mock_quota_file.open.return_value.__enter__.return_value = mock_open

        now = datetime.datetime.now()
        current_month = f"{now.year}-{now.month:02d}"

        with (
            patch("quota_guard.json.load") as mock_json_load,
            patch("quota_guard.sys.exit") as mock_exit,
        ):
            mock_json_load.return_value = {"month": current_month, "uploads": 4500}

            quota_guard.enforce_free_tier()

            mock_exit.assert_called_once_with(1)


if __name__ == "__main__":
    unittest.main()
