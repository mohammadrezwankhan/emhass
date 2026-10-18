"""Temporary aioresponses compatibility for security-supported aiohttp.

aioresponses 0.7.9 omits aiohttp's required stream_writer argument and does not
model the protocol used when its buffered body reaches the high-water mark.
Supply these through the mock library's hooks, only for these tests.
Remove this adapter once aioresponses supports the current aiohttp constructor.
The real response still handles status, headers, bodies, and HTTP errors.
"""

import inspect
from types import SimpleNamespace
from unittest.mock import patch

from aiohttp import ClientResponse, StreamReader
from aioresponses import aioresponses as _aioresponses

_HAS_STREAM_WRITER = "stream_writer" in inspect.signature(ClientResponse).parameters


class _MockClientResponse(ClientResponse):
    def __init__(self, *args, **kwargs):
        if _HAS_STREAM_WRITER:
            # aioresponses supplies writer=None: the mocked request is already sent.
            kwargs.setdefault("stream_writer", SimpleNamespace(output_size=0))
        super().__init__(*args, **kwargs)


class _BufferedResponseProtocol:
    # aioresponses feeds already decoded bytes; it has no wire parser/transport.
    # Preserve the reader's pause/resume state without inventing HTTP wire data.
    connected = True
    _reading_paused = False

    def pause_reading(self):
        self._reading_paused = True

    def resume_reading(self, resume_parser=True):
        self._reading_paused = False


def _stream_reader_factory(loop=None):
    return StreamReader(_BufferedResponseProtocol(), limit=2**16, loop=loop)


class aioresponses(_aioresponses):
    def start(self):
        self._reader_patcher = patch(
            "aioresponses.core.stream_reader_factory", _stream_reader_factory
        )
        self._reader_patcher.start()
        try:
            super().start()
        except BaseException:
            self._reader_patcher.stop()
            raise

    def stop(self):
        try:
            super().stop()
        finally:
            self._reader_patcher.stop()

    def add(self, url, **kwargs):
        if kwargs.get("response_class") is None:
            kwargs["response_class"] = _MockClientResponse
        return super().add(url, **kwargs)
