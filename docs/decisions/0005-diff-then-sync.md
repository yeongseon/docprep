# ADR-0005: Diff-then-Sync Pipeline

**Status**: Accepted
**Date**: 2025-04-12
**Deciders**: Core team

## Context

Embedding APIs (OpenAI, Cohere, etc.) charge per token. For a corpus of 10,000 documents where 50 changed, re-embedding all chunks wastes money and time. We needed a pipeline that:

1. Detects which chunks actually changed between ingestion runs.
2. Syncs only the changed records to the store.
3. Exports only changed chunk IDs for downstream vector store updates.

The alternative -- full re-indexing every time -- is simpler but economically impractical at scale.

## Decision

The pipeline computes a **structural diff** between document revisions, then applies only the changes:

1. **Revision tracking**: Each ingestion run creates a `DocumentRevision` snapshot recording section anchors, chunk anchors, and their content hashes.

2. **Diff computation**: `RevisionDiff` compares two revisions of the same document, producing `SectionDelta` and `ChunkDelta` entries. Each delta has a status: `added`, `removed`, `modified`, or `unchanged`. Matching uses anchors (stable identity) and content hashes (change detection).

3. **Selective sync**: The sync engine uses diff results to upsert only added/modified records and delete removed ones. Full-replace remains available as a fallback for the first ingestion or when the identity model version changes.

4. **Changed-only export**: `ExportDelta` produces only the VectorRecordV1 entries that need updating in a downstream vector store, plus a list of deleted chunk IDs for cleanup.

## Consequences

**Easier:**

- Incremental sync reduces embedding costs proportionally to the change volume.
- Revision history provides an audit trail of what changed and when.
- Changed-only export integrates cleanly with vector store upsert/delete APIs.
- The diff is structural (heading/section level), not line-level, so it aligns with how documents are actually chunked.

**Harder:**

- Diff computation adds pipeline complexity and requires storing revision history.
- Anchor-based matching can produce spurious diffs when headings are reordered (anchors shift).
- The first ingestion run has no previous revision, so it always does a full insert.
- Storage overhead increases with revision history (mitigated by `prune_revisions` to cap retained history).
