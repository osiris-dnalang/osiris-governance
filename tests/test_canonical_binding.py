"""Tests verifying OSIRIS-CANONICAL-JSON-V1 serialization and SHA-256 binding."""

import pytest

from osiris_governance.canonical import (
    CANONICALIZATION_VERSION,
    canonical_sha256,
    canonicalize_json,
)
from osiris_governance.errors import SchemaValidationError


def test_key_sorting_determinism():
    """Different key insertion orders produce identical canonical bytes."""
    data_1 = {"z": 1, "a": "alpha", "m": [3, 2, 1], "b": {"nested_z": 10, "nested_a": 20}}
    data_2 = {"a": "alpha", "b": {"nested_a": 20, "nested_z": 10}, "m": [3, 2, 1], "z": 1}

    bytes_1 = canonicalize_json(data_1)
    bytes_2 = canonicalize_json(data_2)

    assert bytes_1 == bytes_2
    assert canonical_sha256(bytes_1) == canonical_sha256(bytes_2)


def test_compact_separators():
    """Canonical JSON contains no redundant whitespace."""
    data = {"key1": "val1", "key2": [1, 2, 3]}
    bytes_out = canonicalize_json(data)
    # Expected: b'{"key1":"val1","key2":[1,2,3]}'
    assert b" " not in bytes_out
    assert b"\n" not in bytes_out
    assert bytes_out == b'{"key1":"val1","key2":[1,2,3]}'


def test_float_rejection():
    """Floats are strictly rejected to prevent IEEE-754 architecture divergence."""
    with pytest.raises(SchemaValidationError, match="Floats are prohibited"):
        canonicalize_json({"cost_usd": 0.05})

    with pytest.raises(SchemaValidationError, match="Floats are prohibited"):
        canonicalize_json({"nested": {"weights": [1, 2, 3.14]}})


def test_boolean_and_integer_distinction():
    """Booleans and integers are preserved and validated properly."""
    data = {"flag_true": True, "flag_false": False, "count": 0, "positive": 42}
    bytes_out = canonicalize_json(data)
    assert b'"flag_false":false' in bytes_out
    assert b'"flag_true":true' in bytes_out
    assert b'"count":0' in bytes_out
    assert b'"positive":42' in bytes_out


def test_unicode_preservation():
    """UTF-8 unicode characters are preserved without ASCII escape sequences."""
    data = {"message": "λ-calculus and Schrödinger state: |ψ⟩"}
    bytes_out = canonicalize_json(data)
    decoded = bytes_out.decode("utf-8")
    assert "λ-calculus" in decoded
    assert "|ψ⟩" in decoded
    assert "\\u" not in decoded


def test_non_string_key_rejection():
    """Mapping keys must be strings."""
    with pytest.raises(SchemaValidationError, match="Mapping key must be str"):
        canonicalize_json({123: "numeric_key"})
