"""Check the probe against real local HTTP responses."""

import importlib.util
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "docker_smoke_probe", Path(__file__).resolve().parents[1] / "scripts/docker_smoke_probe.py"
)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


class DockerSmokeProbeTests(unittest.TestCase):
    def run_probe(self, config, status, health):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                is_config = self.path == "/get-config"
                self.send_response(200 if is_config else status)
                self.end_headers()
                self.wfile.write(json.dumps(config if is_config else health).encode())

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.01))
        thread.start()
        try:
            return probe.wait_for_startup(
                f"http://127.0.0.1:{server.server_port}", timeout=0.15, interval=0.01
            )
        finally:
            server.shutdown()
            thread.join()
            server.server_close()

    def health(self, status):
        return {"status": status, "boot_ts": "2026-10-18T00:00:00Z", "versions": {"emhass": "1.0"}}

    def test_degraded_before_first_optimization_is_accepted(self):
        self.run_probe({"config": True}, 503, self.health("degraded"))

    def test_healthy_service_is_accepted(self):
        self.run_probe({"config": True}, 200, self.health("ok"))

    def test_empty_configuration_is_rejected(self):
        with self.assertRaises(RuntimeError):
            self.run_probe({}, 200, self.health("ok"))

    def test_inconsistent_health_status_is_rejected(self):
        with self.assertRaises(RuntimeError):
            self.run_probe({"config": True}, 200, self.health("degraded"))

    def test_incomplete_initialization_is_rejected(self):
        with self.assertRaises(RuntimeError):
            self.run_probe({"config": True}, 503, {"status": "degraded"})
