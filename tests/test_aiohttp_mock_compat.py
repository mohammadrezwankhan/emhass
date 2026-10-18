"""Keep HTTP mocks faithful while using security-supported aiohttp releases."""

import unittest

import aiohttp

from .aiohttp_mock import aioresponses


class TestAiohttpMocks(unittest.IsolatedAsyncioTestCase):
    async def test_response_preserves_status_headers_and_json_body(self):
        url = "https://emhass-test.invalid/forecast"
        with aioresponses() as mocked:
            mocked.get(url, status=200, payload={"power": [10, 20]}, headers={"X-Test": "yes"})
            async with aiohttp.ClientSession() as session, session.get(url) as response:
                self.assertIsInstance(response, aiohttp.ClientResponse)
                self.assertEqual(response.status, 200)
                self.assertEqual(response.headers["X-Test"], "yes")
                self.assertEqual(str(response.url), url)
                self.assertEqual(await response.json(), {"power": [10, 20]})
                response.raise_for_status()
            self.assertTrue(response.closed)
            mocked.assert_called_once_with(url)

    async def test_http_error_remains_an_http_error_with_its_body(self):
        url = "https://emhass-test.invalid/unavailable"
        with aioresponses() as mocked:
            mocked.get(url, status=503, body="temporarily unavailable", content_type="text/plain")
            async with aiohttp.ClientSession() as session, session.get(url) as response:
                self.assertEqual(await response.text(), "temporarily unavailable")
                with self.assertRaises(aiohttp.ClientResponseError) as error:
                    response.raise_for_status()
                self.assertEqual(error.exception.status, 503)

    async def test_unregistered_request_is_rejected(self):
        with aioresponses():
            async with aiohttp.ClientSession() as session:
                with self.assertRaises(aiohttp.ClientConnectionError):
                    await session.get("https://emhass-test.invalid/not-registered")

    async def test_large_history_body_preserves_every_byte(self):
        url = "https://emhass-test.invalid/history"
        body = b"recorded history\n" * 20000
        with aioresponses() as mocked:
            mocked.get(url, body=body, content_type="application/octet-stream")
            async with aiohttp.ClientSession() as session, session.get(url) as response:
                self.assertEqual(await response.read(), body)
