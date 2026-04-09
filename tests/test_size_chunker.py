from __future__ import annotations

import uuid

import pytest

from docprep.chunkers.size import SizeChunker
from docprep.exceptions import ChunkError
from docprep.models.domain import Chunk, Document, Section


def _section(content_markdown: str, *, heading_path: tuple[str, ...] = ()) -> Section:
    document_id = uuid.uuid4()
    return Section(
        id=uuid.uuid4(),
        document_id=document_id,
        order_index=0,
        heading_path=heading_path,
        lineage=tuple(str(uuid.uuid4()) for _ in heading_path),
        content_markdown=content_markdown,
    )


def _document(sections: tuple[Section, ...], *, chunks: tuple[Chunk, ...] = ()) -> Document:
    return Document(
        id=sections[0].document_id if sections else uuid.uuid4(),
        source_uri="docs/example.md",
        title="Example",
        source_checksum="checksum",
        sections=sections,
        chunks=chunks,
    )


def test_short_sections_stay_as_single_chunk() -> None:
    section = _section("short body", heading_path=("Intro",))

    chunked = SizeChunker(max_chars=50).chunk(_document((section,)))

    assert len(chunked.chunks) == 1
    assert chunked.chunks[0].content_text == "short body"
    assert chunked.chunks[0].heading_path == ("Intro",)


def test_long_sections_split_at_paragraph_boundaries() -> None:
    text = "A" * 15 + "\n\n" + "B" * 15
    section = _section(text)

    chunked = SizeChunker(max_chars=20).chunk(_document((section,)))

    assert [chunk.content_text for chunk in chunked.chunks] == ["A" * 15, "B" * 15]


def test_split_at_newline_when_no_paragraph_break_fits() -> None:
    text = "A" * 10 + "\n" + "B" * 10
    section = _section(text)

    chunked = SizeChunker(max_chars=12).chunk(_document((section,)))

    assert [chunk.content_text for chunk in chunked.chunks] == ["A" * 10, "B" * 10]


def test_split_at_sentence_when_no_newline_fits() -> None:
    text = "First sentence. Second sentence."
    section = _section(text)

    chunked = SizeChunker(max_chars=20).chunk(_document((section,)))

    assert [chunk.content_text for chunk in chunked.chunks] == [
        "First sentence.",
        "Second sentence.",
    ]


def test_hard_split_at_max_chars_as_last_resort() -> None:
    text = "abcdefghij"
    section = _section(text)

    chunked = SizeChunker(max_chars=4).chunk(_document((section,)))

    assert [chunk.content_text for chunk in chunked.chunks] == ["abcd", "efgh", "ij"]


def test_raises_if_document_has_no_sections() -> None:
    document = Document(
        id=uuid.uuid4(),
        source_uri="docs/example.md",
        title="Example",
        source_checksum="checksum",
    )

    with pytest.raises(ChunkError, match="no sections"):
        _ = SizeChunker().chunk(document)


def test_raises_if_document_already_has_chunks() -> None:
    section = _section("body")
    existing_chunk = Chunk(
        id=uuid.uuid4(),
        document_id=section.document_id,
        section_id=section.id,
        order_index=0,
        section_chunk_index=0,
        content_text="body",
    )

    with pytest.raises(ChunkError, match="already has chunks"):
        _ = SizeChunker().chunk(_document((section,), chunks=(existing_chunk,)))


def test_custom_max_chars_is_applied() -> None:
    section = _section("abcde")

    chunked = SizeChunker(max_chars=2).chunk(_document((section,)))

    assert [chunk.content_text for chunk in chunked.chunks] == ["ab", "cd", "e"]


def test_max_chars_less_than_one_raises_value_error() -> None:
    with pytest.raises(ValueError, match="max_chars"):
        _ = SizeChunker(max_chars=0)
