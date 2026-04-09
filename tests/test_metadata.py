from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, timezone
import math
from typing import cast

import pytest

from docprep.exceptions import MetadataError
from docprep.metadata import SYSTEM_METADATA_PREFIX, normalize_metadata


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        (False, False),
        (True, True),
        (0, 0),
        (42, 42),
        (1.25, 1.25),
        ("value", "value"),
    ],
)
def test_normalize_metadata_preserves_scalar_values(value: object, expected: object) -> None:
    normalized = normalize_metadata(
        {"field": value},
        source="docs/example.md",
        field_name="frontmatter",
    )

    assert normalized == {"field": expected}


def test_normalize_metadata_normalizes_date_value() -> None:
    normalized = normalize_metadata(
        {"published": date(2024, 1, 15)},
        source="docs/example.md",
        field_name="frontmatter",
    )

    assert normalized == {"published": "2024-01-15"}


def test_normalize_metadata_normalizes_datetime_value() -> None:
    normalized = normalize_metadata(
        {"published_at": datetime(2024, 1, 15, 10, 30, 0)},
        source="docs/example.md",
        field_name="frontmatter",
    )

    assert normalized == {"published_at": "2024-01-15T10:30:00"}


def test_normalize_metadata_preserves_datetime_timezone_offset() -> None:
    normalized = normalize_metadata(
        {"published_at": datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)},
        source="docs/example.md",
        field_name="frontmatter",
    )

    assert normalized == {"published_at": "2024-01-15T10:30:00+00:00"}


def test_normalize_metadata_converts_tuple_to_list() -> None:
    normalized = normalize_metadata(
        {"values": (1, 2, 3)},
        source="docs/example.md",
        field_name="frontmatter",
    )

    assert normalized == {"values": [1, 2, 3]}


def test_normalize_metadata_recursively_normalizes_nested_dict_values() -> None:
    normalized = normalize_metadata(
        {"nested": {"published": date(2024, 1, 15), "items": (1, 2)}},
        source="docs/example.md",
        field_name="frontmatter",
    )

    assert normalized == {"nested": {"published": "2024-01-15", "items": [1, 2]}}


def test_normalize_metadata_recursively_normalizes_nested_list_values() -> None:
    normalized = normalize_metadata(
        {"items": [date(2024, 1, 15), {"published_at": datetime(2024, 1, 15, 10, 30, 0)}]},
        source="docs/example.md",
        field_name="frontmatter",
    )

    assert normalized == {
        "items": [
            "2024-01-15",
            {"published_at": "2024-01-15T10:30:00"},
        ]
    }


def test_normalize_metadata_rejects_reserved_namespace_at_top_level() -> None:
    with pytest.raises(MetadataError, match=rf"reserved prefix '{SYSTEM_METADATA_PREFIX}'"):
        _ = normalize_metadata(
            {"docprep.foo": "value"},
            source="docs/example.md",
            field_name="frontmatter",
        )


def test_normalize_metadata_rejects_reserved_namespace_in_nested_dict() -> None:
    with pytest.raises(MetadataError, match=r"frontmatter\.nested\.docprep\.bar"):
        _ = normalize_metadata(
            {"nested": {"docprep.bar": "value"}},
            source="docs/example.md",
            field_name="frontmatter",
        )


def test_normalize_metadata_rejects_non_string_nested_dict_key_with_source_and_field_path() -> None:
    with pytest.raises(
        MetadataError,
        match=(
            r"docs/example\.md: metadata field 'frontmatter\.nested': "
            r"dict key must be string, got int"
        ),
    ):
        _ = normalize_metadata(
            {"nested": {1: "value"}},
            source="docs/example.md",
            field_name="frontmatter",
        )


def test_normalize_metadata_rejects_set_values_with_type_name() -> None:
    with pytest.raises(MetadataError, match=r"unsupported type 'set'"):
        _ = normalize_metadata(
            {"items": {1, 2, 3}},
            source="docs/example.md",
            field_name="frontmatter",
        )


def test_normalize_metadata_rejects_bytes_values() -> None:
    with pytest.raises(MetadataError, match=r"unsupported type 'bytes'"):
        _ = normalize_metadata(
            {"blob": b"value"},
            source="docs/example.md",
            field_name="frontmatter",
        )


@pytest.mark.parametrize("value", [math.nan, math.inf])
def test_normalize_metadata_rejects_non_finite_floats(value: float) -> None:
    with pytest.raises(MetadataError, match=r"must be a finite float"):
        _ = normalize_metadata(
            {"score": value},
            source="docs/example.md",
            field_name="frontmatter",
        )


def test_normalize_metadata_returns_empty_dict_for_none_input() -> None:
    assert normalize_metadata(None, source="docs/example.md", field_name="frontmatter") == {}


def test_normalize_metadata_rejects_non_mapping_input() -> None:
    invalid_metadata = cast(Mapping[str, object], cast(object, ["not", "a", "mapping"]))

    with pytest.raises(MetadataError, match=r"frontmatter: expected mapping, got list"):
        _ = normalize_metadata(
            invalid_metadata,
            source="docs/example.md",
            field_name="frontmatter",
        )


def test_normalize_metadata_allows_reserved_namespace_when_enabled() -> None:
    normalized = normalize_metadata(
        {"docprep.foo": "value"},
        source="docs/example.md",
        field_name="frontmatter",
        allow_reserved_namespace=True,
    )

    assert normalized == {"docprep.foo": "value"}


def test_normalize_metadata_returns_empty_dict_for_empty_mapping() -> None:
    assert normalize_metadata({}, source="docs/example.md", field_name="frontmatter") == {}


def test_normalize_metadata_error_message_includes_source() -> None:
    with pytest.raises(MetadataError, match=r"source://doc\.md"):
        _ = normalize_metadata(
            {"field": {"value": object()}},
            source="source://doc.md",
            field_name="frontmatter",
        )


def test_normalize_metadata_error_message_includes_full_field_path() -> None:
    with pytest.raises(MetadataError, match=r"frontmatter\.nested\.key"):
        _ = normalize_metadata(
            {"nested": {"key": object()}},
            source="docs/example.md",
            field_name="frontmatter",
        )
