# Export Guide

docprep exports structured, vector-ready records from processed documents. This guide covers the export formats, text prepend strategies, JSONL serialization, and incremental (changed-only) export.

## VectorRecordV1

`VectorRecordV1` is the primary export format. Each record maps 1:1 to a chunk and carries full provenance metadata.

```python
from docprep import ingest, build_vector_records_v1

result = ingest("docs/")
records = build_vector_records_v1(result.documents)

for record in records:
    print(f"ID: {record.id}")
    print(f"Source: {record.source_uri}")
    print(f"Section: {' > '.join(record.section_path)}")
    print(f"Text: {record.text[:100]}...")
    print()
```

### Schema

| Field | Type | Description |
|-------|------|-------------|
| `id` | `uuid.UUID` | Deterministic chunk ID |
| `document_id` | `uuid.UUID` | Parent document ID |
| `section_id` | `uuid.UUID` | Parent section ID |
| `chunk_anchor` | `str` | Stable chunk anchor (e.g. `intro:a1b2c3d4`) |
| `section_anchor` | `str` | Parent section anchor (e.g. `intro`) |
| `text` | `str` | Chunk text with optional title/heading prepend |
| `content_hash` | `str` | Truncated SHA-256 of raw chunk content |
| `char_count` | `int` | Character count of `content_text` |
| `source_uri` | `str` | Canonical source file URI |
| `title` | `str` | Document title |
| `section_path` | `tuple[str, ...]` | Heading breadcrumb trail |
| `schema_version` | `int` | Export schema version (currently `1`) |
| `pipeline_version` | `str` | docprep version that produced the record |
| `created_at` | `str` | ISO 8601 timestamp |
| `user_metadata` | `dict` | Merged frontmatter + source metadata |

### VectorRecord (Legacy)

The simpler `VectorRecord` type contains only `id`, `text`, and `metadata` (a flat dict with all provenance info). Use `VectorRecordV1` for new integrations.

## Text Prepend Strategies

The `text` field can optionally prepend document title and heading path before the chunk content. This improves embedding quality by adding context.

```python
from docprep import TextPrependStrategy, build_vector_records_v1

# Default: title + heading path
records = build_vector_records_v1(
    result.documents,
    text_prepend=TextPrependStrategy.TITLE_AND_HEADING_PATH,
)
# text = "My Document\n\nInstallation > Requirements\n\nYou need Python 3.11+..."

# Title only
records = build_vector_records_v1(
    result.documents,
    text_prepend=TextPrependStrategy.TITLE_ONLY,
)
# text = "My Document\n\nYou need Python 3.11+..."

# Heading path only
records = build_vector_records_v1(
    result.documents,
    text_prepend=TextPrependStrategy.HEADING_PATH,
)
# text = "Installation > Requirements\n\nYou need Python 3.11+..."

# No prepend — raw chunk text
records = build_vector_records_v1(
    result.documents,
    text_prepend=TextPrependStrategy.NONE,
)
# text = "You need Python 3.11+..."
```

### Strategy Reference

| Strategy | Prepended Content | Use Case |
|----------|-------------------|----------|
| `TITLE_AND_HEADING_PATH` | Title + heading breadcrumb | Best for general RAG (default) |
| `TITLE_ONLY` | Document title only | When headings aren't informative |
| `HEADING_PATH` | Heading breadcrumb only | Multi-document sets with unique headings |
| `NONE` | Nothing | When chunks are self-contained |

Configure in `docprep.toml`:

```toml
[export]
text_prepend = "title_and_heading_path"
```

## JSONL Export

### Python API

```python
from docprep.export import iter_vector_records_v1, write_jsonl

result = ingest("docs/")

# Stream to file — memory-efficient for large corpora
with open("records.jsonl", "w") as f:
    count = write_jsonl(iter_vector_records_v1(result.documents), f)
    print(f"Exported {count} records")
```

Each line is a JSON object with UUID fields serialized as strings:

```json
{"id": "a1b2c3d4-...", "document_id": "e5f6g7h8-...", "text": "...", "content_hash": "abc123", ...}
```

### CLI

```bash
# Export all records
docprep export -o records.jsonl

# Export with explicit source and database
docprep export docs/ --db sqlite:///docs.db -o records.jsonl

# Export as JSON (for piping)
docprep export --json
```

### Single Record Serialization

```python
from docprep.export import record_to_jsonl

json_line = record_to_jsonl(record)
# Returns a single-line JSON string (no trailing newline)
```

## Changed-Only Export

The most powerful export feature: export only chunks that changed since the last ingestion. This minimizes re-embedding costs.

### How It Works

1. **Ingest** current documents (with a sink to persist state)
2. **Diff** current vs. previous state
3. **Build delta** containing only added, modified, and deleted chunks

### Python API

```python
from docprep import ingest, compute_diff_from_documents, build_export_delta
from docprep.export import write_jsonl
from docprep.sinks.sqlalchemy import SQLAlchemySink
from sqlalchemy import create_engine

engine = create_engine("sqlite:///docs.db")
sink = SQLAlchemySink(engine=engine)

# Ingest current state
current = ingest("docs/", sink=sink)

# ... later, after documents change ...
updated = ingest("docs/", sink=sink)

# Compute diff for each document
diffs = []
for prev_doc, curr_doc in zip(current.documents, updated.documents):
    diffs.append(compute_diff_from_documents(prev_doc, curr_doc))

# Build delta
delta = build_export_delta(
    diff_results=tuple(diffs),
    documents=updated.documents,
)

print(f"Added: {len(delta.added)} records")
print(f"Modified: {len(delta.modified)} records")
print(f"Deleted: {len(delta.deleted_ids)} IDs")

# Export added + modified to JSONL
with open("delta.jsonl", "w") as f:
    from itertools import chain
    write_jsonl(iter(chain(delta.added, delta.modified)), f)
```

### ExportDelta

```python
delta.added       # tuple[VectorRecordV1, ...] — new chunks
delta.modified    # tuple[VectorRecordV1, ...] — changed chunks (full record)
delta.deleted_ids # tuple[uuid.UUID, ...] — IDs to remove from vector store
```

### CLI

```bash
# Export only changed chunks
docprep export docs/ --changed-only --db sqlite:///docs.db -o delta.jsonl
```

## Structural Annotations

Include structural type information (code fences, tables, lists) in exported records:

```python
records = build_vector_records_v1(
    result.documents,
    include_annotations=True,
)

# record.user_metadata may contain:
# {"docprep.structure_types": ["code_fence", "table"]}
```

Configure in `docprep.toml`:

```toml
[export]
include_annotations = true
```

## Integration Examples

### Qdrant

```python
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

client = QdrantClient(url="http://localhost:6333")

points = [
    PointStruct(
        id=str(record.id),
        vector=embed(record.text),  # your embedding function
        payload={
            "source_uri": record.source_uri,
            "title": record.title,
            "section_path": list(record.section_path),
            "content_hash": record.content_hash,
            **record.user_metadata,
        },
    )
    for record in records
]
client.upsert(collection_name="docs", points=points)
```

### pgvector

```python
import psycopg

with psycopg.connect("postgresql://localhost/mydb") as conn:
    for record in records:
        vector = embed(record.text)
        conn.execute(
            "INSERT INTO documents (id, embedding, text, source_uri, metadata) "
            "VALUES (%s, %s, %s, %s, %s) ON CONFLICT (id) DO UPDATE SET "
            "embedding = EXCLUDED.embedding, text = EXCLUDED.text",
            (str(record.id), vector, record.text, record.source_uri,
             json.dumps(record.user_metadata)),
        )
```
