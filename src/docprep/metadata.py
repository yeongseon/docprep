"""Metadata normalization and validation for the docprep pipeline."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
import math
from typing import TypeAlias

from docprep.exceptions import MetadataError

JSONScalar: TypeAlias = None | bool | int | float | str
MetadataValue: TypeAlias = JSONScalar | list["MetadataValue"] | dict[str, "MetadataValue"]
Metadata: TypeAlias = dict[str, MetadataValue]

SYSTEM_METADATA_PREFIX = "docprep."


def normalize_metadata(
    metadata: Mapping[str, object] | None,
    *,
    source: str,
    field_name: str,
    allow_reserved_namespace: bool = False,
) -> Metadata:
    if metadata is None:
        return {}
    if not isinstance(metadata, Mapping):
        raise MetadataError(
            f"{source}: {field_name}: expected mapping, got {type(metadata).__name__}"
        )
    result: Metadata = {}
    for key, value in metadata.items():
        if not isinstance(key, str):
            raise MetadataError(
                f"{source}: {field_name}: dict key must be string, got {type(key).__name__}"
            )
        if not allow_reserved_namespace and key.startswith(SYSTEM_METADATA_PREFIX):
            raise MetadataError(
                f"{source}: metadata field '{field_name}.{key}' "
                f"uses reserved prefix '{SYSTEM_METADATA_PREFIX}'"
            )
        result[key] = _normalize_value(value, source=source, path=f"{field_name}.{key}")
    return result


def _normalize_value(value: object, *, source: str, path: str) -> MetadataValue:
    if value is None:
        return None
    # bool before int (bool is subclass of int)
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise MetadataError(
                f"{source}: metadata field '{path}' must be a finite float, got {value!r}"
            )
        return value
    if isinstance(value, str):
        return value
    # datetime before date (datetime is subclass of date)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return [
            _normalize_value(item, source=source, path=f"{path}[{i}]")
            for i, item in enumerate(value)
        ]
    if isinstance(value, Mapping):
        result: dict[str, MetadataValue] = {}
        for k, v in value.items():
            if not isinstance(k, str):
                raise MetadataError(
                    f"{source}: metadata field '{path}': "
                    f"dict key must be string, got {type(k).__name__}"
                )
            if k.startswith(SYSTEM_METADATA_PREFIX):
                raise MetadataError(
                    f"{source}: metadata field '{path}.{k}' "
                    f"uses reserved prefix '{SYSTEM_METADATA_PREFIX}'"
                )
            result[k] = _normalize_value(v, source=source, path=f"{path}.{k}")
        return result
    raise MetadataError(
        f"{source}: metadata field '{path}' has unsupported type '{type(value).__name__}'"
    )
