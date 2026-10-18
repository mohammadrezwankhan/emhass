"""Exercise the database updater's Git operations against local repositories."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


class DatabaseUpdateWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.work = self.root / "work"
        self.remote = self.root / "remote.git"
        self.work.mkdir()
        self.git("init", "--bare", str(self.remote))
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Workflow test fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "commit.gpgsign", "false")
        self.git("config", "core.hooksPath", str(self.work / ".git/hooks"))
        self.data = self.work / "src/emhass/data"
        self.data.mkdir(parents=True)
        for name in ("cec_inverters.pbz2", "cec_modules.pbz2"):
            (self.data / name).write_text("initial fixture\n")
        self.git("add", ".")
        self.git("commit", "-m", "Initial fixture")
        self.git("remote", "add", "origin", str(self.remote))
        self.git("push", "-u", "origin", "main")
        self.before = self.git("rev-parse", "HEAD").stdout.strip()

    def git(self, *args):
        return subprocess.run(
            ["git", *args],
            cwd=self.work,
            check=True,
            capture_output=True,
            text=True,
        )

    def run_publish_fragment(self):
        workflow = yaml.safe_load((ROOT / ".github/workflows/updatePVLibDB.yaml").read_text())
        step = next(
            item
            for item in workflow["jobs"]["pull-and-build"]["steps"]
            if item.get("name") == "push database changes"
        )
        lines = step["run"].splitlines()
        # Cleanup and identity setup are unrelated to this failure path and
        # include a system temporary path; exercise only actual Git operations.
        start = next(i for i, line in enumerate(lines) if line.startswith("git add "))
        return subprocess.run(
            [
                "bash",
                "--noprofile",
                "--norc",
                "-e",
                "-o",
                "pipefail",
                "-c",
                "\n".join(lines[start:]),
            ],
            cwd=self.work,
            capture_output=True,
            text=True,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )

    def change_database(self):
        (self.data / "cec_modules.pbz2").write_text("updated fixture\n")

    def install_rejecting_hook(self, path):
        path.write_text("#!/bin/sh\nexit 1\n")
        path.chmod(0o755)

    def test_unchanged_databases_succeed_without_new_commit(self):
        result = self.run_publish_fragment()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.git("rev-parse", "HEAD").stdout.strip(), self.before)

    def test_changed_databases_are_pushed(self):
        self.change_database()
        result = self.run_publish_fragment()
        self.assertEqual(result.returncode, 0, result.stderr)
        current = self.git("rev-parse", "HEAD").stdout.strip()
        self.assertNotEqual(current, self.before)
        remote = self.git("ls-remote", "origin", "refs/heads/main").stdout.split()[0]
        self.assertEqual(remote, current)

    def test_rejected_commit_fails_the_job(self):
        self.change_database()
        self.install_rejecting_hook(self.work / ".git/hooks/commit-msg")
        result = self.run_publish_fragment()
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.git("rev-parse", "HEAD").stdout.strip(), self.before)

    def test_rejected_push_fails_the_job(self):
        self.change_database()
        self.install_rejecting_hook(self.remote / "hooks/pre-receive")
        result = self.run_publish_fragment()
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        remote = self.git("ls-remote", "origin", "refs/heads/main").stdout.split()[0]
        self.assertEqual(remote, self.before)


if __name__ == "__main__":
    unittest.main()
