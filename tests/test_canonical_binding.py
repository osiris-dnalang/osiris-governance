"""Tests verifying OSIRIS-CANONICAL-JSON-V1 serialization, test vectors, and normalization pipeline."""

import hashlib
import pytest

from osiris_governance.canonical import (
    CANONICALIZATION_VERSION,
    canonical_sha256,
    canonicalize_json,
    enforce_unicode_policy,
    normalize_and_canonicalize,
    strict_parse_json,
)
from osiris_governance.errors import SchemaValidationError


# Official Published Test Vectors for OSIRIS-CANONICAL-JSON-V1
TEST_VECTORS = [
    {
        "id": "basic-key-order",
        "input": '{"z":3,"a":true}',
        "canonical_utf8": b'{"a":true,"z":3}',
        "expected_sha256": "sha256:" + hashlib.sha256(b'{"a":true,"z":3}').hexdigest(),
    },
    {
        "id": "nested-object-order",
        "input": '{"input":{"z":2,"a":1},"fixture_id":"echo-v1"}',
        "canonical_utf8": b'{"fixture_id":"echo-v1","input":{"a":1,"z":2}}',
        "expected_sha256": "sha256:" + hashlib.sha256(b'{"fixture_id":"echo-v1","input":{"a":1,"z":2}}').hexdigest(),
    },
    {
        "id": "array-order-preserved",
        "input": '{"items":["b","a"]}',
        "canonical_utf8": b'{"items":["b","a"]}',
        "expected_sha256": "sha256:" + hashlib.sha256(b'{"items":["b","a"]}').hexdigest(),
    },
    {
        "id": "unicode-nfc",
        "input": '{"message":"e\u0301"}', # e + combining acute accent (NFD)
        "canonical_utf8": '{"message":"\u00e9"}'.encode("utf-8"), # é (NFC)
        "expected_sha256": "sha256:" + hashlib.sha256('{"message":"\u00e9"}'.encode("utf-8")).hexdigest(),
    },
]


@pytest.mark.parametrize("vector", TEST_VECTORS, ids=lambda v: v["id"])
def test_official_test_vectors(vector):
    canonical_bytes, digest = normalize_and_canonicalize(vector["input"])
    assert canonical_bytes == vector["canonical_utf8"]
    assert digest == vector["expected_sha256"]


def test_reject_float_in_strict_parse():
    with pytest.raises(SchemaValidationError, match="FLOAT_FORBIDDEN"):
        strict_parse_json('{"count":1.0}')

    with pytest.raises(SchemaValidationError, match="FLOAT_FORBIDDEN"):
        normalize_and_canonicalize('{"nested":{"val":3.14}}')


def test_reject_duplicate_key_in_strict_parse():
    with pytest.raises(SchemaValidationError, match="DUPLICATE_KEY"):
        strict_parse_json('{"fixture_id":"safe-v1","fixture_id":"different-v1"}')


def test_reject_bom():
    with pytest.raises(SchemaValidationError, match="BOM_FORBIDDEN"):
        strict_parse_json(b'\xef\xbb\xbf{"key":"val"}')


def test_reject_trailing_data():
    with pytest.raises(SchemaValidationError, match="TRAILING_DATA"):
        strict_parse_json('{"a":1} trailing_non_whitespace')


def test_reject_bidi_controls():
    # U+202E is Right-to-Left Override (RLO)
    with pytest.raises(SchemaValidationError, match="BIDI_CONTROL_FORBIDDEN"):
        normalize_and_canonicalize('{"message":"test\u202eoverride"}')


def test_reject_non_ascii_keys():
    # French accent in key is forbidden by Unicode policy
    with pytest.raises(SchemaValidationError, match="KEY_NOT_ASCII"):
        normalize_and_canonicalize('{"clé":"valeur"}')


def test_unknown_field_schema_validation():
    def mock_schema_validator(obj):
        allowed_keys = {"schema_version", "fixture_id", "input"}
        extra = set(obj.keys()) - allowed_keys
        if extra:
            raise SchemaValidationError(f"UNKNOWN_FIELD: Unexpected fields {extra}")

    with pytest.raises(SchemaValidationError, match="UNKNOWN_FIELD"):
        normalize_and_canonicalize('{"fixture_id":"echo-v1","shell":"rm -rf /"}', schema_validator=mock_schema_validator)


def test_key_sorting_determinism():
    data_1 = {"z": 1, "a": "alpha", "m": [3, 2, 1], "b": {"nested_z": 10, "nested_a": 20}}
    data_2 = {"a": "alpha", "b": {"nested_a": 20, "nested_z": 10}, "m": [3, 2, 1], "z": 1}

    bytes_1 = canonicalize_json(data_1)
    bytes_2 = canonicalize_json(data_2)

    assert bytes_1 == bytes_2
    assert canonical_sha256(bytes_1) == canonical_sha256(bytes_2)


def test_compact_separators():
    data = {"key1": "val1", "key2": [1, 2, 3]}
    bytes_out = canonicalize_json(data)
    assert b" " not in bytes_out
    assert b"\n" not in bytes_out
    assert bytes_out == b'{"key1":"val1","key2":[1,2,3]}'


def test_boolean_and_integer_distinction():
    data = {"flag_true": True, "flag_false": False, "count": 0, "positive": 42}
    bytes_out = canonicalize_json(data)
    assert b'"flag_false":false' in bytes_out
    assert b'"flag_true":true' in bytes_out
    assert b'"count":0' in bytes_out
    assert b'"positive":42' in bytes_out
