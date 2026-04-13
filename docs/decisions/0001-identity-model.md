# ADR-0001: Identity Model

**Status**: Accepted
**Date**: 2025-04-12
**Deciders**: Core team

## Context

RAG pipelines store chunk embeddings in vector databases. When source documents change, the pipeline needs to re-ingest them. If chunk IDs change on every re-ingest (e.g., because they are derived purely from content), the entire vector store must be replaced -- even if only one paragraph changed.

We needed an identity scheme where:

1. Chunk IDs remain stable across minor edits, enabling incremental sync.
2. Content changes are still detectable, so stale embeddings can be updated.
3. IDs are deterministic -- the same input always produces the same IDs, regardless of when or where the pipeline runs.

## Decision

We adopted a two-part identity model:

- **Anchor** (stable lineage): A UUIDv5 derived from the document's heading structure. Section anchors are built from a normalized heading slug plus a sibling occurrence index (to disambiguate repeated headings). Chunk anchors combine the section anchor with the chunk's position within the section (for example, `intro:chunk_0`). Anchors survive content edits as long as the heading structure doesn't change.

- **Version hash** (change detection): A SHA-256 hash of the chunk's actual content. This changes whenever the text changes, even if the anchor stays the same.

Together, anchor + version_hash let the diff engine answer: "Is this the same logical chunk?" (anchor match) and "Has its content changed?" (hash mismatch).

Key implementation details:

- All UUIDs use UUIDv5 with a fixed docprep namespace (`DOCPREP_NAMESPACE`).
- `IDENTITY_VERSION` is bumped whenever ID generation logic changes, signaling that sinks should re-ingest.
- Root (untitled) sections use a `__root__` sentinel anchor.
- Heading normalization: NFKC, casefold, collapse non-alphanumeric to hyphens, trim.

## Consequences

**Easier:**

- Incremental sync: only chunks whose version_hash changed need re-embedding.
- Stable references: external systems can store chunk IDs as durable links.
- Deterministic: no randomness, no timestamps in IDs.

**Harder:**

- Heading restructuring changes all anchors downstream, triggering a full re-index of affected sections.
- The identity model is more complex than simple content hashing -- contributors must understand the anchor vs. hash distinction.
- Sibling occurrence indexing means inserting a new section with the same heading can shift indices of later siblings.
