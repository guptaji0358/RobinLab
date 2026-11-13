"""Minimal, dependency-free JSON schema validation for automation I/O.

Supports the subset LIAS manifests need: object/array/string/number/integer/
boolean/null types, required properties, enum, minimum/maximum and additional
properties. Unknown keywords are ignored rather than treated as errors.
"""

from __future__ import annotations
from typing import Any, Dict, List, Tuple

_TYPE_MAP = {
    "object": dict,
    "array": list,
    "string": str,
    "boolean": bool,
    "null": type(None),
}


class SchemaError(ValueError):
    """Raised when automation input or output does not match its schema."""


def _matches_type(value: Any, expected: str) -> bool:
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected in _TYPE_MAP:
        return isinstance(value, _TYPE_MAP[expected])
    return True


def _validate(value: Any, schema: Dict[str, Any], path: str, errors: List[str]) -> None:
    expected = schema.get("type")
    if isinstance(expected, str) and not _matches_type(value, expected):
        errors.append(f"{path}: expected {expected}, got {type(value).__name__}")
        return

    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: value {value!r} not in enum")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: {value} below minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: {value} above maximum {schema['maximum']}")

    if isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                errors.append(f"{path}: missing required property '{key}'")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in properties:
                    errors.append(f"{path}: unexpected property '{key}'")
        for key, sub_schema in properties.items():
            if key in value and isinstance(sub_schema, dict):
                _validate(value[key], sub_schema, f"{path}.{key}", errors)

    if isinstance(value, list) and isinstance(schema.get("items"), dict):
        for index, item in enumerate(value):
            _validate(item, schema["items"], f"{path}[{index}]", errors)


def is_schema_empty(schema: Dict[str, Any] | None) -> bool:
    return not schema or not schema.get("properties") and not schema.get("required") and not schema.get("type")


def validate_against_schema(data: Any, schema: Dict[str, Any] | None, label: str = "value") -> Tuple[bool, List[str]]:
    """Validate ``data`` and return ``(ok, errors)`` without raising."""
    if is_schema_empty(schema):
        return True, []
    errors: List[str] = []
    _validate(data, schema or {}, label, errors)
    return not errors, errors
