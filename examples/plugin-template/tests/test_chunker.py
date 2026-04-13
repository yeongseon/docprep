"""Tests for the sentence chunker plugin."""

from __future__ import annotations

import uuid

from my_docprep_plugin.chunker import SentenceChunker

from docprep.chunkers.protocol import Chunker
from docprep.models.domain import Document, Section


def _make_doc(body: str) -> Document:
    doc_id = uuid.uuid5(uuid.NAMESPACE_DNS, "test")
    return Document(
        id=doc_id,
        source_uri="file:test.md",
        title="Test",
        source_checksum="abc123",
        body_markdown=body,
        sections=(
            Section(
                id=uuid.uuid5(uuid.NAMESPACE_DNS, "s0"),
                document_id=doc_id,
                order_index=0,
                anchor="root",
                content_markdown=body,
            ),
        ),
    )


def test_protocol_conformance() -> None:
    assert isinstance(SentenceChunker(), Chunker)


def test_splits_sentences() -> None:
    doc = _make_doc("First sentence. Second sentence. Third one!")
    result = SentenceChunker().chunk(doc)

    assert len(result.chunks) == 3
    assert result.chunks[0].content_text == "First sentence."
    assert result.chunks[1].content_text == "Second sentence."
    assert result.chunks[2].content_text == "Third one!"


def test_preserves_document_identity() -> None:
    doc = _make_doc("Hello world. Goodbye world.")
    result = SentenceChunker().chunk(doc)

    assert result.id == doc.id
    assert result.source_uri == doc.source_uri
    assert result.sections == doc.sections


def test_deterministic_output() -> None:
    doc = _make_doc("One. Two. Three.")
    chunker = SentenceChunker()

    result1 = chunker.chunk(doc)
    result2 = chunker.chunk(doc)

    assert result1.chunks == result2.chunks


def test_empty_sections_unchanged() -> None:
    doc = Document(
        id=uuid.uuid5(uuid.NAMESPACE_DNS, "empty"),
        source_uri="file:empty.md",
        title="Empty",
        source_checksum="def456",
    )
    result = SentenceChunker().chunk(doc)
    assert result.chunks == ()
