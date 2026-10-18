"""Bounded startup smoke probe; no Home Assistant credentials are needed."""

import json
import time
from urllib.error import HTTPError
from urllib.request import urlopen


def read_json(url, timeout):
    try:
        response = urlopen(url, timeout=timeout)
    except HTTPError as error:
        response = error
    with response:
        return response.code, json.load(response)


def wait_for_startup(base_url="http://127.0.0.1:5000", timeout=90, interval=1):
    deadline = time.monotonic() + timeout
    error = None
    while time.monotonic() < deadline:
        try:
            request_timeout = max(0.01, min(2, deadline - time.monotonic()))
            config_code, config = read_json(base_url + "/get-config", request_timeout)
            health_code, health = read_json(base_url + "/healthz", request_timeout)
            if config_code != 200 or not isinstance(config, dict) or not config:
                raise ValueError("Configuration endpoint did not return a nonempty object")
            if (health_code, health.get("status")) not in ((200, "ok"), (503, "degraded")):
                raise ValueError("Unexpected health status")
            if not health.get("boot_ts") or not health.get("versions", {}).get("emhass"):
                raise ValueError("Startup metadata is incomplete")
            print("Docker startup smoke passed: " + health["status"])
            return health
        except (OSError, ValueError, AttributeError) as exc:
            error = exc
            time.sleep(min(interval, max(0, deadline - time.monotonic())))
    raise RuntimeError(f"Application did not start within {timeout}s: {error}")


if __name__ == "__main__":
    wait_for_startup()
