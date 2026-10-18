"""Verify the HTTP mock preserves aiohttp response and error behavior."""

import asyncio

import aiohttp
import pytest

from tests.aiohttp_mock import aioresponses


def test_json_response_preserves_status_headers_and_body():
    async def run():
        with aioresponses() as mocked:
            mocked.get(
                "https://dependency-test.invalid/status",
                status=201,
                payload={"status": "ok", "value": 42},
                headers={"X-Test-Header": "preserved"},
            )
            async with aiohttp.ClientSession() as session:
                async with session.get("https://dependency-test.invalid/status") as response:
                    assert isinstance(response, aiohttp.ClientResponse)
                    assert response.status == 201
                    assert response.headers["X-Test-Header"] == "preserved"
                    assert await response.json() == {"status": "ok", "value": 42}

    asyncio.run(run())


def test_error_status_and_body_are_not_suppressed():
    async def run():
        with aioresponses() as mocked:
            mocked.get("https://dependency-test.invalid/missing", status=404, body="missing")
            async with aiohttp.ClientSession() as session:
                async with session.get("https://dependency-test.invalid/missing") as response:
                    assert response.status == 404
                    assert await response.text() == "missing"
                    with pytest.raises(aiohttp.ClientResponseError) as caught:
                        response.raise_for_status()
                    assert caught.value.status == 404

    asyncio.run(run())


def test_transport_errors_are_not_suppressed():
    async def run():
        with aioresponses() as mocked:
            mocked.get(
                "https://dependency-test.invalid/offline",
                exception=aiohttp.ClientConnectionError("offline"),
            )
            async with aiohttp.ClientSession() as session:
                with pytest.raises(aiohttp.ClientConnectionError, match="offline"):
                    await session.get("https://dependency-test.invalid/offline")

    asyncio.run(run())


def test_large_response_stream_preserves_every_byte():
    async def run():
        # Exceed StreamReader's high-water mark to exercise mock flow control.
        body = b"fixture response " * 20000
        with aioresponses() as mocked:
            mocked.get("https://dependency-test.invalid/history", body=body)
            async with aiohttp.ClientSession() as session:
                async with session.get("https://dependency-test.invalid/history") as response:
                    chunks = [chunk async for chunk in response.content.iter_chunked(8192)]
                    assert b"".join(chunks) == body
                    assert response.content.at_eof()
                    assert response.status == 200

    asyncio.run(run())
