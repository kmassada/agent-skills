#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Companion unit tests for managing-credentials run_eval runner."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from run_eval import (
    check_credential_expectation,
    load_dataset,
    main,
    run_static_eval,
)


class TestRunEval(unittest.TestCase):
    """Hermetic unit tests for eval runner functions."""

    def test_check_credential_expectation(self) -> None:
        text = "Run doppler projects create test-proj and doppler setup --project test-proj"
        passed, _ = check_credential_expectation(
            text, "Instructs creating a project using doppler projects create"
        )
        self.assertTrue(passed)

        passed, _ = check_credential_expectation(
            text, "Binds local directory to dev environment using doppler setup"
        )
        self.assertTrue(passed)

        passed, _ = check_credential_expectation(
            "echo hello", "Mentions doppler secrets set"
        )
        self.assertFalse(passed)

    def test_run_static_eval_success(self) -> None:
        case = {
            "id": 1,
            "expected_output": "doppler projects create p && doppler setup && doppler secrets set K=V",
            "expectations": [
                "doppler projects create",
                "doppler setup",
                "doppler secrets set",
            ],
            "expected_command_patterns": [
                r"doppler\s+projects\s+create",
                r"doppler\s+setup",
            ],
            "forbidden_command_patterns": [r"echo\s+>\s+\.env"],
        }
        ok, failures = run_static_eval(case)
        self.assertTrue(ok, msg=str(failures))
        self.assertEqual(len(failures), 0)

    def test_run_static_eval_forbidden_failure(self) -> None:
        case = {
            "id": 99,
            "expected_output": "doppler run -- python3 script.py\necho > .env",
            "expectations": ["doppler run"],
            "expected_command_patterns": [r"doppler\s+run\s+--"],
            "forbidden_command_patterns": [r"echo\s+>\s+\.env"],
        }
        ok, failures = run_static_eval(case)
        self.assertFalse(ok)
        self.assertTrue(any("forbidden" in f for f in failures))

    def test_load_dataset_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "evals.json"
            content = {"skill_name": "managing-credentials", "evals": [{"id": 1}]}
            file_path.write_text(json.dumps(content), encoding="utf-8")

            cases = load_dataset(file_path)
            self.assertEqual(len(cases), 1)
            self.assertEqual(cases[0].get("id"), 1)

    def test_load_dataset_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "evals.json"
            file_path.write_text(json.dumps({"wrong_key": []}), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_dataset(file_path)

    @patch("builtins.print")
    def test_main_static(self, _mock_print: MagicMock) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            dataset = Path(tmp_dir) / "evals.json"
            dataset.write_text(
                json.dumps(
                    {
                        "skill_name": "managing-credentials",
                        "evals": [
                            {
                                "id": 1,
                                "prompt": "Setup doppler project",
                                "expected_output": "doppler projects create p && doppler setup",
                                "expectations": [],
                                "expected_command_patterns": [],
                                "forbidden_command_patterns": [],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            exit_code = main(["--dataset", str(dataset), "--static"])
            self.assertEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
