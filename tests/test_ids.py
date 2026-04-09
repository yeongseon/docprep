from __future__ import annotations

import hashlib
import uuid

from docprep.ids import DOCPREP_NAMESPACE, chunk_id, document_id, section_id, sha256_checksum


def test_document_id_is_deterministic() -> None:
    source_uri = "docs/guide.md"

    assert document_id(source_uri) == document_id(source_uri)
    assert document_id(source_uri) == uuid.uuid5(DOCPREP_NAMESPACE, source_uri)


def test_section_id_is_deterministic() -> None:
    doc_id = uuid.uuid4()

    assert section_id(doc_id, 3) == section_id(doc_id, 3)
    assert section_id(doc_id, 3) == uuid.uuid5(DOCPREP_NAMESPACE, f"{doc_id}:section:3")


def test_chunk_id_is_deterministic() -> None:
    sect_id = uuid.uuid4()

    assert chunk_id(sect_id, 7) == chunk_id(sect_id, 7)
    assert chunk_id(sect_id, 7) == uuid.uuid5(DOCPREP_NAMESPACE, f"{sect_id}:chunk:7")


def test_different_inputs_produce_different_ids() -> None:
    doc_id = uuid.uuid4()
    sect_id = uuid.uuid4()

    assert document_id("a.md") != document_id("b.md")
    assert section_id(doc_id, 1) != section_id(doc_id, 2)
    assert chunk_id(sect_id, 1) != chunk_id(sect_id, 2)


def test_sha256_checksum_returns_expected_hex_digest() -> None:
    content = "hello world"

    assert sha256_checksum(content) == hashlib.sha256(content.encode("utf-8")).hexdigest()
