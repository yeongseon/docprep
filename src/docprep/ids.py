"""Deterministic ID generation and checksum utilities.

Identity model v2: anchor-based.
- Section identity: hierarchical parent-scoped path anchors
- Chunk identity: section_anchor + content_hash
- IDENTITY_VERSION tracks breaking changes to ID generation
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import re
import unicodedata
import uuid

# Docprep namespace for UUIDv5 - generated once, stable forever.
DOCPREP_NAMESPACE = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")

# Bump when any ID-generation logic changes. Sinks should re-ingest when version differs.
IDENTITY_VERSION = 2

# Schema version for database tables and export contracts.
# Bump when table structure, field names, or export shape changes.
SCHEMA_VERSION = 1

# Root section anchor constant
ROOT_ANCHOR = "__root__"

_SLUG_COLLAPSE_RE = re.compile(r"[^a-z0-9]+")


def normalize_heading(text: str) -> str:
    """Normalize heading text to a URL-safe slug.

    - NFKC normalize
    - casefold
    - collapse non-alphanumeric runs to `-`
    - trim leading/trailing `-`
    - fallback to "section" if empty

    Preserves Unicode letters and digits (CJK, Korean, etc).
    """
    normalized = unicodedata.normalize("NFKC", text).casefold()
    slug = re.sub(r"[^\w]+", "-", normalized, flags=re.UNICODE)
    slug = slug.strip("-")
    return slug if slug else "section"


def section_anchor(
    heading: str | None,
    parent_anchor: str,
    sibling_counts: dict[tuple[str, str], int],
) -> str:
    """Build a hierarchical parent-scoped section anchor.

    Rules:
    - Root section (heading=None): returns ROOT_ANCHOR
    - Top-level (parent is ROOT_ANCHOR): just the slug, e.g. "intro"
    - Nested: parent/slug, e.g. "intro/install"
    - Duplicates within same parent: append ~N, e.g. "intro/install~2"

    `sibling_counts` is mutated: maps (parent_anchor, normalized_slug) -> seen count.
    """
    if heading is None:
        return ROOT_ANCHOR

    slug = normalize_heading(heading)
    key = (parent_anchor, slug)

    count = sibling_counts.get(key, 0) + 1
    sibling_counts[key] = count

    if parent_anchor == ROOT_ANCHOR:
        base = slug
    else:
        base = f"{parent_anchor}/{slug}"

    if count > 1:
        return f"{base}~{count}"
    return base


def document_id(source_uri: str) -> uuid.UUID:
    """Generate a deterministic document ID from a source URI."""
    return uuid.uuid5(DOCPREP_NAMESPACE, source_uri)


def section_id(doc_id: uuid.UUID, anchor: str) -> uuid.UUID:
    """Generate a deterministic section ID from document ID and anchor."""
    return uuid.uuid5(DOCPREP_NAMESPACE, f"{doc_id}:section:{anchor}")


def chunk_id(doc_id: uuid.UUID, chunk_anchor: str) -> uuid.UUID:
    """Generate a deterministic chunk ID from document ID and chunk anchor."""
    return uuid.uuid5(DOCPREP_NAMESPACE, f"{doc_id}:chunk:{chunk_anchor}")


def content_hash(text: str) -> str:
    """Compute truncated SHA-256 hex digest (16 chars) for change detection."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def chunk_anchor(
    sect_anchor: str,
    chunk_content_hash: str,
    dup_counts: dict[tuple[str, str], int],
) -> str:
    """Build a chunk anchor from section anchor + content hash.

    Format: section_anchor:content_hash, with ~N for duplicate identical texts.
    dup_counts is mutated: maps (section_anchor, content_hash) -> seen count.
    """
    key = (sect_anchor, chunk_content_hash)
    count = dup_counts.get(key, 0) + 1
    dup_counts[key] = count

    base = f"{sect_anchor}:{chunk_content_hash}"
    if count > 1:
        return f"{base}~{count}"
    return base


def canonicalize_source_uri(
    file_path: str | Path,
    source_root: str | Path | None = None,
) -> str:
    """Canonicalize a file-based source URI for stable identity.

    Rules:
    1. Resolve symlinks to real path
    2. If source_root is provided, make path relative to it (forward-slash separated)
    3. If no source_root, use resolved absolute POSIX path
    4. Normalize: no './' prefix, no trailing '/', forward slashes only
    5. Prefix with 'file:' scheme

    Returns a canonical URI string like 'file:docs/guide.md' or 'file:/absolute/path.md'.
    """
    from pathlib import Path as PathCls

    p = PathCls(file_path).resolve()

    if source_root is not None:
        root = PathCls(source_root).resolve()
        try:
            rel = p.relative_to(root)
            return f"file:{rel.as_posix()}"
        except ValueError:
            pass

    return f"file:{p.as_posix()}"


def sha256_checksum(content: str) -> str:
    """Compute full SHA-256 hex digest of a string."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
