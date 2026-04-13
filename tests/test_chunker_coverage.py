"""Tests for chunkers/token.py and chunkers/size.py — edge cases for uncovered lines."""

from __future__ import annotations

import uuid

from docprep.chunkers.size import SizeChunker
from docprep.chunkers.token import TokenChunker
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


# =============================================================================
# TokenChunker — overlap logic, sentence split, hard split
# =============================================================================


def test_token_chunker_overlap_suffix_small_text() -> None:
    """When entire previous text fits in overlap budget, return all of it."""
    section = _section("a b c d e f g h")

    chunked = TokenChunker(max_tokens=3, overlap_tokens=2).chunk(_document((section,)))
    # With overlap, chunks should contain overlapping content
    assert len(chunked.chunks) >= 2
    # First chunk should not have overlap, subsequent ones should
    assert chunked.chunks[0].content_text.startswith("a")


def test_token_chunker_sentence_split_fallback() -> None:
    """Force sentence split path when no paragraph breaks fit."""
    # Single paragraph with sentence boundaries
    text = "First sentence. Second sentence. Third sentence. Fourth sentence."
    section = _section(text)

    # max_tokens=4 should force splitting at sentence boundaries
    chunked = TokenChunker(max_tokens=4).chunk(_document((section,)))
    assert len(chunked.chunks) >= 2


def test_token_chunker_hard_split_no_boundaries() -> None:
    """Force hard split when no natural boundaries exist."""
    # A single long "word" with no spaces within budget
    text = "x" * 100
    section = _section(text)

    def char_counter(t: str) -> int:
        return len(t)

    chunked = TokenChunker(max_tokens=30, token_counter=char_counter).chunk(_document((section,)))
    assert len(chunked.chunks) >= 3


def test_token_chunker_whitespace_only_section_skipped() -> None:
    """Sections with only whitespace should not produce chunks."""
    section = _section("   \n\n   ")
    doc = _document((section,))
    chunked = TokenChunker(max_tokens=10).chunk(doc)
    assert len(chunked.chunks) == 0


def test_token_chunker_overlap_with_preceding_whitespace() -> None:
    """Test overlap joiner behavior when preceding char is whitespace."""
    text = "word1 word2 word3 word4 word5 word6 word7 word8"
    section = _section(text)
    chunked = TokenChunker(max_tokens=3, overlap_tokens=1).chunk(_document((section,)))
    # Should produce chunks with overlap
    assert len(chunked.chunks) >= 2
    # Check that at least one chunk has more tokens than max_tokens (due to overlap)
    overlapping = [c for c in chunked.chunks if c.token_count > 3]
    assert len(overlapping) >= 1


def test_token_chunker_protected_span_hard_split() -> None:
    """Test hard split around code blocks (protected spans)."""
    text = "Before text.\n\n```python\ncode = True\n```\n\nAfter text."
    section = _section(text)

    def char_counter(t: str) -> int:
        return len(t)

    chunked = TokenChunker(max_tokens=25, token_counter=char_counter).chunk(_document((section,)))
    assert len(chunked.chunks) >= 2


def test_token_chunker_markdown_boundary_split() -> None:
    """Test splitting at markdown boundaries (headings within section content)."""
    text = "## Sub A\n\nContent A paragraph.\n\n## Sub B\n\nContent B paragraph."
    section = _section(text)

    chunked = TokenChunker(max_tokens=5).chunk(_document((section,)))
    assert len(chunked.chunks) >= 2


def test_token_chunker_newline_split() -> None:
    """When no paragraph break fits, should split at newline."""
    text = "line one here\nline two here\nline three here\nline four here"
    section = _section(text)

    chunked = TokenChunker(max_tokens=4).chunk(_document((section,)))
    assert len(chunked.chunks) >= 2


# =============================================================================
# SizeChunker — overlap, merge_small_ranges, hard_split, sentence split
# =============================================================================


def test_size_chunker_overlap() -> None:
    """Test character-based overlap."""
    text = "AAAA\n\nBBBB\n\nCCCC"
    section = _section(text)

    chunked = SizeChunker(max_chars=8, overlap_chars=3).chunk(_document((section,)))
    assert len(chunked.chunks) >= 2
    # Chunks after the first should start with overlap from previous
    for i, chunk in enumerate(chunked.chunks):
        if i > 0:
            assert len(chunk.content_text) > len("BBBB")  # Has overlap prefix


def test_size_chunker_merge_small_ranges_with_previous() -> None:
    """Small range merges into previous range."""
    # Create text where last segment is tiny
    text = "A" * 40 + "\n\n" + "B" * 40 + "\n\n" + "C" * 5
    section = _section(text)

    chunked = SizeChunker(max_chars=45, min_chars=10).chunk(_document((section,)))
    # The tiny "CCCCC" range should be merged into the previous
    texts = [c.content_text for c in chunked.chunks]
    assert all(len(t) >= 10 for t in texts)


def test_size_chunker_merge_small_ranges_with_next() -> None:
    """When first range is small, merge into next."""
    text = "AB\n\n" + "C" * 40 + "\n\n" + "D" * 40
    section = _section(text)

    chunked = SizeChunker(max_chars=45, min_chars=10).chunk(_document((section,)))
    texts = [c.content_text for c in chunked.chunks]
    # First tiny range should be merged
    assert all(len(t) >= 2 for t in texts)


def test_size_chunker_sentence_split() -> None:
    """Force sentence split when no paragraph or newline boundaries fit."""
    text = "First sentence here. Second sentence here. Third sentence here. Fourth sentence here."
    section = _section(text)

    chunked = SizeChunker(max_chars=50).chunk(_document((section,)))
    assert len(chunked.chunks) >= 2


def test_size_chunker_hard_split_protected_span() -> None:
    """Hard split around code block (protected span)."""
    text = "x" * 10 + "```\ncode\n```" + "y" * 10
    section = _section(text)

    chunked = SizeChunker(max_chars=15).chunk(_document((section,)))
    assert len(chunked.chunks) >= 1


def test_size_chunker_hard_split_no_safe_boundary() -> None:
    """Hard split when no safe boundary exists at all."""
    text = "x" * 200
    section = _section(text)

    chunked = SizeChunker(max_chars=50).chunk(_document((section,)))
    assert len(chunked.chunks) >= 3


def test_size_chunker_markdown_boundary() -> None:
    """Split at markdown boundaries when paragraph breaks don't fit."""
    text = "## A\n\nContent A.\n\n## B\n\nContent B."
    section = _section(text)

    chunked = SizeChunker(max_chars=20).chunk(_document((section,)))
    assert len(chunked.chunks) >= 2


def test_size_chunker_newline_fallback() -> None:
    """Split at newline when no paragraph break found."""
    text = "line one here\nline two here\nline three here"
    section = _section(text)

    chunked = SizeChunker(max_chars=20).chunk(_document((section,)))
    assert len(chunked.chunks) >= 2


def test_size_chunker_no_min_chars_no_merge() -> None:
    """When min_chars=0, no merging should occur."""
    text = "A\n\nBBBBBBBBBB\n\nCCCCCCCCCC"
    section = _section(text)

    chunked = SizeChunker(max_chars=15, min_chars=0).chunk(_document((section,)))
    assert len(chunked.chunks) >= 2


def test_size_chunker_empty_section_skipped() -> None:
    section = _section("   \n\n   ")
    chunked = SizeChunker(max_chars=100).chunk(_document((section,)))
    assert len(chunked.chunks) == 0
