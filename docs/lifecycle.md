# Document Lifecycle

This guide explains how docprep handles documents throughout their lifecycle — from initial ingestion through modification, rename, deletion, and pruning.

## Pipeline Flow

Every ingestion run follows the same pipeline:

```
Source files → Loader → Parser → Chunker(s) → Sink → Checkpoint
```

Each document produces:
- **Sections** — structural units (headings, blocks) with deterministic anchors
- **Chunks** — text segments within sections with deterministic anchors
- **Content hashes** — per-section and per-chunk, derived from content

The **anchor** and **content hash** are the core of docprep's change detection.

## Change Detection (Diff Engine)

docprep detects changes by comparing **anchors** and **content hashes** between two revisions of the same document.

### How It Works

```python
from docprep import compute_diff_from_documents

diff = compute_diff_from_documents(previous_document, current_document)
print(diff.summary)
# DiffSummary(sections_added=1, sections_removed=0, sections_modified=2, ...)
```

For each section and chunk, the diff engine compares `anchor → content_hash` mappings:

| Previous anchor exists? | Hash matches? | Status |
|------------------------|---------------|--------|
| No | — | `added` |
| Yes | Yes | `unchanged` |
| Yes | No | `modified` |
| In previous, not in current | — | `removed` |

The result is a `RevisionDiff` containing:
- `section_deltas` — per-section change status
- `chunk_deltas` — per-chunk change status
- `summary` — aggregate counts (added, modified, removed, unchanged)

### What Triggers Each Status

| Change | Sections | Chunks |
|--------|----------|--------|
| Edit text under a heading | `modified` | `modified` |
| Add a new heading | `added` (new section + chunks) | `added` |
| Remove a heading | `removed` | `removed` |
| Reorder headings (no text change) | `unchanged` | `unchanged` |
| Change heading text | `modified` (anchor changes → old `removed` + new `added`) | same |

> **Key insight**: Anchors are derived from heading text, not position. Reordering headings without changing their text produces no diff.

## Incremental Sync

### Upsert Behavior

When a sink receives a document via `upsert()`:

1. If the document's `source_checksum` matches the stored checksum → **skip** (no work)
2. If the checksum differs or the document is new → **update** (full replace of sections + chunks)

This is a per-document checksum comparison — docprep doesn't re-embed unchanged documents.

### Changed-Only Export

The `docprep export --changed-only` command combines diff detection with export:

```bash
docprep export docs/ --changed-only --db sqlite:///docs.db -o delta.jsonl
```

This exports only `VectorRecordV1` entries for chunks that are `added` or `modified` since the last ingestion. Deleted chunk IDs are listed separately so you can remove them from your vector store.

## Source Deletion

docprep does **not** automatically delete stored documents when source files are removed. Deletion requires explicit action via one of two mechanisms:

### CLI: `docprep prune`

Compares current source files against stored documents, then removes stale entries:

```bash
# Preview what would be pruned (dry run)
docprep prune docs/ --db sqlite:///docs.db --dry-run

# Actually prune
docprep prune docs/ --db sqlite:///docs.db
```

How prune works:

1. Load source files → collect all current source URIs
2. Query stored documents within scope → collect all stored source URIs
3. **Stale URIs** = stored URIs that are in scope but absent from current sources
4. Delete stale documents (with all their sections, chunks, and revisions)

### CLI: `docprep delete`

Deletes a single document by its source URI:

```bash
docprep delete "file:path/to/document.md" --db sqlite:///docs.db
```

### API: `SQLAlchemySink.sync()`

The `sync()` method combines upsert + prune in a single operation:

```python
from docprep.sinks.sqlalchemy import SQLAlchemySink
from docprep.models.domain import DeletePolicy

sink = SQLAlchemySink(engine=engine)
result = sink.sync(
    documents,
    scope=run_scope,
    delete_policy=DeletePolicy.HARD_DELETE,  # default
)

print(result.upsert_result)   # what was updated/skipped
print(result.delete_result)   # what was pruned
```

### Delete Policies

| Policy | Behavior |
|--------|----------|
| `DeletePolicy.HARD_DELETE` | Remove stale documents, sections, chunks, and revisions from the database |
| `DeletePolicy.IGNORE` | Leave stale documents in place (no deletion) |

## Source Rename

docprep has **no rename detection**. A renamed file appears as:

- **Old URI** → stale (removed on next prune)
- **New URI** → added (new document with new ID)

This means chunk IDs change when files are renamed, and the renamed document will be re-embedded from scratch. This is by design: docprep's identity model anchors document IDs to source URIs for determinism.

If you need rename-safe behavior, keep source file paths stable.

## Source Scope

Every ingestion run has a **scope** — the set of source URIs it is authoritative for. Scope prevents prune from deleting documents ingested from a different directory.

```
# Ingesting docs/ only affects docs/ scope
docprep ingest docs/ --db sqlite:///docs.db

# Pruning docs/ will NOT delete documents from notes/
docprep prune docs/ --db sqlite:///docs.db
```

Scope is derived automatically from the source path:

| Source | Derived Scope |
|--------|--------------|
| `docs/` (directory) | All URIs starting with `file:docs/` |
| `docs/guide.md` (file) | Exactly `file:docs/guide.md` |
| Explicit `--scope` flag | Custom prefix |

Stale URI computation: `stale = stored_in_scope - seen_in_current_run`

## Checkpoints (Resumable Ingestion)

Checkpoints enable resumable ingestion for large document sets. They track which source URIs have been successfully processed.

```bash
docprep ingest docs/ --resume
```

### How Checkpoints Work

1. Before processing, check if `(source_uri, source_checksum)` was already completed → **skip**
2. After successful persist, mark the source as completed
3. Checkpoint is saved to `.docprep-checkpoint.json`

### Checkpoint Invalidation

Checkpoints are invalidated when:

- Pipeline configuration changes (loader, parser, or chunker settings)
- Checkpoint file version doesn't match
- Checkpoint file is corrupted or missing

When invalidated, all sources are reprocessed from scratch.

### Checkpoint vs. Sink Skip

These are two independent skip mechanisms:

| Mechanism | When it skips | Scope |
|-----------|--------------|-------|
| **Checkpoint** | Source URI + checksum already processed in this resumed run | Local file (`.docprep-checkpoint.json`) |
| **Sink upsert** | `source_checksum` matches stored checksum in database | Database |

Both can skip independently. A document might be checkpoint-skipped (already processed in a partial run) but still need a sink update (if database was reset).

## Revision History

`SQLAlchemySink` maintains a revision history for each document:

- Each upsert creates a new `DocumentRevision` with an incrementing `revision_number`
- The latest revision is marked `is_current = True`
- Previous revisions are retained for diff computation

### Revision Pruning

To limit storage growth, prune old revisions:

```python
pruned_count = sink.prune_revisions(max_depth=10)
```

This keeps the 10 most recent revisions per document and deletes older ones.

## Lifecycle Summary

```
                    ┌─── ingest ──→ upsert (add/update)
                    │
Source files ──→ Load ──→ Parse ──→ Chunk ──→ Sink
                    │
                    ├─── diff ───→ compare with stored revision
                    │
                    ├─── export ─→ JSONL (full or changed-only)
                    │
                    ├─── prune ──→ delete stale documents
                    │
                    └─── delete ─→ remove specific document

No automatic deletion. Prune is always explicit.
```

## Common Scenarios

### First ingestion
```bash
docprep ingest docs/ --db sqlite:///docs.db
```
All documents are loaded, parsed, chunked, and persisted. No deletions.

### Re-ingestion after edits
```bash
docprep ingest docs/ --db sqlite:///docs.db
```
Only documents with changed checksums are updated. Unchanged documents are skipped by the sink.

### After deleting source files
```bash
# See what's stale
docprep prune docs/ --db sqlite:///docs.db --dry-run

# Remove stale documents
docprep prune docs/ --db sqlite:///docs.db
```

### After renaming source files
Same as deletion + addition. The old URI becomes stale (prune it), and the new URI is added on next ingest.

### Resuming a failed ingestion
```bash
docprep ingest docs/ --db sqlite:///docs.db --resume
```
Skips sources already processed in the partial run.
