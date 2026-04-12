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


def test_overlap_produces_expected_prefix_on_following_chunks() -> None:
    section = _section("abcdefghij")

    chunked = SizeChunker(max_chars=4, overlap_chars=2).chunk(_document((section,)))

    assert [chunk.content_text for chunk in chunked.chunks] == ["abcd", "cdefgh", "ghij"]


def test_overlap_does_not_create_empty_or_overlap_only_chunks() -> None:
    section = _section("abcdef")

    chunked = SizeChunker(max_chars=3, overlap_chars=2).chunk(_document((section,)))

    assert [chunk.content_text for chunk in chunked.chunks] == ["abc", "bcdef"]
    assert all(chunk.content_text.strip() for chunk in chunked.chunks)


def test_min_chars_merges_small_tail_chunk() -> None:
    section = _section("abcdefghi")

    chunked = SizeChunker(max_chars=4, min_chars=2).chunk(_document((section,)))

    assert [chunk.content_text for chunk in chunked.chunks] == ["abcd", "efghi"]


def test_never_splits_inside_fenced_code_block() -> None:
    code = "```python\n" + "x = 1\n" * 20 + "```"
    section = _section(code)

    chunked = SizeChunker(max_chars=40).chunk(_document((section,)))

    assert len(chunked.chunks) == 1
    assert chunked.chunks[0].content_text == code


def test_table_rows_are_not_split_mid_row() -> None:
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

    chunked = SizeChunker(max_chars=35).chunk(_document((section,)))

    assert len(chunked.chunks) >= 2
    assert all(not chunk.content_text.endswith("| row") for chunk in chunked.chunks)
    assert all(not chunk.content_text.startswith("-1 |") for chunk in chunked.chunks)


def test_heading_is_kept_with_first_paragraph() -> None:
    text = "# Title\n\nFirst paragraph stays with heading.\n\nSecond paragraph can split."
    section = _section(text)

    chunked = SizeChunker(max_chars=30).chunk(_document((section,)))

    assert chunked.chunks[0].content_text.startswith("# Title")
    assert "First paragraph" in chunked.chunks[0].content_text


def test_list_item_boundary_is_preferred() -> None:
    text = (
        "- item one has enough text to force split\n"
        "- item two has enough text to force split\n"
        "- item three"
    )
    section = _section(text)

    chunked = SizeChunker(max_chars=45).chunk(_document((section,)))

    assert len(chunked.chunks) >= 2
    assert all(chunk.content_text.startswith("-") for chunk in chunked.chunks)


def test_chunk_char_offsets_match_original_source_boundaries() -> None:
    text = "alpha beta gamma delta"
    section = _section(text)

    chunked = SizeChunker(max_chars=8, overlap_chars=2).chunk(_document((section,)))

    for index, chunk in enumerate(chunked.chunks):
        base = text[chunk.char_start : chunk.char_end]
        assert chunk.char_start < chunk.char_end
        if index == 0:
            assert chunk.content_text == base
        else:
            assert chunk.content_text.endswith(base)


def test_defaults_preserve_previous_chunking_behavior() -> None:
    text = "A" * 10 + "\n\n" + "B" * 10
    section = _section(text)

    chunked = SizeChunker(max_chars=12).chunk(_document((section,)))

    assert [chunk.content_text for chunk in chunked.chunks] == ["A" * 10, "B" * 10]


def test_empty_fenced_block_pathological_case() -> None:
    section = _section("```\n```\n\nTail paragraph")

    chunked = SizeChunker(max_chars=8).chunk(_document((section,)))

    assert any("```\n```" in chunk.content_text for chunk in chunked.chunks)


def test_nested_fence_markers_pathological_case() -> None:
    text = "````\n```python\nprint('inner')\n```\n````\n\nAfter"
    section = _section(text)

    chunked = SizeChunker(max_chars=18).chunk(_document((section,)))

    assert "````" in chunked.chunks[0].content_text
    assert "print('inner')" in chunked.chunks[0].content_text


def test_table_with_no_data_rows_pathological_case() -> None:
    section = _section("| A | B |\n| --- | --- |")

    chunked = SizeChunker(max_chars=8).chunk(_document((section,)))

    assert len(chunked.chunks) >= 1
    assert "| A | B |" in "\n".join(chunk.content_text for chunk in chunked.chunks)


def test_unicode_inside_code_fence_pathological_case() -> None:
    section = _section("```python\nprint('한글 🚀')\n```\n\nAfter")

    chunked = SizeChunker(max_chars=10).chunk(_document((section,)))

    assert any("한글 🚀" in chunk.content_text for chunk in chunked.chunks)


def test_overlap_and_min_chars_validation() -> None:
    with pytest.raises(ValueError, match="overlap_chars"):
        _ = SizeChunker(max_chars=10, overlap_chars=10)
    with pytest.raises(ValueError, match="overlap_chars"):
        _ = SizeChunker(max_chars=10, overlap_chars=-1)
    with pytest.raises(ValueError, match="min_chars"):
        _ = SizeChunker(max_chars=10, min_chars=-1)
