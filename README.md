<p align="center">
  <img src="assets/logo.svg" width="128" alt="docprep logo">
</p>

# docprep

Deterministic document chunking for RAG pipelines.

[![Test and Coverage](https://github.com/yeongseon/docprep/actions/workflows/ci-test.yml/badge.svg)](https://github.com/yeongseon/docprep/actions/workflows/ci-test.yml)
[![PyPI version](https://badge.fury.io/py/docprep.svg)](https://pypi.org/project/docprep/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## What is docprep?

docprep transforms source documents into structured, vector-ready chunks with **deterministic IDs**, **Markdown-aware boundaries**, and **incremental sync**. It sits between your documents and your vector store:

```
Source files → Loader → Parser → Chunker(s) → Sink → Export
                                      │
                                Diff Engine → Changed-only export
```

docprep produces the same chunk IDs for the same input, every time. When documents change, it computes a structural diff and exports only the added, modified, or deleted chunks — so you re-embed only what changed.

## What docprep is NOT

- **Not a document parser.** Use [MarkItDown](https://github.com/microsoft/markitdown), [Docling](https://github.com/DS4SD/docling), or [Unstructured](https://github.com/Unstructured-IO/unstructured) for PDFs/DOCX/PPTX, then feed Markdown into docprep via [adapters](docs/adapters.md).
- **Not an embedding service.** docprep produces text chunks; you bring your own embedding model.
- **Not a vector database.** docprep exports records for Qdrant, pgvector, Chroma, or any other store.
- **Not a RAG framework.** Use LlamaIndex or LangChain for retrieval. docprep handles the ingestion layer.

## How docprep compares

| Feature | docprep | MarkItDown | Docling | Unstructured | Chonkie |
|---------|---------|------------|---------|--------------|---------|
| Deterministic chunk IDs | ✅ | N/A | ❌ | ❌ | ❌ |
| Markdown-aware splitting | ✅ | N/A | Limited | Limited | ❌ |
| Incremental sync (diff) | ✅ | ❌ | ❌ | ❌ | ❌ |
| Multi-format parsing | Via adapters | ✅ | ✅ | ✅ | ❌ |
| Plugin system | ✅ | ❌ | ❌ | ❌ | ❌ |
| Chunk-level provenance | ✅ | N/A | Partial | Partial | ❌ |

## Installation

```bash
pip install docprep
```

For PostgreSQL support:

```bash
pip install docprep[postgres]
```

## Quick Start

### Config-first (recommended)

Create a `docprep.toml` in your project root:

```toml
source = "docs/"

[sink]
database_url = "sqlite:///docs.db"
create_tables = true

[[chunkers]]
type = "heading"

[[chunkers]]
type = "token"
max_tokens = 512
```

Then run:

```bash
docprep ingest              # Ingest documents
docprep preview             # Preview structure without persisting
docprep export -o out.jsonl # Export as JSONL
docprep diff                # Show what changed since last ingest
```

### Python API

```python
from docprep import ingest

result = ingest("docs/")
for doc in result.documents:
    print(f"{doc.title}: {len(doc.sections)} sections, {len(doc.chunks)} chunks")
```

### With database persistence

```python
from sqlalchemy import create_engine
from docprep import ingest
from docprep.sinks.sqlalchemy import SQLAlchemySink

engine = create_engine("sqlite:///docs.db")
sink = SQLAlchemySink(engine=engine)

result = ingest("docs/", sink=sink)
print(f"Persisted: {result.persisted}, Skipped: {len(result.skipped_source_uris)}")
```

### Changed-only export

```bash
docprep export docs/ --changed-only --db sqlite:///docs.db -o delta.jsonl
```

## Documentation

| Guide | Description |
|-------|-------------|
| [Getting Started](docs/getting-started.md) | Installation, first ingestion, basic usage |
| [Configuration](docs/configuration.md) | `docprep.toml` reference and all options |
| [CLI Reference](docs/cli-reference.md) | All commands, flags, and examples |
| [Python API](docs/python-api.md) | Types, functions, and usage patterns |
| [Architecture](docs/architecture.md) | Pipeline flow, identity model, module map |
| [Export](docs/export.md) | VectorRecordV1, JSONL, changed-only export |
| [Plugins](docs/plugins.md) | Entry-point plugin system |
| [Adapters](docs/adapters.md) | External converter integration |

Design decisions are documented as [Architecture Decision Records](docs/decisions/README.md).

## Supported Formats

| Format | Extensions | Parser | Notes |
|--------|-----------|--------|-------|
| Markdown | `.md` | Built-in | Frontmatter extraction, heading hierarchy |
| Plain text | `.txt` | Built-in | First non-empty line as title |
| HTML | `.html`, `.htm` | Built-in (stdlib) | Strips script/style, converts headings |
| reStructuredText | `.rst` | Built-in | Heading adornments, field lists |
| Any format | `*` | Via [adapter](docs/adapters.md) | MarkItDown, Docling, Unstructured, etc. |

## Development

```bash
git clone https://github.com/yeongseon/docprep.git
cd docprep
make install

make check-all    # lint + typecheck + test + security
make test         # pytest
make lint         # ruff + mypy
make format       # ruff format
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full development guide.

## License

MIT
