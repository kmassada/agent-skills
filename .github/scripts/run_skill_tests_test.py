#!/usr/bin/env python3
"""Hermetic unit tests for .github/scripts/run_skill_tests.py."""

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from run_skill_tests import (
    discover_skill_tests,
    find_skill_root,
    main,
    run_test_files,
)


class TestFindSkillRoot(unittest.TestCase):
    """Tests finding skill root directories from file paths."""

    def test_find_valid_skill_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = Path(tmp_dir).resolve()
            skill = repo / "my-skill"
            skill.mkdir()
            (skill / "SKILL.md").write_text("# My Skill\n", encoding="utf-8")
            script = skill / "scripts" / "foo.py"
            script.parent.mkdir()
            script.write_text("# code\n", encoding="utf-8")

            found = find_skill_root(script, repo)
            self.assertEqual(found, skill)

    def test_find_root_non_skill_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = Path(tmp_dir).resolve()
            other = repo / ".github" / "scripts" / "test.py"
            other.parent.mkdir(parents=True)
            other.write_text("# code\n", encoding="utf-8")

            found = find_skill_root(other, repo)
            self.assertIsNone(found)

    def test_find_root_outside_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = Path(tmp_dir).resolve() / "repo"
            repo.mkdir()
            outside = Path(tmp_dir).resolve() / "outside.txt"
            outside.write_text("hello\n", encoding="utf-8")

            found = find_skill_root(outside, repo)
            self.assertIsNone(found)


class TestDiscoverSkillTests(unittest.TestCase):
    """Tests discovering companion test files inside a skill package."""

    def test_discovers_scripts_and_evals_tests(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            skill = Path(tmp_dir).resolve() / "sample-skill"
            scripts = skill / "scripts"
            evals = skill / "evals"
            scripts.mkdir(parents=True)
            evals.mkdir(parents=True)

            t1 = scripts / "helper_test.py"
            t1.write_text("# test\n", encoding="utf-8")
            t2 = scripts / "test_legacy.py"
            t2.write_text("# test\n", encoding="utf-8")
            t3 = evals / "run_eval_test.py"
            t3.write_text("# test\n", encoding="utf-8")

            # Non-test files to ignore
            (scripts / "helper.py").write_text("# helper\n", encoding="utf-8")
            (scripts / ".hidden_test.py").write_text("# hidden\n", encoding="utf-8")
            (scripts / "notes.txt").write_text("notes\n", encoding="utf-8")

            found = discover_skill_tests(skill)
            self.assertEqual(set(found), {t1, t2, t3})

    def test_empty_when_no_tests(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            skill = Path(tmp_dir).resolve() / "empty-skill"
            skill.mkdir()
            found = discover_skill_tests(skill)
            self.assertEqual(found, [])


class TestRunTestFiles(unittest.TestCase):
    """Tests executing test scripts with subprocess."""

    @mock.patch("subprocess.run")
    def test_run_success(self, mock_run: mock.MagicMock) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["python3", "test.py"],
            returncode=0,
            stdout="OK\n",
            stderr="",
        )
        passed = run_test_files([Path("/repo/skill/scripts/a_test.py")], Path("/repo"))
        self.assertTrue(passed)
        mock_run.assert_called_once()

    @mock.patch("subprocess.run")
    def test_run_failure(self, mock_run: mock.MagicMock) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["python3", "test.py"],
            returncode=1,
            stdout="",
            stderr="FAILED\n",
        )
        passed = run_test_files([Path("/repo/skill/scripts/a_test.py")], Path("/repo"))
        self.assertFalse(passed)


class TestMain(unittest.TestCase):
    """Tests main entrypoint flag handling."""

    def test_main_no_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            ret = main(["--repo-root", tmp_dir])
            self.assertEqual(ret, 0)

    @mock.patch("run_skill_tests.run_test_files", return_value=True)
    def test_main_with_all_flag(self, mock_run: mock.MagicMock) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = Path(tmp_dir).resolve()
            skill = repo / "test-skill"
            scripts = skill / "scripts"
            scripts.mkdir(parents=True)
            (skill / "SKILL.md").write_text("# Title\n", encoding="utf-8")
            test_file = scripts / "sample_test.py"
            test_file.write_text("# code\n", encoding="utf-8")

            ret = main(["--all", "--repo-root", str(repo)])
            self.assertEqual(ret, 0)
            mock_run.assert_called_once_with([test_file], repo)


if __name__ == "__main__":
    unittest.main()
