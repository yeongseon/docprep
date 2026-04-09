# docprep

Prepare documents into structured, vector-ready data.

[![Test and Coverage](https://github.com/yeongseon/docprep/actions/workflows/ci-test.yml/badge.svg)](https://github.com/yeongseon/docprep/actions/workflows/ci-test.yml)
[![PyPI version](https://badge.fury.io/py/docprep.svg)](https://pypi.org/project/docprep/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## What is docprep?

docprep is a Python library that transforms source documents (starting with Markdown) into structured, vector-ready data for storage and retrieval. It provides a clean pipeline:

```
Documents → Structured Sections → Sized Chunks → Storage → Vector Records
```

## Features

- **Markdown ingestion** with frontmatter extraction
- **Heading-aware sectioning** preserving document hierarchy
- **Smart chunking** with greedy paragraph/sentence/newline splitting
- **SQLAlchemy storage** with checksum-based re-ingestion skip
- **Vector-ready export** for embedding pipelines
- **Deterministic IDs** (UUIDv5) for stable references
- **CLI and Python API**

## Installation

```bash
pip install docprep
```

For PostgreSQL support:

```bash
pip install docprep[postgres]
```

## Quick Start

### Python API

```python
from docprep import ingest
from docprep.chunkers.heading import HeadingChunker
from docprep.chunkers.size import SizeChunker

result = ingest(
    "docs/",
    chunkers=[HeadingChunker(), SizeChunker()],
)

for doc in result.documents:
    print(f"{doc.title}: {len(doc.sections)} sections, {len(doc.chunks)} chunks")
```

### With database persistence

```python
from sqlalchemy import create_engine
from docprep import ingest
from docprep.chunkers.heading import HeadingChunker
from docprep.chunkers.size import SizeChunker
from docprep.sinks.sqlalchemy import SQLAlchemySink

engine = create_engine("sqlite:///docs.db")
sink = SQLAlchemySink(engine=engine)

result = ingest(
    "docs/",
    chunkers=[HeadingChunker(), SizeChunker()],
    sink=sink,
)
print(f"Persisted: {result.persisted}, Skipped: {len(result.skipped_source_uris)}")
```

### Vector-ready export

```python
from docprep.export import build_vector_records

records = build_vector_records(result.documents)
for record in records:
    print(f"ID: {record.id}")
    print(f"Text: {record.text[:100]}...")
    print(f"Metadata: {record.metadata}")
```

### CLI

```bash
# Preview document structure
docprep preview docs/

# Ingest into a database
docprep ingest docs/ --db sqlite:///docs.db

# Show database statistics
docprep stats sqlite:///docs.db

# JSON output
docprep preview docs/ --json
```

## Architecture

```
src/docprep/
├── models/domain.py      # Document, Section, Chunk, VectorRecord
├── loaders/markdown.py    # Load .md files from disk
├── parsers/markdown.py    # Parse frontmatter + body
├── chunkers/
│   ├── heading.py         # Split by headings → Sections
│   └── size.py            # Split sections → sized Chunks
├── sinks/
│   ├── orm.py             # SQLAlchemy table definitions
│   └── sqlalchemy.py      # Database persistence + stats
├── export.py              # Build vector-ready records
├── ingest.py              # Pipeline orchestration
└── cli/main.py            # Command-line interface
```

## Development

```bash
# Clone and install
git clone https://github.com/yeongseon/docprep.git
cd docprep
make install

# Run checks
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
