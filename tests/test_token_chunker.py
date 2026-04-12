from __future__ import annotations

import uuid

import pytest

from docprep.chunkers.token import TokenChunker
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


def test_basic_token_chunking_uses_pluggable_counter() -> None:
    section = _section("alpha beta gamma delta")

    def counter(text: str) -> int:
        return len(text.split())

    chunked = TokenChunker(max_tokens=2, token_counter=counter).chunk(_document((section,)))

    assert [chunk.content_text for chunk in chunked.chunks] == ["alpha beta", "gamma delta"]
    assert [chunk.token_count for chunk in chunked.chunks] == [2, 2]


def test_token_overlap_uses_token_budget() -> None:
    section = _section("a b c d e")

    chunked = TokenChunker(max_tokens=2, overlap_tokens=1).chunk(_document((section,)))

    assert [chunk.content_text for chunk in chunked.chunks] == ["a b", "b c d", "d e"]
    assert [chunk.token_count for chunk in chunked.chunks] == [2, 3, 2]


def test_default_whitespace_counter_is_used() -> None:
    section = _section("one two three")

    chunked = TokenChunker(max_tokens=1).chunk(_document((section,)))

    assert [chunk.content_text for chunk in chunked.chunks] == ["one", "two", "three"]
    assert [chunk.token_count for chunk in chunked.chunks] == [1, 1, 1]


def test_character_counter_mode() -> None:
    section = _section("abcdef")

    chunked = TokenChunker(max_tokens=2, token_counter=len).chunk(_document((section,)))

    assert [chunk.content_text for chunk in chunked.chunks] == ["ab", "cd", "ef"]
    assert [chunk.token_count for chunk in chunked.chunks] == [2, 2, 2]


def test_markdown_safe_boundaries_are_preserved_for_fences() -> None:
    code = "```python\n" + "x = 1\n" * 12 + "```"
    section = _section(code)

    chunked = TokenChunker(max_tokens=10).chunk(_document((section,)))

    assert len(chunked.chunks) == 1
    assert chunked.chunks[0].content_text == code


def test_markdown_table_rows_are_not_split_mid_row() -> None:
    table = "\n".join(
        [
            "| A | B |",
            "| --- | --- |",
            "| row-1 | value-1 |",
            "| row-2 | value-2 |",
            "| row-3 | value-3 |",
        ]
    )
    section = _section(table)

    chunked = TokenChunker(max_tokens=8).chunk(_document((section,)))

    assert len(chunked.chunks) >= 2
    assert all(not chunk.content_text.endswith("| row") for chunk in chunked.chunks)
    assert all(not chunk.content_text.startswith("-1 |") for chunk in chunked.chunks)


def test_deterministic_chunking_for_same_input() -> None:
    section = _section("alpha beta gamma delta")
    document = _document((section,))
    chunker = TokenChunker(max_tokens=2)

    first = chunker.chunk(document)
    second = chunker.chunk(document)

    assert first.chunks == second.chunks


def test_raises_for_invalid_document_states() -> None:
    empty = Document(
        id=uuid.uuid4(), source_uri="docs/example.md", title="Example", source_checksum="x"
    )
    with pytest.raises(ChunkError, match="no sections"):
        _ = TokenChunker().chunk(empty)

    section = _section("body")
    existing = Chunk(
        id=uuid.uuid4(),
        document_id=section.document_id,
        section_id=section.id,
        order_index=0,
        section_chunk_index=0,
        content_text="body",
    )
    with pytest.raises(ChunkError, match="already has chunks"):
        _ = TokenChunker().chunk(_document((section,), chunks=(existing,)))


def test_overlap_and_max_token_validation() -> None:
    with pytest.raises(ValueError, match="max_tokens"):
        _ = TokenChunker(max_tokens=0)
    with pytest.raises(ValueError, match="overlap_tokens"):
        _ = TokenChunker(max_tokens=10, overlap_tokens=-1)
    with pytest.raises(ValueError, match="overlap_tokens"):
        _ = TokenChunker(max_tokens=10, overlap_tokens=10)
