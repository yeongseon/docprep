<p align="center">
  <img src="assets/logo.svg" width="128" alt="docprep logo">
</p>

# docprep

Deterministic document chunking for RAG pipelines.

[![Test and Coverage](https://github.com/yeongseon/docprep/actions/workflows/ci-test.yml/badge.svg)](https://github.com/yeongseon/docprep/actions/workflows/ci-test.yml)
[![PyPI version](https://badge.fury.io/py/docprep.svg)](https://pypi.org/project/docprep/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## What is docprep?

docprep transforms source documents into structured, vector-ready chunks with **deterministic IDs**, **Markdown-aware boundaries**, and **incremental sync**. It sits between your documents and your vector store:

```
Source files -> Loader -> Parser -> Chunker(s) -> Sink -> Export
                                       |
                                 Diff Engine -> Changed-only export
```

docprep produces the same chunk IDs for the same input, every time. When documents change, it computes a structural diff and exports only the added, modified, or deleted chunks -- so you re-embed only what changed.

## What docprep is NOT

- **Not a document parser.** docprep does not parse PDFs, DOCX, or PPTX. Use [MarkItDown](https://github.com/microsoft/markitdown), [Docling](https://github.com/DS4SD/docling), or [Unstructured](https://github.com/Unstructured-IO/unstructured) for that, then feed their Markdown output into docprep.
- **Not an embedding service.** docprep produces text chunks; you bring your own embedding model.
- **Not a vector database.** docprep exports records for Qdrant, pgvector, Chroma, or any other store.
- **Not a RAG framework.** Use LlamaIndex or LangChain for retrieval orchestration. docprep handles the ingestion layer.

## How docprep compares

| Feature | docprep | MarkItDown | Docling | Unstructured | Chonkie |
|---------|---------|------------|---------|--------------|---------|
| Deterministic chunk IDs | Yes | N/A | No | No | No |
| Markdown-aware splitting | Yes | N/A | Limited | Limited | No |
| Incremental sync (diff) | Yes | No | No | No | No |
| Multi-format parsing | Via adapters | Yes | Yes | Yes | No |
| Plugin system | Yes | No | No | No | No |
| Chunk-level provenance | Yes | N/A | Partial | Partial | No |

MarkItDown converts files to Markdown (complementary to docprep). Chonkie is a chunking library without structural awareness or identity tracking.

## Supported formats

| Format | Extensions | Parser | Notes |
|--------|-----------|--------|-------|
| Markdown | `.md` | Built-in | Frontmatter extraction, heading hierarchy |
| Plain text | `.txt` | Built-in | First non-empty line as title |
| HTML | `.html`, `.htm` | Built-in (stdlib) | Strips script/style, converts headings |
| reStructuredText | `.rst` | Built-in | Heading adornments, field lists |
| Any format | `*` | Via adapter | MarkItDown, Docling, Unstructured, etc. |

## Installation

```bash
pip install docprep
```

For PostgreSQL support:

```bash
pip install docprep[postgres]
```

## Quick start

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
# Ingest documents
docprep ingest

# Preview structure without persisting
docprep preview

# Export as JSONL
docprep export -o records.jsonl

# Show what changed since last ingest
docprep diff
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

### Streaming JSONL export

```python
from docprep import ingest
from docprep.export import iter_vector_records_v1, write_jsonl

result = ingest("docs/")

# Stream to file
with open("records.jsonl", "w") as f:
    count = write_jsonl(iter_vector_records_v1(result.documents), f)
    print(f"Exported {count} records")
```

### Changed-only export

```bash
# Export only chunks that changed since last sync
docprep export docs/ --changed-only --db sqlite:///docs.db -o delta.jsonl
```

## CLI reference

| Command | Description |
|---------|-------------|
| `docprep ingest` | Ingest documents into a database |
| `docprep preview` | Preview document structure without persistence |
| `docprep export` | Export vector records as JSONL |
| `docprep diff` | Show changes against persisted state |
| `docprep stats` | Show database statistics |
| `docprep inspect` | Inspect a document, section, or chunk by URI or ID |
| `docprep prune` | Remove stale documents no longer in source |
| `docprep delete` | Delete a document by source URI |

All commands support `--config PATH` for explicit config and `--json` / `--no-json` for output format.

## Configuration

docprep discovers `docprep.toml` by searching the current directory and parent directories. Config precedence: CLI arguments > explicit `--config` > discovered config > defaults.

See [`examples/configs/`](examples/configs/) for minimal, standard, and advanced configurations.

### Full config reference

```toml
# Source directory or file
source = "docs/"

# Default output format for CLI
json = false

[loader]
type = "filesystem"                    # "markdown" or "filesystem"
include_globs = ["**/*.md", "**/*.txt", "**/*.html", "**/*.htm", "**/*.rst"]
exclude_globs = ["**/drafts/**"]
hidden_policy = "skip"                 # "skip" or "include"
symlink_policy = "follow"              # "follow" or "skip"
encoding = "utf-8"
encoding_errors = "strict"

[parser]
type = "auto"                          # "markdown", "plaintext", "html", "rst", or "auto"

[[chunkers]]
type = "heading"                       # Split by headings into sections

[[chunkers]]
type = "token"                         # Split sections into token-budgeted chunks
max_tokens = 512
overlap_tokens = 0
tokenizer = "whitespace"               # "whitespace" or "character"

# Alternative: size-based chunking
# [[chunkers]]
# type = "size"
# max_chars = 1500
# overlap_chars = 0
# min_chars = 0

[sink]
type = "sqlalchemy"
database_url = "sqlite:///docs.db"
create_tables = true

[export]
text_prepend = "title_and_heading_path"  # "none", "title_only", "heading_path", or "title_and_heading_path"
```

## Architecture

```
src/docprep/
├── models/domain.py       # Document, Section, Chunk, VectorRecordV1
├── loaders/
│   ├── markdown.py        # Load .md files
│   └── filesystem.py      # Multi-format loader with glob patterns
├── parsers/
│   ├── markdown.py        # Frontmatter + heading extraction
│   ├── plaintext.py       # Plain text with title detection
│   ├── html.py            # HTML to Markdown (stdlib only)
│   ├── rst.py             # RST heading adornments + field lists
│   └── multi.py           # Auto-dispatch by media type
├── chunkers/
│   ├── heading.py         # Split by headings into sections
│   ├── size.py            # Size-based chunk splitting
│   ├── token.py           # Token-aware chunk splitting
│   └── _markdown.py       # Shared Markdown boundary analysis
├── sinks/
│   ├── sqlalchemy.py      # SQLAlchemy persistence + revision tracking
│   └── orm.py             # Table definitions
├── adapters/
│   └── protocol.py        # Adapter protocol for external converters
├── plugins.py             # Entry-point plugin discovery
├── diff.py                # Structural diff engine
├── export.py              # VectorRecordV1 export + JSONL streaming
├── ingest.py              # Pipeline orchestration
├── ids.py                 # Deterministic ID generation
├── config.py              # Config discovery and validation
├── eval/                  # Evaluation corpus and benchmark harness
└── cli/main.py            # Command-line interface
```

## Plugin system

Third-party packages can provide custom loaders, parsers, chunkers, sinks, and adapters via Python entry points. No core modification required.

### Creating a plugin

In your package's `pyproject.toml`:

```toml
[project.entry-points."docprep.parsers"]
my-format = "my_package.parser:MyFormatParser"
```

Your parser class must implement the `Parser` protocol:

```python
from docprep.loaders.types import LoadedSource
from docprep.models.domain import Document

class MyFormatParser:
    def parse(self, loaded_source: LoadedSource) -> Document:
        ...
```

Plugin import failures produce warnings but never break built-in components.

## Design decisions

Key architectural decisions are documented as [Architecture Decision Records](docs/decisions/README.md):

- **Identity model**: Anchor-based stable IDs with content hash for change detection
- **Adapter-not-parser**: docprep normalizes, external tools parse
- **Chunking strategy**: Markdown-aware boundaries, then token-budget splitting
- **Plugin registry**: Entry-point discovery via `importlib.metadata`
- **Diff-then-sync**: Structural diff for incremental updates
- **Export contract**: VectorRecordV1 with mandatory provenance fields

## Development

```bash
git clone https://github.com/yeongseon/docprep.git
cd docprep
make install

# Run all checks
make check-all    # lint + typecheck + test + security

# Individual commands
make test         # pytest
make lint         # ruff + mypy
make format       # ruff format
make security     # bandit
make cov          # coverage report
```

## License

MIT
