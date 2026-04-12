from __future__ import annotations

import hashlib
import uuid

from docprep.ids import (
    DOCPREP_NAMESPACE,
    IDENTITY_VERSION,
    ROOT_ANCHOR,
    SCHEMA_VERSION,
    chunk_anchor,
    chunk_id,
    content_hash,
    document_id,
    normalize_heading,
    section_anchor,
    section_id,
    sha256_checksum,
)


def test_normalize_heading_basic_and_special_chars() -> None:
    assert normalize_heading("Hello, World!") == "hello-world"
    assert normalize_heading("A---B___C") == "a-b___c"


def test_normalize_heading_preserves_cjk_and_korean() -> None:
    assert normalize_heading("설치 가이드") == "설치-가이드"
    assert normalize_heading("快速开始 指南") == "快速开始-指南"


def test_normalize_heading_emoji_and_empty_cases() -> None:
    assert normalize_heading("🚀✨") == "section"
    assert normalize_heading("") == "section"
    assert normalize_heading("   \t\n") == "section"


def test_section_anchor_root_top_level_nested_and_duplicates() -> None:
    sibling_counts: dict[tuple[str, str], int] = {}

    assert section_anchor(None, ROOT_ANCHOR, sibling_counts) == ROOT_ANCHOR

    intro = section_anchor("Intro", ROOT_ANCHOR, sibling_counts)
    assert intro == "intro"

    install = section_anchor("Install", intro, sibling_counts)
    assert install == "intro/install"

    install_dup = section_anchor("Install", intro, sibling_counts)
    assert install_dup == "intro/install~2"

    intro_dup = section_anchor("Intro", ROOT_ANCHOR, sibling_counts)
    assert intro_dup == "intro~2"


def test_document_id_is_deterministic() -> None:
    source_uri = "docs/guide.md"

    assert document_id(source_uri) == document_id(source_uri)
    assert document_id(source_uri) == uuid.uuid5(DOCPREP_NAMESPACE, source_uri)


def test_section_id_is_deterministic_from_anchor() -> None:
    doc_id = uuid.uuid4()
    anchor = "intro/install"

    assert section_id(doc_id, anchor) == section_id(doc_id, anchor)
    assert section_id(doc_id, anchor) == uuid.uuid5(
        DOCPREP_NAMESPACE,
        f"{doc_id}:section:{anchor}",
    )


def test_chunk_id_is_deterministic_from_chunk_anchor() -> None:
    doc_id = uuid.uuid4()
    c_anchor = "intro/install:deadbeefdeadbeef"

    assert chunk_id(doc_id, c_anchor) == chunk_id(doc_id, c_anchor)
    assert chunk_id(doc_id, c_anchor) == uuid.uuid5(
        DOCPREP_NAMESPACE,
        f"{doc_id}:chunk:{c_anchor}",
    )


def test_content_hash_is_deterministic_and_truncated() -> None:
    text = "hello world"
    digest = content_hash(text)

    assert digest == content_hash(text)
    assert len(digest) == 16
    assert digest == hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def test_chunk_anchor_basic_and_duplicates() -> None:
    dup_counts: dict[tuple[str, str], int] = {}

    first = chunk_anchor("intro", "0123456789abcdef", dup_counts)
    second = chunk_anchor("intro", "0123456789abcdef", dup_counts)
    other = chunk_anchor("intro", "ffffffffffffffff", dup_counts)

    assert first == "intro:0123456789abcdef"
    assert second == "intro:0123456789abcdef~2"
    assert other == "intro:ffffffffffffffff"


def test_different_inputs_produce_different_ids() -> None:
    doc_id = uuid.uuid4()

    assert document_id("a.md") != document_id("b.md")
    assert section_id(doc_id, "intro") != section_id(doc_id, "usage")
    assert chunk_id(doc_id, "intro:aaaa") != chunk_id(doc_id, "intro:bbbb")


def test_sha256_checksum_returns_expected_hex_digest() -> None:
    content = "hello world"

    assert sha256_checksum(content) == hashlib.sha256(content.encode("utf-8")).hexdigest()


def test_identity_version_is_2() -> None:
    assert IDENTITY_VERSION == 2


def test_schema_version_is_1() -> None:
    assert SCHEMA_VERSION == 1
