"""Deterministic canonical serialization and hashing: OSIRIS-CANONICAL-JSON-V1.

Specification:
1. Encoding: UTF-8 only.
2. Byte-order mark: Forbidden.
3. Whitespace: No insignificant whitespace outside JSON string literals.
4. Object members: Sorted recursively using lexicographic ASCII code-point order.
5. Arrays: Preserve supplied element order exactly.
6. Object keys: Strings only, ASCII-only; unique (duplicates rejected before canonicalization).
7. Strings: Valid Unicode strings subject to Unicode NFC normalization; no bidi controls.
8. Booleans: Only lowercase JSON literals 'true' and 'false'.
9. Null: Only lowercase JSON literal 'null' if schema permits.
10. Integers: Exact base-10 JSON integer spelling, no leading plus, decimal point, or exponent.
11. Floats: Strictly rejected.
12. NaN / Infinity: Strictly rejected.
13. Trailing newline: Forbidden.
14. Content identifier: SHA-256(canonical_bytes) is a binding digest, not a signature.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
import hashlib
import json
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple
import unicodedata

from .errors import SchemaValidationError

CANONICALIZATION_VERSION = "OSIRIS-CANONICAL-JSON-V1"

# Forbidden Unicode Bidirectional control codepoints
BIDI_CONTROL_CODEPOINTS = {
    0x200E,  # Left-to-Right Mark (LRM)
    0x200F,  # Right-to-Left Mark (RLM)
    0x202A,  # Left-to-Right Embedding (LRE)
    0x202B,  # Right-to-Left Embedding (RLE)
    0x202C,  # Pop Directional Formatting (PDF)
    0x202D,  # Left-to-Right Override (LRO)
    0x202E,  # Right-to-Left Override (RLO)
    0x2066,  # Left-to-Right Isolate (LRI)
    0x2067,  # Right-to-Left Isolate (RLI)
    0x2068,  # First Strong Isolate (FSI)
    0x2069,  # Pop Directional Isolate (PDI)
}


def _reject_duplicate_keys(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
    """Custom object_pairs_hook for json.loads that strictly forbids duplicate keys."""
    res: Dict[str, Any] = {}
    for key, value in pairs:
        if key in res:
            raise SchemaValidationError(f"DUPLICATE_KEY: Duplicate object key '{key}' detected in JSON payload.")
        res[key] = value
    return res


def _reject_float(val: str) -> None:
    """Raises SchemaValidationError immediately upon encountering any float literal."""
    raise SchemaValidationError(
        f"FLOAT_FORBIDDEN: Floats are prohibited in {CANONICALIZATION_VERSION}. "
        f"Encountered float token '{val}'. Use exact integers or fixed-point representations."
    )


def _reject_constant(val: str) -> None:
    """Raises SchemaValidationError upon encountering NaN, Infinity, or -Infinity."""
    raise SchemaValidationError(
        f"CONSTANT_FORBIDDEN: Constant '{val}' is prohibited in {CANONICALIZATION_VERSION}."
    )


def strict_parse_json(raw: bytes | str) -> Any:
    """Strict JSON parser enforcing OSIRIS-CANONICAL-JSON-V1 parser rules:
    
    1. Rejects BOM (Byte Order Mark).
    2. Rejects invalid UTF-8.
    3. Rejects duplicate object keys.
    4. Rejects float numbers, NaN, and Infinity.
    5. Rejects trailing non-whitespace data after the root object/array.
    """
    if isinstance(raw, bytes):
        if raw.startswith(b"\xef\xbb\xbf"):
            raise SchemaValidationError(f"BOM_FORBIDDEN: Byte Order Mark (BOM) is forbidden in {CANONICALIZATION_VERSION}.")
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as e:
            raise SchemaValidationError(f"INVALID_UTF8: Raw payload is not valid UTF-8: {e}")
    elif isinstance(raw, str):
        if raw.startswith("\ufeff"):
            raise SchemaValidationError(f"BOM_FORBIDDEN: Byte Order Mark (BOM) is forbidden in {CANONICALIZATION_VERSION}.")
        text = raw
    else:
        raise SchemaValidationError(f"UNSUPPORTED_INPUT: Expected bytes or str, got {type(raw).__name__}")

    decoder = json.JSONDecoder(
        object_pairs_hook=_reject_duplicate_keys,
        parse_float=_reject_float,
        parse_constant=_reject_constant,
    )

    stripped = text.strip()
    if not stripped:
        raise SchemaValidationError("EMPTY_PAYLOAD: JSON payload cannot be empty.")

    obj, idx = decoder.raw_decode(stripped)
    trailing = stripped[idx:].strip()
    if trailing:
        raise SchemaValidationError(f"TRAILING_DATA: Unexpected trailing data after root token: '{trailing[:32]}'")

    return obj


def enforce_unicode_policy(value: Any, path: str = "root") -> Any:
    """Recursively validates and applies the OSIRIS Unicode Policy:
    
    1. Schema & Object Keys: Must be ASCII-only.
    2. Free-text strings: Must be normalized to Unicode NFC.
    3. Control characters: ASCII < 32 forbidden (newlines/tabs already parsed from JSON escapes).
    4. Bidirectional controls: Strictly forbidden.
    """
    if isinstance(value, str):
        # Check bidi controls and forbidden control characters
        for ch in value:
            cp = ord(ch)
            if cp in BIDI_CONTROL_CODEPOINTS:
                raise SchemaValidationError(
                    f"BIDI_CONTROL_FORBIDDEN: Bidirectional control character U+{cp:04X} forbidden at '{path}'."
                )
            if cp < 32 and ch not in ("\t", "\n", "\r"):
                raise SchemaValidationError(
                    f"CONTROL_CHAR_FORBIDDEN: Unescaped control character U+{cp:04X} forbidden at '{path}'."
                )
        return unicodedata.normalize("NFC", value)

    if isinstance(value, (list, tuple)):
        return [enforce_unicode_policy(item, f"{path}[{idx}]") for idx, item in enumerate(value)]

    if isinstance(value, (dict, Mapping)):
        normalized_dict = {}
        for k, v in value.items():
            if not isinstance(k, str):
                raise SchemaValidationError(f"MAPPING_KEY_NOT_STR: Key at '{path}' must be str, got {type(k).__name__}")
            if not k.isascii():
                raise SchemaValidationError(
                    f"KEY_NOT_ASCII: Object key '{k}' at '{path}' must be ASCII-only per unicode policy."
                )
            for ch in k:
                cp = ord(ch)
                if cp < 32:
                    raise SchemaValidationError(f"KEY_CONTROL_CHAR: Control character in key '{k}' at '{path}'.")
            normalized_dict[k] = enforce_unicode_policy(v, f"{path}.{k}")
        return normalized_dict

    if is_dataclass(value) and not isinstance(value, type):
        return enforce_unicode_policy(asdict(value), path)

    return value


def _validate_types_recursive(value: Any, path: str = "root") -> None:
    """Validates that value contains only allowed canonical types."""
    if value is None:
        return
    if isinstance(value, bool):
        return
    if isinstance(value, float):
        raise SchemaValidationError(
            f"FLOAT_FORBIDDEN: Floats are prohibited in {CANONICALIZATION_VERSION} at '{path}'. "
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
                    f"MAPPING_KEY_NOT_STR: Mapping key must be str in {CANONICALIZATION_VERSION} at '{path}', got {type(k).__name__}"
                )
            _validate_types_recursive(v, f"{path}.{k}")
        return

    raise SchemaValidationError(
        f"UNSUPPORTED_TYPE: Unsupported type '{type(value).__name__}' at '{path}' in {CANONICALIZATION_VERSION}"
    )


def canonicalize_json(data: Any, apply_unicode_normalization: bool = True) -> bytes:
    """Serializes arbitrary structured data into canonical UTF-8 bytes per OSIRIS-CANONICAL-JSON-V1."""
    if is_dataclass(data) and not isinstance(data, type):
        data = asdict(data)

    if apply_unicode_normalization:
        data = enforce_unicode_policy(data)

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
    """Computes a sha256:<hex> content-binding digest over canonical bytes or raw input.
    
    Invariant:
    SHA-256(canonical_bytes) provides content identifier binding.
    It is NOT an electronic signature, nor an authorization.
    """
    if isinstance(payload, bytes):
        raw = payload
    elif isinstance(payload, str):
        raw = payload.encode("utf-8")
    else:
        raw = canonicalize_json(payload)
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


def normalize_and_canonicalize(
    raw: bytes | str,
    schema_validator: Optional[Callable[[Any], None]] = None,
) -> Tuple[bytes, str]:
    """Executes the full 7-stage normalization and canonicalization pipeline:
    
    1. Strict parse with duplicate-key & float detection.
    2. Schema validation & unknown field rejection (if schema_validator provided).
    3. Semantic type restrictions & Unicode policy enforcement (NFC, ASCII keys, no bidi).
    4. Recursive canonical serialization (sorted keys, preserved array order, whitespace-free).
    5. Generation of UTF-8 canonical bytes.
    6. Computation of SHA-256 request digest.
    7. Returns (canonical_bytes, digest).
    """
    parsed = strict_parse_json(raw)
    if schema_validator is not None:
        schema_validator(parsed)
    normalized = enforce_unicode_policy(parsed)
    canonical_bytes = canonicalize_json(normalized, apply_unicode_normalization=False)
    digest = canonical_sha256(canonical_bytes)
    return canonical_bytes, digest
