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
    load_skill_corpus,
    main,
    run_static_eval,
)


class TestRunEval(unittest.TestCase):
    """Hermetic unit tests for eval runner functions."""

    def test_check_credential_expectation(self) -> None:
        text = (
            "Initialize via pass init user@local and set via cred set slack/bot_token"
        )
        passed, _ = check_credential_expectation(
            text, "Instructs initializing pass store using pass init"
        )
        self.assertTrue(passed)

        passed, _ = check_credential_expectation(
            text, "Sets secret tokens using cred set"
        )
        self.assertTrue(passed)

        passed, _ = check_credential_expectation("echo hello", "Mentions pass init")
        self.assertFalse(passed)

    def test_run_static_eval_success(self) -> None:
        case = {
            "id": 1,
            "expectations": [
                "pass init",
                "cred set",
            ],
            "expected_command_patterns": [
                r"pass\s+init",
                r"cred\s+set",
            ],
            "forbidden_command_patterns": [r"echo\s+>\s+\.env"],
        }
        corpus = "pass init user@local && cred set slack/bot_token"
        ok, failures = run_static_eval(case, corpus=corpus)
        self.assertTrue(ok, msg=str(failures))
        self.assertEqual(len(failures), 0)

    def test_run_static_eval_forbidden_failure(self) -> None:
        case = {
            "id": 99,
            "expectations": ["cred run"],
            "expected_command_patterns": [r"cred\s+run\s+--"],
            "forbidden_command_patterns": [r"echo\s+>\s+\.env"],
        }
        corpus = "cred run -- python3 script.py\necho > .env"
        ok, failures = run_static_eval(case, corpus=corpus)
        self.assertFalse(ok)
        self.assertTrue(any("forbidden" in f for f in failures))

    def test_run_static_eval_missing_pattern_fails(self) -> None:
        """The suite must be falsifiable: absent documentation is a failure."""
        case = {
            "id": 100,
            "expectations": [],
            "expected_command_patterns": [r"cred\s+teleport"],
            "forbidden_command_patterns": [],
        }
        ok, failures = run_static_eval(case, corpus="cred run -- agy")
        self.assertFalse(ok)
        self.assertTrue(any("Missing expected command pattern" in f for f in failures))

    def test_load_skill_corpus_reads_real_docs(self) -> None:
        """Static mode scores the shipped documentation, not a sample answer."""
        corpus = load_skill_corpus()
        self.assertIn("cred run", corpus)
        self.assertIn("pass init", corpus)

    def test_load_skill_corpus_missing_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with self.assertRaises(FileNotFoundError):
                load_skill_corpus([Path(tmp_dir) / "absent.md"])

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
                                "prompt": "Setup pass store",
                                "expected_output": "pass init user@local && cred set slack/bot_token",
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
