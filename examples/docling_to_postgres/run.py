#!/usr/bin/env python3
"""Demo: Simulated Docling conversion persisted to PostgreSQL."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from docprep import ingest
from docprep.sinks.sqlalchemy import SQLAlchemySink

DEFAULT_DATABASE_URL = "postgresql+psycopg://docprep:docprep@localhost:5432/docprep_demo"

RESEARCH_PAPER_MD = """---
title: Research Paper
domain: machine-learning
---

# Research Paper

## Abstract

This paper presents a novel retrieval-ranking strategy for long technical documents.

## Method

We combine heading-aware segmentation with deterministic chunk identity tracking.

## Results

The approach improves answer grounding by 18% on the internal benchmark.
"""

TECH_SPEC_MD = """---
title: Technical Specification
system: ingestion-service
---

# Technical Specification

## Scope

Defines ingestion flow, revision tracking, and changed-only export behavior.

## API Contract

### `POST /ingest`

Accepts a source URI and returns a run summary.

### `GET /diff/{document_id}`

Returns section and chunk-level status values.
"""

USER_MANUAL_MD = """---
title: User Manual
audience: operators
---

# User Manual

## Installation

Install dependencies and configure the environment before first run.

## Daily Workflow

1. Ingest current documents.
2. Export changed records.
3. Sync vector database.

## Troubleshooting

If ingestion fails, review parser errors and retry after correction.
"""


def _write_sample_docs(docs_dir: Path) -> None:
    # In production, Docling converts your PDF/DOCX files. This demo uses pre-converted Markdown.
    docs_dir.mkdir(parents=True, exist_ok=True)
    _ = (docs_dir / "research-paper.md").write_text(RESEARCH_PAPER_MD, encoding="utf-8")
    _ = (docs_dir / "technical-spec.md").write_text(TECH_SPEC_MD, encoding="utf-8")
    _ = (docs_dir / "user-manual.md").write_text(USER_MANUAL_MD, encoding="utf-8")


def _sample_chunk_from_db(sink: SQLAlchemySink, source_uri: str) -> tuple[str, str, str] | None:
    db_document = sink.get_document(source_uri)
    if db_document is None or not db_document.chunks:
        return None

    chunk = db_document.chunks[0]
    heading_by_section = {
        section.id: " > ".join(section.heading_path) for section in db_document.sections
    }
    heading = heading_by_section.get(chunk.section_id, "")
    return db_document.title, heading, chunk.content_text


def main() -> None:
    database_url = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    engine = create_engine(database_url)
    sink = SQLAlchemySink(engine=engine, create_tables=True)

    parsed = make_url(database_url)
    print(f"Connected to PostgreSQL at {parsed.host}:{parsed.port}/{parsed.database}")

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs_dir = Path(tmp_dir) / "docling_output"
        _write_sample_docs(docs_dir)

        result = ingest(str(docs_dir), sink=sink)
        chunk_count = sum(len(document.chunks) for document in result.documents)

    print(f"Ingested {len(result.documents)} documents -> {chunk_count} chunks")
    print(f"Persisted: {result.persisted}, Skipped: {len(result.skipped_source_uris)}")

    stats = sink.stats()

    print("\nDatabase contents:")
    print(f"  documents: {stats.documents} rows")
    print(f"  sections: {stats.sections} rows")
    print(f"  chunks: {stats.chunks} rows")

    sample_source_uri = result.documents[0].source_uri if result.documents else ""
    sample = _sample_chunk_from_db(sink, sample_source_uri) if sample_source_uri else None
    if sample is not None:
        title, section, text_preview = sample
        preview = text_preview.replace("\n", " ").strip()[:90]
        print("\nSample chunk from database:")
        print(f"  Title: {title}")
        print(f"  Section: {section}")
        print(f'  Text: "{preview}..."')


if __name__ == "__main__":
    main()
