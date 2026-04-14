# ADR-0007: SQLAlchemy as the Canonical Persistence Layer

**Status**: Accepted
**Date**: 2025-04-14
**Deciders**: Core team

## Context

Document ingestion for RAG involves two persistence concerns:

1. **Canonical state** — storing document revisions, section/chunk anchors, content hashes, and run manifests so that the diff engine can compute incremental changes between ingestion runs.
2. **Vector storage** — storing embeddings alongside chunk text and metadata for semantic search.

These two concerns have fundamentally different requirements. Canonical state needs relational integrity: foreign keys between documents, sections, and chunks; revision history with ordered snapshots; transactional upserts with conflict detection. Vector storage needs approximate nearest-neighbor search over high-dimensional embeddings, which relational databases do not optimize for.

A common first instinct is to persist directly to a vector database (Qdrant, Chroma, Weaviate, etc.). This would mean either (a) embedding revision tracking logic into every vector DB client, or (b) losing incremental sync — docprep's core value proposition.

## Decision

SQLAlchemy is the **first-party canonical persistence layer**. It serves as the single source of truth for document state, revision history, and diff computation. Vector database integration is handled at the **export layer**, not the sink layer.

The architecture separates persistence into two layers:

```
Sink (SQLAlchemy)          Export (JSONL / VectorRecordV1)
├── Document rows          ├── Chunk text + metadata
├── Section/Chunk rows     ├── Deterministic IDs
├── Revision history       ├── Changed-only delta
├── Run manifests          └── → Your vector DB
└── Upsert/conflict logic
```

Vector DB sinks are intentionally third-party. A plugin implementing the Sink protocol could persist directly to a vector database, but it would need to independently implement revision tracking to support incremental sync. The recommended pattern is: persist to SQLAlchemy for state tracking, export changed-only records to your vector store.

SQLAlchemy was chosen over raw SQL or a custom ORM because:

- It supports SQLite (zero-config local development) and PostgreSQL (production) with the same code.
- Its ORM layer maps cleanly to the domain model (Document, Section, Chunk rows).
- Session-based transactions provide the atomicity guarantees needed for upsert-or-skip logic.
- It is the most widely adopted Python database toolkit, minimizing adoption friction.

## Consequences

**Easier:**

- Revision tracking, diff computation, and incremental sync all operate on a well-structured relational schema.
- Users get SQLite for local development with zero configuration and PostgreSQL for production with one config change.
- The export layer (VectorRecordV1 → JSONL) provides a clean, DB-agnostic handoff point to any vector store.
- Third-party sink plugins can opt into full persistence without docprep core needing to know about specific vector DBs.

**Harder:**

- Users expecting a built-in Qdrant or Chroma sink must instead use the two-step pattern: ingest → export → load.
- The relational schema requires migration tooling for upgrades (not yet built — planned for Beta).
- SQLAlchemy adds a dependency that pure-vector-DB users might consider unnecessary.
- The separation between sink and export adds a conceptual step that all-in-one tools don't have.
