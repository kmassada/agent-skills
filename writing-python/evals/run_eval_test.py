#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Unit tests for writing-python/evals/run_eval.py."""

import json
import sys
import unittest
from pathlib import Path

# Ensure script can import run_eval directly
sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_eval import (
    DEFAULT_DATASET,
    check_python_expectation,
    evaluate_static_benchmark,
)


class RunEvalTest(unittest.TestCase):
    """Test suite covering Python quality expectations and static benchmark evaluations."""

    def test_collections_abc_check(self):
        """Should detect collections.abc abstractions."""
        valid = "from collections.abc import Sequence\ndef f(x: Sequence[str]): pass"
        invalid = "def f(x: list[str]): pass"

        passed, _ = check_python_expectation(valid, "uses collections.abc")
        self.assertTrue(passed)

        failed, _ = check_python_expectation(invalid, "from collections.abc import")
        self.assertFalse(failed)

    def test_legacy_typing_ban(self):
        """Should fail when deprecated typing.List/Dict are used."""
        dirty = "from typing import List, Dict\nx: List[str] = []"
        clean = "from collections.abc import Sequence\nx: list[str] = []"

        passed, _ = check_python_expectation(clean, "no legacy typing")
        self.assertTrue(passed)

        failed, _ = check_python_expectation(dirty, "no legacy typing")
        self.assertFalse(failed)

    def test_subprocess_check_parameter(self):
        """Should detect explicit check parameter in subprocess.run."""
        valid = "subprocess.run(['git'], check=False)"
        invalid = "subprocess.run(['git'])"

        passed, _ = check_python_expectation(valid, "check=False parameter")
        self.assertTrue(passed)

        failed, _ = check_python_expectation(invalid, "check=False parameter")
        self.assertFalse(failed)

    def test_all_dataset_benchmarks_pass_statically(self):
        """All 10 benchmark cases in evals.json should pass static evaluation."""
        self.assertTrue(DEFAULT_DATASET.is_file())
        dataset = json.loads(DEFAULT_DATASET.read_text(encoding="utf-8"))
        eval_cases = dataset.get("evals", [])
        self.assertEqual(len(eval_cases), 10)

        for case in eval_cases:
            passed, failures = evaluate_static_benchmark(case, verbose=False)
            self.assertTrue(passed, f"Case {case['id']} failed: {failures}")


if __name__ == "__main__":
    unittest.main()
