# Docling to PostgreSQL

Convert documents via [Docling](https://github.com/DS4SD/docling) and persist to PostgreSQL using docprep's SQLAlchemy sink.

## What This Example Does

1. Converts sample documents to Markdown (simulated Docling output)
2. Ingests through docprep's chunking pipeline
3. Persists documents, sections, and chunks to PostgreSQL
4. Queries the database to show stored records

## Prerequisites

- Python 3.10+
- Docker and Docker Compose (for PostgreSQL)

## Setup

```bash
cd examples/docling_to_postgres

# Start PostgreSQL
docker compose up -d

# Install dependencies
pip install -r requirements.txt
```

## Run

```bash
python run.py
```

## Expected Output

```
Connected to PostgreSQL at localhost:5432/docprep_demo
Ingested 3 documents -> 12 chunks
Persisted: 12, Skipped: 0

Database contents:
  documents: 3 rows
  sections: 8 rows
  chunks: 12 rows

Sample chunk from database:
  Title: Research Paper
  Section: Abstract
  Text: "This paper presents a novel approach to..."
```

## Cleanup

```bash
docker compose down -v  # Removes PostgreSQL data
```

## What to Try Next

- Replace sample docs with real Docling output (`pip install docling`)
- Run the script twice to see incremental sync (skips unchanged documents)
- Export changed-only JSONL with `docprep export --changed-only`
