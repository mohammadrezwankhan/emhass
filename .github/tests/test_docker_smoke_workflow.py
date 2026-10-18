"""Check the Docker smoke-test decision using a local Docker command stub."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


class DockerSmokeWorkflowTests(unittest.TestCase):
    def run_smoke_step(self, output, status):
        workflow = yaml.safe_load((ROOT / ".github/workflows/docker-build-test.yaml").read_text())
        step = next(
            item for item in workflow["jobs"]["build"]["steps"] if item.get("name") == "Test Image"
        )
        command = step["run"].replace("${{ steps.build.outputs.imageid }}", "fixture-image")
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            docker = directory / "docker"
            docker.write_text(
                '#!/bin/sh\nprintf "%s\\n" "$FIXTURE_DOCKER_OUTPUT" >&2\nexit "$FIXTURE_DOCKER_STATUS"\n'
            )
            docker.chmod(0o755)
            return subprocess.run(
                ["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", command],
                capture_output=True,
                text=True,
                cwd=directory,
                env={
                    **os.environ,
                    "PATH": str(directory) + os.pathsep + os.environ["PATH"],
                    "EMHASS_IMAGE": "fixture-image",
                    "FIXTURE_DOCKER_OUTPUT": output,
                    "FIXTURE_DOCKER_STATUS": str(status),
                },
            )

    def test_expected_missing_config_failure_is_accepted(self):
        result = self.run_smoke_step("FileNotFoundError: secrets_emhass.yaml", 1)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_unrelated_application_failure_is_rejected(self):
        result = self.run_smoke_step("ImportError: cannot import application", 1)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_docker_runtime_failure_is_rejected(self):
        result = self.run_smoke_step("docker: daemon unavailable", 125)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_unexpected_success_is_rejected(self):
        result = self.run_smoke_step("secrets_emhass.yaml loaded successfully", 0)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_other_failure_that_mentions_config_is_rejected(self):
        result = self.run_smoke_step("ValueError: secrets_emhass.yaml is invalid", 1)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
