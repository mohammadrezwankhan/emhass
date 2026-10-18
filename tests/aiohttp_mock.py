"""Adapt aioresponses 0.7.9 to aiohttp >= 3.14.3 without changing production code.

aioresponses constructs a response after a simulated request has completed, but
does not pass aiohttp's required stream_writer argument. Its buffered response
bodies also use a bare network protocol with no HTTP parser for flow control.
Adapt those two test-only seams. Remove this adapter when upgrading to an
aioresponses release supporting aiohttp 3.14 response construction (upstream #289).
"""

from types import SimpleNamespace
from unittest.mock import patch

from aiohttp import ClientResponse
from aiohttp.streams import StreamReader
from aioresponses import aioresponses as _aioresponses

__all__ = ["aioresponses"]


class _MockClientResponse(ClientResponse):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("stream_writer", SimpleNamespace(output_size=0))
        super().__init__(*args, **kwargs)


class _BufferedResponseProtocol:
    """Flow control for complete fixture bodies, which have no network parser."""

    connected = True
    _reading_paused = False

    def pause_reading(self):
        self._reading_paused = True

    def resume_reading(self, resume_parser=True):
        self._reading_paused = False


def _buffered_stream_reader(loop=None):
    return StreamReader(_BufferedResponseProtocol(), limit=2**16, loop=loop)


class aioresponses(_aioresponses):
    def start(self):
        # Patch only the mock library while this mock context is active.
        self._reader_patch = patch(
            "aioresponses.core.stream_reader_factory", _buffered_stream_reader
        )
        self._reader_patch.start()
        try:
            super().start()
        except BaseException:
            self._reader_patch.stop()
            raise

    def stop(self):
        try:
            super().stop()
        finally:
            self._reader_patch.stop()

    def add(self, url, **kwargs):
        kwargs.setdefault("response_class", _MockClientResponse)
        return super().add(url, **kwargs)
