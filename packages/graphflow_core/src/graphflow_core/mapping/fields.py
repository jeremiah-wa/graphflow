"""Source-field resolution and type coercion.

The mapper resolves source fields named in :class:`NodeMapping` /
:class:`RelationshipMapping` against a :class:`ParsedRecord.data`
dictionary, then coerces the raw value to the
:class:`PropertyType` declared in the ontology.

Coercion rules are intentionally conservative: each accepted shape is
documented and explicit. Unknown or ambiguous shapes (for example a
boolean expressed as ``"yes"``) raise :class:`FieldCoercionError`
instead of guessing.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from graphflow_core.manifests.ontology import PropertyType


class FieldCoercionError(ValueError):
    """Raised when a raw source value cannot be coerced to a property type."""


def read_source_field(data: dict[str, Any], field: str) -> Any:
    """Return ``data[field]`` or raise :class:`KeyError` if absent.

    Whitespace-only string values are treated as missing and raise
    :class:`KeyError` to keep mapping behaviour consistent between CSV
    (which produces ``""`` for blanks) and JSON (which produces
    ``null``).
    """
    if field not in data:
        raise KeyError(field)
    value = data[field]
    if value is None:
        raise KeyError(field)
    if isinstance(value, str) and value.strip() == "":
        raise KeyError(field)
    return value


_TRUE_TOKENS = frozenset({"true", "1"})
_FALSE_TOKENS = frozenset({"false", "0"})


def coerce_to_property_type(value: Any, property_type: PropertyType) -> Any:
    """Coerce a raw value to the requested ontology property type.

    Strings are stripped before coercion. Numeric/boolean strings are
    accepted in the obvious form ("123", "1.5", "true"/"false"/"1"/"0"
    case-insensitively). Date and datetime strings must be ISO-8601.
    """
    if property_type == "string":
        if isinstance(value, str):
            return value
        return str(value)

    if property_type == "integer":
        if isinstance(value, bool):
            raise FieldCoercionError(f"expected integer, got bool: {value!r}")
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            if not value.is_integer():
                raise FieldCoercionError(f"expected integer, got float: {value!r}")
            return int(value)
        if isinstance(value, str):
            try:
                return int(value.strip())
            except ValueError as exc:
                raise FieldCoercionError(f"could not parse integer: {value!r}") from exc
        raise FieldCoercionError(f"unsupported value for integer: {value!r}")

    if property_type == "float":
        if isinstance(value, bool):
            raise FieldCoercionError(f"expected float, got bool: {value!r}")
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value.strip())
            except ValueError as exc:
                raise FieldCoercionError(f"could not parse float: {value!r}") from exc
        raise FieldCoercionError(f"unsupported value for float: {value!r}")

    if property_type == "boolean":
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            token = value.strip().lower()
            if token in _TRUE_TOKENS:
                return True
            if token in _FALSE_TOKENS:
                return False
            raise FieldCoercionError(f"could not parse boolean: {value!r}")
        raise FieldCoercionError(f"unsupported value for boolean: {value!r}")

    if property_type == "date":
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return date.fromisoformat(value.strip())
            except ValueError as exc:
                raise FieldCoercionError(f"could not parse date: {value!r}") from exc
        raise FieldCoercionError(f"unsupported value for date: {value!r}")

    if property_type == "datetime":
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.strip())
            except ValueError as exc:
                raise FieldCoercionError(f"could not parse datetime: {value!r}") from exc
        raise FieldCoercionError(f"unsupported value for datetime: {value!r}")

    raise FieldCoercionError(  # pragma: no cover - guarded by Literal
        f"unknown property type: {property_type!r}"
    )
