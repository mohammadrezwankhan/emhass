"""Read recorded HTTP response bodies without reconstructing pickled objects.

These legacy fixtures contain a requests.Response pickle inside bzip2. Tests
need only its literal _content bytes, so parse the opcode stream statically and
never import or invoke any object named by the serialized data.
"""

import bz2
import pickletools

MAX_COMPRESSED_BYTES = 4 * 1024 * 1024
MAX_DECOMPRESSED_BYTES = 8 * 1024 * 1024
MAX_OPCODES = 10_000


def _fixture_opcodes(compressed: bytes) -> list[tuple]:
    if len(compressed) > MAX_COMPRESSED_BYTES:
        raise ValueError("Response fixture exceeds the compressed size limit")
    decoder = bz2.BZ2Decompressor()
    try:
        payload = decoder.decompress(compressed, max_length=MAX_DECOMPRESSED_BYTES + 1)
    except (EOFError, OSError, ValueError):
        raise ValueError("Response fixture is not valid bzip2 data") from None
    if len(payload) > MAX_DECOMPRESSED_BYTES:
        raise ValueError("Response fixture exceeds the decompressed size limit")
    if not decoder.eof or decoder.unused_data:
        raise ValueError("Response fixture is incomplete or has trailing compressed data")
    if payload[:2] not in (b"\x80\x04", b"\x80\x05"):
        raise ValueError("Response fixture must use pickle protocol 4 or 5")

    operations = []
    try:
        for operation in pickletools.genops(payload):
            operations.append(operation)
            if len(operations) > MAX_OPCODES:
                raise ValueError("Response fixture exceeds the opcode limit")
    except ValueError:
        raise ValueError("Response fixture has invalid or excessive pickle opcodes") from None
    if not operations or operations[-1][0].name != "STOP":
        raise ValueError("Response fixture has no terminating opcode")
    if operations[-1][2] != len(payload) - 1:
        raise ValueError("Response fixture has trailing pickle data")
    boundaries = {position for _, _, position in operations} | {len(payload)}
    for opcode, argument, position in operations:
        if opcode.name == "FRAME" and position + 9 + argument not in boundaries:
            raise ValueError("Response fixture has an invalid frame boundary")
    return operations


def extract_response_content(compressed: bytes) -> bytes:
    """Extract exactly one literal response body, without unpickling the fixture."""
    contents = []
    awaiting_content = False
    for opcode, argument, _ in _fixture_opcodes(compressed):
        if awaiting_content:
            if opcode.name in {"MEMOIZE", "BINPUT", "LONG_BINPUT"}:
                continue
            if opcode.name not in {"BINBYTES", "SHORT_BINBYTES", "BINBYTES8"}:
                raise ValueError("Response fixture content must be literal bytes")
            contents.append(argument)
            awaiting_content = False
        elif isinstance(argument, str) and argument == "_content":
            awaiting_content = True
    if awaiting_content or len(contents) != 1:
        raise ValueError("Response fixture must contain exactly one literal response body")
    return contents[0]
