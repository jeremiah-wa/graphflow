"""Unit tests for source-field resolution and type coercion."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from graphflow_core.mapping import (
    FieldCoercionError,
    coerce_to_property_type,
    read_source_field,
)


def test_read_source_field_returns_value() -> None:
    assert read_source_field({"a": "x"}, "a") == "x"
    assert read_source_field({"a": 0}, "a") == 0


def test_read_source_field_missing_raises_key_error() -> None:
    with pytest.raises(KeyError):
        read_source_field({"a": "x"}, "b")


def test_read_source_field_treats_none_as_missing() -> None:
    with pytest.raises(KeyError):
        read_source_field({"a": None}, "a")


def test_read_source_field_treats_blank_string_as_missing() -> None:
    with pytest.raises(KeyError):
        read_source_field({"a": "   "}, "a")


def test_coerce_string_passes_through_str() -> None:
    assert coerce_to_property_type("hello", "string") == "hello"


def test_coerce_string_stringifies_other_types() -> None:
    assert coerce_to_property_type(42, "string") == "42"


def test_coerce_integer_accepts_int_and_string() -> None:
    assert coerce_to_property_type(7, "integer") == 7
    assert coerce_to_property_type(" 7 ", "integer") == 7


def test_coerce_integer_rejects_float_with_fraction() -> None:
    with pytest.raises(FieldCoercionError):
        coerce_to_property_type(1.5, "integer")


def test_coerce_integer_rejects_bool() -> None:
    with pytest.raises(FieldCoercionError):
        coerce_to_property_type(True, "integer")


def test_coerce_integer_rejects_garbage_string() -> None:
    with pytest.raises(FieldCoercionError):
        coerce_to_property_type("seven", "integer")


def test_coerce_float_accepts_numeric_forms() -> None:
    assert coerce_to_property_type("1.5", "float") == 1.5
    assert coerce_to_property_type(2, "float") == 2.0


def test_coerce_boolean_accepts_known_tokens() -> None:
    assert coerce_to_property_type("true", "boolean") is True
    assert coerce_to_property_type("False", "boolean") is False
    assert coerce_to_property_type("1", "boolean") is True
    assert coerce_to_property_type("0", "boolean") is False


def test_coerce_boolean_rejects_yes_no() -> None:
    with pytest.raises(FieldCoercionError):
        coerce_to_property_type("yes", "boolean")


def test_coerce_date_parses_iso_string() -> None:
    assert coerce_to_property_type("2026-05-03", "date") == date(2026, 5, 3)


def test_coerce_date_rejects_non_iso() -> None:
    with pytest.raises(FieldCoercionError):
        coerce_to_property_type("03/05/2026", "date")


def test_coerce_datetime_parses_iso_string() -> None:
    assert coerce_to_property_type("2026-05-03T12:00:00", "datetime") == datetime(
        2026, 5, 3, 12, 0, 0
    )


def test_coerce_datetime_passes_through_datetime() -> None:
    now = datetime(2026, 5, 3, 12, 0, 0)
    assert coerce_to_property_type(now, "datetime") is now
