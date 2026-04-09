from __future__ import annotations

import pytest

from docprep.exceptions import (
    ChunkError,
    DocPrepError,
    IngestError,
    LoadError,
    ParseError,
    SinkError,
)


@pytest.mark.parametrize("exc_type", [LoadError, ParseError, ChunkError, SinkError, IngestError])
def test_all_specific_exceptions_are_subclasses_of_docprep_error(
    exc_type: type[DocPrepError],
) -> None:
    assert issubclass(exc_type, DocPrepError)


def test_docprep_error_is_subclass_of_exception() -> None:
    assert issubclass(DocPrepError, Exception)


@pytest.mark.parametrize(
    "exc",
    [
        DocPrepError("base"),
        LoadError("load"),
        ParseError("parse"),
        ChunkError("chunk"),
        SinkError("sink"),
        IngestError("ingest"),
    ],
)
def test_each_exception_can_be_raised_and_caught(exc: DocPrepError) -> None:
    with pytest.raises(type(exc)):
        raise exc
