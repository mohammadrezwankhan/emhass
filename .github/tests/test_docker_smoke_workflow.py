"""Exercise Docker smoke orchestration without requiring a Docker daemon."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


class DockerSmokeWorkflowTests(unittest.TestCase):
    def run_smoke_step(self, launch_status=0, probe_status=0):
        workflow = yaml.safe_load((ROOT / ".github/workflows/docker-build-test.yaml").read_text())
        step = next(
            item for item in workflow["jobs"]["build"]["steps"] if item.get("name") == "Test Image"
        )
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            cleanup = directory / "cleanup.txt"
            docker = directory / "docker"
            docker.write_text(
                "#!/bin/sh\n"
                'case "$1" in\n'
                ' run) printf "fixture-container\\n"; exit "$FIXTURE_LAUNCH_STATUS" ;;\n'
                ' exec) exit "$FIXTURE_PROBE_STATUS" ;;\n'
                ' logs) printf "fixture logs\\n" ;;\n'
                ' rm) printf "cleaned\\n" > "$FIXTURE_CLEANUP" ;;\n'
                " *) exit 99 ;;\nesac\n"
            )
            docker.chmod(0o755)
            result = subprocess.run(
                ["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", step["run"]],
                capture_output=True,
                text=True,
                cwd=ROOT,
                timeout=10,
                env={
                    **os.environ,
                    "PATH": str(directory) + os.pathsep + os.environ["PATH"],
                    "EMHASS_IMAGE": "fixture-image",
                    "FIXTURE_LAUNCH_STATUS": str(launch_status),
                    "FIXTURE_PROBE_STATUS": str(probe_status),
                    "FIXTURE_CLEANUP": str(cleanup),
                },
            )
            return result, cleanup.exists()

    def test_running_service_is_probed_and_removed(self):
        result, cleaned = self.run_smoke_step()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(cleaned)

    def test_failed_probe_is_rejected_and_container_removed(self):
        result, cleaned = self.run_smoke_step(probe_status=1)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(cleaned)

    def test_docker_launch_failure_is_rejected(self):
        result, _ = self.run_smoke_step(launch_status=125)
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
