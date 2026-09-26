"""Deterministic canonical serialization and hashing: OSIRIS-CANONICAL-JSON-V1."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
import hashlib
import json
from typing import Any, Mapping

from .errors import SchemaValidationError

CANONICALIZATION_VERSION = "OSIRIS-CANONICAL-JSON-V1"


def _validate_types_recursive(value: Any, path: str = "root") -> None:
    """Validates that value contains only allowed canonical types.
    
    Allowed types:
      - None
      - bool
      - int (strictly int, excluding bool which is an int subclass in Python)
      - str
      - list, tuple
      - dict (with string keys)
      - dataclass (converted via asdict)
      
    Forbidden types:
      - float (to eliminate IEEE-754 serialization differences across architectures)
      - set, frozenset
      - bytes, bytearray
      - objects with custom repr
    """
    if value is None:
        return
    if isinstance(value, bool):
        return
    if isinstance(value, float):
        raise SchemaValidationError(
            f"Floats are prohibited in {CANONICALIZATION_VERSION} at '{path}'. "
            "Use integer fixed-point or decimal string representation."
        )
    if isinstance(value, int):
        return
    if isinstance(value, str):
        return
    if is_dataclass(value) and not isinstance(value, type):
        _validate_types_recursive(asdict(value), path)
        return
    if isinstance(value, (list, tuple)):
        for idx, item in enumerate(value):
            _validate_types_recursive(item, f"{path}[{idx}]")
        return
    if isinstance(value, (dict, Mapping)):
        for k, v in value.items():
            if not isinstance(k, str):
                raise SchemaValidationError(
                    f"Mapping key must be str in {CANONICALIZATION_VERSION} at '{path}', got {type(k).__name__}"
                )
            _validate_types_recursive(v, f"{path}.{k}")
        return

    raise SchemaValidationError(
        f"Unsupported type '{type(value).__name__}' at '{path}' in {CANONICALIZATION_VERSION}"
    )


def canonicalize_json(data: Any) -> bytes:
    """Serializes arbitrary structured data into canonical UTF-8 bytes per OSIRIS-CANONICAL-JSON-V1."""
    if is_dataclass(data) and not isinstance(data, type):
        data = asdict(data)

    _validate_types_recursive(data)

    encoded = json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return encoded.encode("utf-8")


def canonical_sha256(payload: bytes | str | Any) -> str:
    """Computes a sha256:<hex> digest over canonical bytes or raw input."""
    if isinstance(payload, bytes):
        raw = payload
    elif isinstance(payload, str):
        raw = payload.encode("utf-8")
    else:
        raw = canonicalize_json(payload)
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"
