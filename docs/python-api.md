# Python API Reference

This guide covers the public Python API surface. All symbols listed below are importable directly from the `docprep` top-level package.

```python
from docprep import ingest, Ingestor, Document, Chunk, Section
```

## Core Types

### Document

A fully parsed and optionally chunked document.

```python
from docprep import Document

# Fields (all keyword-only, frozen dataclass)
doc.id                      # uuid.UUID — deterministic from source_uri
doc.source_uri              # str — canonical file URI (e.g. "file:docs/guide.md")
doc.title                   # str — extracted title
doc.source_checksum         # str — SHA-256 of raw content
doc.source_type             # str — media type (default: "markdown")
doc.frontmatter             # dict — parsed YAML frontmatter
doc.source_metadata         # dict — loader-supplied metadata
doc.body_markdown           # str — full body text
doc.structural_annotations  # tuple[StructuralAnnotation, ...] — code fences, tables, lists
doc.sections                # tuple[Section, ...] — heading-split sections
doc.chunks                  # tuple[Chunk, ...] — sized text chunks
```

### Section

A heading-delimited section within a document.

```python
from docprep import Section

section.id                  # uuid.UUID — deterministic from document_id + anchor
section.document_id         # uuid.UUID
section.order_index         # int — position in document
section.parent_id           # uuid.UUID | None — parent section
section.heading             # str | None — heading text (None for root)
section.heading_level       # int — 0 for root, 1-6 for headings
section.anchor              # str — hierarchical anchor (e.g. "intro/install")
section.content_hash        # str — truncated SHA-256 for change detection
section.heading_path        # tuple[str, ...] — breadcrumb trail
section.lineage             # tuple[str, ...] — anchor chain to root
section.content_markdown    # str — section body text
```

### Chunk

A sized text chunk derived from a section.

```python
from docprep import Chunk

chunk.id                    # uuid.UUID — deterministic from document_id + anchor
chunk.document_id           # uuid.UUID
chunk.section_id            # uuid.UUID
chunk.order_index           # int — global position across all chunks
chunk.section_chunk_index   # int — position within its section
chunk.anchor                # str — section_anchor:chunk_N (e.g. intro:chunk_0)
chunk.content_hash          # str — truncated SHA-256
chunk.content_text          # str — the actual chunk text
chunk.char_start            # int — character offset in section
chunk.char_end              # int — character end offset
chunk.token_count           # int | None — token count if computed
chunk.heading_path          # tuple[str, ...] — inherited from section
chunk.lineage               # tuple[str, ...] — inherited from section
chunk.structure_types       # tuple[str, ...] — e.g. ("code_fence", "table")
```

## Ingestion

### `ingest()` — Convenience Function

The simplest way to process documents. Creates an `Ingestor` internally and runs it.

```python
from docprep import ingest

result = ingest("docs/")
print(f"Processed: {result.processed_count}")
print(f"Documents: {len(result.documents)}")
```

**Signature:**

```python
def ingest(
    source: str | Path | None = None,
    *,
    config: DocPrepConfig | None = None,
    loader: Loader | None = None,
    parser: Parser | None = None,
    chunkers: Sequence[Chunker] | None = None,
    sink: Sink | None = None,
    scope: SourceScope | None = None,
    logger: logging.Logger | None = None,
    progress_callback: ProgressCallback | None = None,
    error_mode: ErrorMode = ErrorMode.CONTINUE_ON_ERROR,
    workers: int = 1,
    resume: bool = False,
    checkpoint_path: str | Path | None = None,
) -> IngestResult
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `source` | `str \| Path \| None` | `None` | Directory or file path. Falls back to config. |
| `config` | `DocPrepConfig \| None` | `None` | Parsed config object. |
| `loader` | `Loader \| None` | `None` | Custom loader. Defaults based on config. |
| `parser` | `Parser \| None` | `None` | Custom parser. Defaults to `MultiFormatParser`. |
| `chunkers` | `Sequence[Chunker] \| None` | `None` | Custom chunker pipeline. Defaults to heading + size. |
| `sink` | `Sink \| None` | `None` | Persistence backend. `None` = in-memory only. |
| `error_mode` | `ErrorMode` | `CONTINUE_ON_ERROR` | `FAIL_FAST` or `CONTINUE_ON_ERROR`. |
| `workers` | `int` | `1` | Thread pool size for parallel parse+chunk. |
| `resume` | `bool` | `False` | Enable checkpoint-based resumable ingestion. |
| `checkpoint_path` | `str \| Path \| None` | `None` | Custom checkpoint file path. |

### `Ingestor` — Full Control

For more control, instantiate `Ingestor` directly.

```python
from docprep import Ingestor, ErrorMode
from docprep.sinks.sqlalchemy import SQLAlchemySink
from sqlalchemy import create_engine

engine = create_engine("sqlite:///docs.db")
sink = SQLAlchemySink(engine=engine)

ingestor = Ingestor(
    sink=sink,
    error_mode=ErrorMode.FAIL_FAST,
)

result = ingestor.run("docs/", workers=4)
```

**Constructor parameters** are identical to `ingest()` except `source`, `workers`, `resume`, and `checkpoint_path` — those are passed to `run()` instead.

**`Ingestor.run()` signature:**

```python
def run(
    self,
    source: str | Path | None = None,
    workers: int = 1,
    resume: bool = False,
    checkpoint_path: str | Path | None = None,
) -> IngestResult
```

### `IngestResult`

Returned by both `ingest()` and `Ingestor.run()`.

```python
result.documents            # tuple[Document, ...] — successfully processed
result.processed_count      # int
result.skipped_count        # int — unchanged since last run
result.updated_count        # int — upserted to sink
result.deleted_count        # int
result.failed_count         # int
result.skipped_source_uris  # tuple[str, ...]
result.updated_source_uris  # tuple[str, ...]
result.failed_source_uris   # tuple[str, ...]
result.errors               # tuple[DocumentError, ...]
result.stage_reports        # tuple[IngestStageReport, ...] — timing per stage
result.persisted            # bool — whether sink was used
result.sink_name            # str | None
result.run_manifest         # RunManifest | None
```

### Progress Callbacks

Monitor ingestion progress with a callback:

```python
from docprep import ingest, IngestProgressEvent

def on_progress(event: IngestProgressEvent) -> None:
    print(f"[{event.stage}] {event.event}: {event.source_uri or ''}")

result = ingest("docs/", progress_callback=on_progress)
```

`IngestProgressEvent` fields include `stage`, `event`, `source_uri`, `current`, `total`, `elapsed_ms`, and more.

### Resumable Ingestion

For large corpora, enable checkpointing to resume after interruption:

```python
result = ingest("docs/", resume=True, checkpoint_path=".docprep-checkpoint.json")
```

The checkpoint file records which sources have been successfully processed with their checksums. If the pipeline config changes, the checkpoint is automatically invalidated.

## Configuration

### Loading Config

```python
from docprep import load_config, load_discovered_config, DocPrepConfig

# Load from explicit path
config = load_config("docprep.toml")

# Auto-discover by walking up directories
config = load_discovered_config()  # returns None if not found

# Use config with ingest
result = ingest(config=config)
```

### Config Dataclasses

All config types are frozen dataclasses:

| Class | Description |
|-------|-------------|
| `DocPrepConfig` | Top-level config with all sections |
| `FileSystemLoaderConfig` | Multi-format loader with glob patterns |
| `MarkdownLoaderConfig` | Markdown-only loader |
| `AutoParserConfig` | Auto-detect parser by media type |
| `HeadingChunkerConfig` | Split by headings |
| `TokenChunkerConfig` | Token-budget splitting |
| `SizeChunkerConfig` | Character-count splitting |
| `SQLAlchemySinkConfig` | SQLAlchemy database sink |
| `ExportConfig` | Export text prepend and annotation settings |

## Diff Engine

Compare two versions of a document to find structural changes.

### From Documents

```python
from docprep import compute_diff_from_documents

diff = compute_diff_from_documents(previous_doc, current_doc)

print(f"Sections added: {diff.summary.sections_added}")
print(f"Chunks modified: {diff.summary.chunks_modified}")
print(f"Chunks removed: {diff.summary.chunks_removed}")

for delta in diff.chunk_deltas:
    print(f"  {delta.anchor}: {delta.status}")
```

### From IngestResults

```python
from docprep import compute_diff

diff = compute_diff(previous_result, current_result)
```

Both `previous_result` and `current_result` must contain exactly one document with the same `source_uri`.

### RevisionDiff

```python
diff.source_uri             # str
diff.previous_revision      # str — checksum
diff.current_revision       # str — checksum
diff.section_deltas         # tuple[SectionDelta, ...]
diff.chunk_deltas           # tuple[ChunkDelta, ...]
diff.summary                # DiffSummary

# Delta statuses: "added", "modified", "removed", "unchanged"
```

## Export

### Vector Records

Build embedding-ready records from documents:

```python
from docprep import build_vector_records_v1, iter_vector_records_v1, TextPrependStrategy

# Eager (tuple)
records = build_vector_records_v1(result.documents)

# Lazy (iterator) — preferred for large datasets
for record in iter_vector_records_v1(result.documents):
    print(record.text[:80])

# Control text prepend strategy
records = build_vector_records_v1(
    result.documents,
    text_prepend=TextPrependStrategy.HEADING_PATH,
    include_annotations=True,
)
```

### VectorRecordV1 Fields

```python
record.id               # uuid.UUID — same as chunk ID
record.document_id      # uuid.UUID
record.section_id       # uuid.UUID
record.chunk_anchor     # str
record.section_anchor   # str
record.text             # str — with optional title/heading prepend
record.content_hash     # str
record.char_count       # int
record.source_uri       # str
record.title            # str
record.section_path     # tuple[str, ...]
record.schema_version   # int
record.pipeline_version # str — docprep version
record.created_at       # str — ISO 8601 timestamp
record.user_metadata    # dict — merged frontmatter + source metadata
```

### JSONL Export

```python
from docprep.export import iter_vector_records_v1, write_jsonl

with open("records.jsonl", "w") as f:
    count = write_jsonl(iter_vector_records_v1(result.documents), f)
    print(f"Exported {count} records")
```

### Changed-Only Export

Export only chunks that differ from the previous version:

```python
from docprep import build_export_delta

delta = build_export_delta(
    diff_results=(diff,),
    documents=result.documents,
)

print(f"Added: {len(delta.added)}")
print(f"Modified: {len(delta.modified)}")
print(f"Deleted IDs: {len(delta.deleted_ids)}")
```

See the [Export Guide](export.md) for detailed examples.

## Identity Model

docprep generates deterministic UUIDv5 identifiers:

```python
from docprep import canonicalize_source_uri, IDENTITY_VERSION, SCHEMA_VERSION

# Document ID = UUIDv5(namespace, source_uri)
# Section ID  = UUIDv5(namespace, "{doc_id}:section:{anchor}")
# Chunk ID    = UUIDv5(namespace, "{doc_id}:chunk:{anchor}")

uri = canonicalize_source_uri("docs/guide.md", source_root="docs/")
# => "file:guide.md"

# Version constants
print(f"Identity: v{IDENTITY_VERSION}, Schema: v{SCHEMA_VERSION}")
```

Same input always produces the same IDs. See [ADR-0001](decisions/0001-identity-model.md) for the design rationale.

## CheckpointStore

Low-level access to the checkpoint mechanism:

```python
from docprep import CheckpointStore

store = CheckpointStore(path=".docprep-checkpoint.json")
store.load(config_fingerprint="abc123")

if store.is_completed("file:docs/guide.md", checksum="deadbeef"):
    print("Already processed")
else:
    # ... process document ...
    store.mark_completed("file:docs/guide.md", checksum="deadbeef")
    store.save(run_id="run-001")

print(f"Completed: {store.completed_count}")
store.clear()  # remove checkpoint file
```

## Error Handling

All docprep exceptions inherit from `DocPrepError`:

```python
from docprep import (
    DocPrepError,    # base
    ConfigError,     # invalid config
    LoadError,       # file loading failed
    ParseError,      # parsing failed
    ChunkError,      # chunking failed
    IngestError,     # pipeline orchestration error
    SinkError,       # persistence error
    MetadataError,   # metadata validation error
)
```

### Error Modes

```python
from docprep import ErrorMode

# Default: skip failures, collect errors
result = ingest("docs/", error_mode=ErrorMode.CONTINUE_ON_ERROR)
for error in result.errors:
    print(f"Failed: {error.source_uri} at {error.stage}: {error.message}")

# Strict: raise on first failure
result = ingest("docs/", error_mode=ErrorMode.FAIL_FAST)
```

## Component Discovery

List all registered components (built-in + plugins):

```python
from docprep import get_all_loaders, get_all_parsers, get_all_chunkers, get_all_sinks

for name, cls in get_all_parsers().items():
    print(f"  {name}: {cls}")
```
