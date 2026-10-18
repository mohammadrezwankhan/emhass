"""Static credential and format checks for recorded HTTP fixtures."""

import bz2
import json
import pathlib
import re
import struct

import pytest

from tests import response_fixtures

DATA_PATH = pathlib.Path(__file__).resolve().parents[1] / "data"
RESPONSE_FIXTURES = [
    "test_response_get_data_get_method.pbz2",
    "test_response_solcast_get_method.pbz2",
]
PLACEHOLDER_AUTHORIZATION = "Bearer TEST_ONLY_REDACTED_"
JWT_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"
)


def _response_pickle(*bodies, prefix=b""):
    entries = []
    for body in bodies:
        entries.append(b"\x8c\x08_contentB" + struct.pack("<I", len(body)) + body + b"s")
    return b"\x80\x04" + prefix + b"}" + b"".join(entries) + b"."


@pytest.mark.parametrize("filename", RESPONSE_FIXTURES)
def test_recorded_authorization_is_an_inert_placeholder(filename):
    operations = response_fixtures._fixture_opcodes((DATA_PATH / filename).read_bytes())
    header_indices = []
    unsafe_indices = []
    for index, (_, argument, _) in enumerate(operations, 1):
        if isinstance(argument, str) and re.match(r"(?i)^(Bearer|Basic)\s", argument):
            header_indices.append(index)
            if not re.fullmatch(re.escape(PLACEHOLDER_AUTHORIZATION) + "X*", argument):
                unsafe_indices.append(index)
    # Report positions only, so a regression cannot disclose credentials in pytest output.
    assert len(header_indices) == 1
    assert not unsafe_indices, f"Non-placeholder authorization at opcodes {unsafe_indices}"


@pytest.mark.parametrize("filename", RESPONSE_FIXTURES)
def test_recorded_response_has_no_jwt_strings(filename):
    operations = response_fixtures._fixture_opcodes((DATA_PATH / filename).read_bytes())
    matching_indices = [
        index
        for index, (_, argument, _) in enumerate(operations, 1)
        if isinstance(argument, str) and JWT_PATTERN.search(argument)
    ]
    assert not matching_indices, f"JWT-shaped text at opcodes {matching_indices}"


def test_recorded_cookie_metadata_is_an_inert_placeholder():
    operations = response_fixtures._fixture_opcodes(
        (DATA_PATH / "test_response_solcast_get_method.pbz2").read_bytes()
    )
    expected_slots = {91: "TEST_ONLY_REDACTED_COOKIE_", 321: "TEST", 391: "TEST", 448: "TEST", 505: "TEST"}
    unsafe_indices = []
    for index, prefix in expected_slots.items():
        argument = operations[index - 1][1]
        if not isinstance(argument, str) or not re.fullmatch(re.escape(prefix) + "X*", argument):
            unsafe_indices.append(index)
    assert not unsafe_indices, f"Non-placeholder cookie metadata at opcodes {unsafe_indices}"


@pytest.mark.parametrize("filename", RESPONSE_FIXTURES)
def test_recorded_response_body_is_still_json(filename):
    body = response_fixtures.extract_response_content((DATA_PATH / filename).read_bytes())
    parsed = json.loads(body)
    shape = type(parsed).__name__
    expected_shape = "list" if filename == RESPONSE_FIXTURES[0] else "dict"
    assert shape == expected_shape
    assert len(parsed) > 0


def test_extractor_never_resolves_serialized_globals():
    body = b'{"fixture":true}'
    # Resolving this GLOBAL would import a nonexistent module; static parsing does not.
    payload = _response_pickle(body, prefix=b"cfixture_module_that_does_not_exist\nResponse\n0")
    assert response_fixtures.extract_response_content(bz2.compress(payload)) == body


@pytest.mark.parametrize(
    "payload",
    [b"\x80\x04N.", _response_pickle(b"{}", b"[]"), b"\x80\x04}\x8c\x08_contentNs."],
)
def test_extractor_rejects_missing_duplicate_or_nonliteral_content(payload):
    with pytest.raises(ValueError, match="(exactly one|literal bytes)"):
        response_fixtures.extract_response_content(bz2.compress(payload))


def test_extractor_bounds_compressed_input(monkeypatch):
    compressed = bz2.compress(_response_pickle(b"{}"))
    monkeypatch.setattr(response_fixtures, "MAX_COMPRESSED_BYTES", len(compressed) - 1)
    with pytest.raises(ValueError, match="compressed size limit"):
        response_fixtures.extract_response_content(compressed)


def test_extractor_bounds_decompression(monkeypatch):
    compressed = bz2.compress(_response_pickle(b"x" * 1024))
    monkeypatch.setattr(response_fixtures, "MAX_DECOMPRESSED_BYTES", 128)
    with pytest.raises(ValueError, match="decompressed size limit"):
        response_fixtures.extract_response_content(compressed)


def test_extractor_bounds_opcode_count(monkeypatch):
    compressed = bz2.compress(_response_pickle(b"{}", prefix=b"N0" * 100))
    monkeypatch.setattr(response_fixtures, "MAX_OPCODES", 20)
    with pytest.raises(ValueError, match="excessive pickle opcodes"):
        response_fixtures.extract_response_content(compressed)


@pytest.mark.parametrize("layer", ["compressed", "pickle"])
def test_extractor_rejects_trailing_data(layer):
    payload = _response_pickle(b"{}")
    compressed = (
        bz2.compress(payload + b"extra")
        if layer == "pickle"
        else bz2.compress(payload) + b"extra"
    )
    with pytest.raises(ValueError, match="trailing"):
        response_fixtures.extract_response_content(compressed)


def test_extractor_rejects_truncated_compression():
    compressed = bz2.compress(_response_pickle(b"{}"))
    with pytest.raises(ValueError, match="incomplete"):
        response_fixtures.extract_response_content(compressed[:-4])


def test_extractor_rejects_invalid_frame_boundary():
    payload = _response_pickle(b"{}")
    payload = payload[:2] + b"\x95" + struct.pack("<Q", len(payload) + 100) + payload[2:]
    with pytest.raises(ValueError, match="frame boundary"):
        response_fixtures.extract_response_content(bz2.compress(payload))
