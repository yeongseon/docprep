from __future__ import annotations

import uuid

import pytest

from docprep.chunkers.heading import HeadingChunker
from docprep.exceptions import ChunkError
from docprep.models.domain import Document, Section


def _document(body_markdown: str, *, sections: tuple[Section, ...] = ()) -> Document:
    return Document(
        id=uuid.uuid4(),
        source_uri="docs/example.md",
        title="Example",
        source_checksum="checksum",
        body_markdown=body_markdown,
        sections=sections,
    )


def test_document_with_multiple_headings_creates_sections_correctly() -> None:
    document = _document("# One\nAlpha\n## Two\nBeta\n# Three\nGamma")

    chunked = HeadingChunker().chunk(document)

    assert [section.heading for section in chunked.sections] == ["One", "Two", "Three"]
    assert [section.content_markdown for section in chunked.sections] == ["Alpha", "Beta", "Gamma"]


def test_root_section_created_for_content_before_first_heading() -> None:
    document = _document("Intro\n\n# One\nAlpha")

    chunked = HeadingChunker().chunk(document)

    assert chunked.sections[0].heading is None
    assert chunked.sections[0].heading_level == 0
    assert chunked.sections[0].anchor == "__root__"
    assert chunked.sections[0].content_markdown == "Intro"


def test_no_root_section_when_document_starts_with_heading() -> None:
    document = _document("# One\nAlpha")

    chunked = HeadingChunker().chunk(document)

    assert all(section.heading is not None for section in chunked.sections)


def test_nested_headings_build_heading_path_and_lineage() -> None:
    document = _document("# One\nAlpha\n## Two\nBeta\n### Three\nGamma\n## Four\nDelta")

    chunked = HeadingChunker().chunk(document)

    assert chunked.sections[1].heading_path == ("One", "Two")
    assert chunked.sections[2].heading_path == ("One", "Two", "Three")
    assert chunked.sections[3].heading_path == ("One", "Four")
    assert chunked.sections[2].parent_id == chunked.sections[1].id
    assert chunked.sections[2].lineage == (
        "one",
        "one/two",
        "one/two/three",
    )


def test_empty_body_returns_document_unchanged() -> None:
    document = _document("   \n\n")

    assert HeadingChunker().chunk(document) == document


def test_raises_if_document_already_has_sections() -> None:
    existing = Section(id=uuid.uuid4(), document_id=uuid.uuid4(), order_index=0)
    document = _document("# One", sections=(existing,))

    with pytest.raises(ChunkError, match="already has sections"):
        _ = HeadingChunker().chunk(document)


def test_single_heading_creates_single_section() -> None:
    document = _document("# One\nAlpha")

    chunked = HeadingChunker().chunk(document)

    assert len(chunked.sections) == 1
    assert chunked.sections[0].heading == "One"


def test_no_headings_creates_single_root_section() -> None:
    document = _document("Alpha\nBeta")

    chunked = HeadingChunker().chunk(document)

    assert len(chunked.sections) == 1
    assert chunked.sections[0].heading is None
    assert chunked.sections[0].content_markdown == "Alpha\nBeta"
