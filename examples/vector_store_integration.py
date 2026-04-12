#!/usr/bin/env python3
"""Example: Integrate docprep with vector databases.

Shows how to export docprep chunks to popular vector stores:
  1. Direct JSONL export (works with any store)
  2. Qdrant integration pattern
  3. ChromaDB integration pattern

Each pattern demonstrates the full flow:
  docprep ingest → export records → upsert to vector store

Usage:
    python examples/vector_store_integration.py
"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile

from docprep import VectorRecordV1, ingest, iter_vector_records_v1
from docprep.export import write_jsonl

# ---------------------------------------------------------------------------
# Sample documents for the demo
# ---------------------------------------------------------------------------

DOCS = {
    "intro.md": """\
---
title: Introduction to Machine Learning
---

# Introduction to Machine Learning

Machine learning is a subset of artificial intelligence that enables
systems to learn and improve from experience without being explicitly
programmed.

## Supervised Learning

In supervised learning, the algorithm learns from labeled training data.
Common algorithms include linear regression, decision trees, and neural
networks.

## Unsupervised Learning

Unsupervised learning finds hidden patterns in data without labels.
Clustering (K-means, DBSCAN) and dimensionality reduction (PCA, t-SNE)
are common techniques.
""",
    "deep-learning.md": """\
---
title: Deep Learning Fundamentals
---

# Deep Learning Fundamentals

Deep learning uses neural networks with multiple layers to progressively
extract higher-level features from raw input.

## Neural Network Architecture

A typical neural network consists of an input layer, one or more hidden
layers, and an output layer. Each layer contains neurons that apply
an activation function to their weighted inputs.

## Training Process

Training involves forward propagation (computing predictions),
loss calculation, and backpropagation (updating weights via gradients).
Optimizers like Adam and SGD control the weight update process.

## Common Architectures

- **CNN** — Convolutional Neural Networks for image tasks
- **RNN/LSTM** — Recurrent networks for sequential data
- **Transformer** — Attention-based architecture for NLP and beyond
""",
}


def create_sample_docs(base_dir: Path) -> None:
    for name, content in DOCS.items():
        (base_dir / name).write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Pattern 1: JSONL export (universal)
# ---------------------------------------------------------------------------


def demo_jsonl_export(docs_dir: Path, output_dir: Path) -> None:
    """Export to JSONL — works with any vector store that accepts JSON."""
    print("── Pattern 1: JSONL Export (Universal) ──\n")

    result = ingest(str(docs_dir))
    jsonl_path = output_dir / "records.jsonl"

    with open(jsonl_path, "w", encoding="utf-8") as f:
        count = write_jsonl(iter_vector_records_v1(result.documents), f)

    print(f"  Exported {count} records to {jsonl_path.name}")
    print("  Each record contains: id, text, metadata, source info\n")

    # Show one record
    with open(jsonl_path, encoding="utf-8") as f:
        first = json.loads(f.readline())
    print(f"  Sample record keys: {sorted(first.keys())}")
    print(f"  Text preview: {first['text'][:80]}...")
    print()


# ---------------------------------------------------------------------------
# Pattern 2: Qdrant integration
# ---------------------------------------------------------------------------


def demo_qdrant_pattern(docs_dir: Path) -> None:
    """Show how to integrate with Qdrant (pattern only — no Qdrant dependency).

    Install: pip install qdrant-client
    """
    print("── Pattern 2: Qdrant Integration ──\n")

    result = ingest(str(docs_dir))
    records = list(iter_vector_records_v1(result.documents))

    print("  # Real Qdrant code (requires: pip install qdrant-client):")
    print("  #")
    print("  # from qdrant_client import QdrantClient, models")
    print("  #")
    print("  # client = QdrantClient(url='http://localhost:6333')")
    print("  # client.recreate_collection(")
    print("  #     collection_name='docs',")
    print("  #     vectors_config=models.VectorParams(size=1536, distance=models.Distance.COSINE),")
    print("  # )")
    print("  #")
    print("  # for record in records:")
    print("  #     embedding = your_embed_fn(record.text)  # Your embedding model")
    print("  #     client.upsert(")
    print("  #         collection_name='docs',")
    print("  #         points=[models.PointStruct(")
    print("  #             id=record.id.hex,            # Deterministic ID!")
    print("  #             vector=embedding,")
    print("  #             payload={")
    print("  #                 'text': record.text,")
    print("  #                 'source_uri': record.source_uri,")
    print("  #                 'title': record.title,")
    print("  #                 'section_path': list(record.section_path),")
    print("  #                 'content_hash': record.content_hash,")
    print("  #             },")
    print("  #         )],")
    print("  #     )")
    print()

    # Show what the payloads would look like
    print(f"  Prepared {len(records)} records for Qdrant:\n")
    for r in records[:3]:
        print(f"    ID: {r.id.hex[:12]}...")
        print(f"    Text: {r.text[:60].replace(chr(10), ' ')}...")
        print(f"    Source: {r.source_uri}")
        print(f"    Section: {' > '.join(r.section_path)}")
        print()

    # Show incremental update pattern
    print("  Incremental update pattern:")
    print("  - docprep chunk IDs are deterministic (same content → same ID)")
    print("  - Use build_export_delta() to get only changed chunks")
    print("  - Upsert added/modified, delete removed — no orphaned vectors!")
    print()


# ---------------------------------------------------------------------------
# Pattern 3: ChromaDB integration
# ---------------------------------------------------------------------------


def demo_chroma_pattern(docs_dir: Path) -> None:
    """Show how to integrate with ChromaDB (pattern only — no Chroma dependency).

    Install: pip install chromadb
    """
    print("── Pattern 3: ChromaDB Integration ──\n")

    result = ingest(str(docs_dir))
    records = list(iter_vector_records_v1(result.documents))

    print("  # Real ChromaDB code (requires: pip install chromadb):")
    print("  #")
    print("  # import chromadb")
    print("  #")
    print("  # client = chromadb.Client()")
    print("  # collection = client.get_or_create_collection('docs')")
    print("  #")
    print("  # # Batch upsert (ChromaDB handles embedding if configured)")
    print("  # collection.upsert(")
    print("  #     ids=[r.id.hex for r in records],")
    print("  #     documents=[r.text for r in records],")
    print("  #     metadatas=[{")
    print("  #         'source_uri': r.source_uri,")
    print("  #         'title': r.title,")
    print("  #         'section_path': ' > '.join(r.section_path),")
    print("  #         'content_hash': r.content_hash,")
    print("  #     } for r in records],")
    print("  # )")
    print()

    # Show the data shape
    print(f"  Prepared {len(records)} records for ChromaDB:\n")
    for r in records[:3]:
        print(f"    ID:       {r.id.hex[:12]}...")
        print(f"    Document: {r.text[:60].replace(chr(10), ' ')}...")
        print(f"    Metadata: title={r.title!r}, source={r.source_uri}")
        print()


# ---------------------------------------------------------------------------
# Helper: show record structure
# ---------------------------------------------------------------------------


def show_record_structure(record: VectorRecordV1) -> None:
    """Display all fields of a VectorRecordV1 for educational purposes."""
    print("  VectorRecordV1 fields:")
    print(f"    id:               {record.id}")
    print(f"    document_id:      {record.document_id}")
    print(f"    section_id:       {record.section_id}")
    print(f"    chunk_anchor:     {record.chunk_anchor}")
    print(f"    section_anchor:   {record.section_anchor}")
    print(f"    text:             {record.text[:50]}...")
    print(f"    content_hash:     {record.content_hash}")
    print(f"    char_count:       {record.char_count}")
    print(f"    source_uri:       {record.source_uri}")
    print(f"    title:            {record.title}")
    print(f"    section_path:     {record.section_path}")
    print(f"    schema_version:   {record.schema_version}")
    print(f"    pipeline_version: {record.pipeline_version}")
    print(f"    created_at:       {record.created_at}")
    print(f"    user_metadata:    {record.user_metadata}")


def main() -> None:
    print("=" * 60)
    print("  docprep → Vector Store Integration Examples")
    print("=" * 60)
    print()

    with tempfile.TemporaryDirectory() as tmpdir:
        docs_dir = Path(tmpdir) / "docs"
        docs_dir.mkdir()
        output_dir = Path(tmpdir) / "output"
        output_dir.mkdir()
        create_sample_docs(docs_dir)

        # Pattern 1: Universal JSONL
        demo_jsonl_export(docs_dir, output_dir)

        # Pattern 2: Qdrant
        demo_qdrant_pattern(docs_dir)

        # Pattern 3: ChromaDB
        demo_chroma_pattern(docs_dir)

        # Bonus: Show full record structure
        print("── Bonus: Full VectorRecordV1 Structure ──\n")
        result = ingest(str(docs_dir))
        records = list(iter_vector_records_v1(result.documents))
        if records:
            show_record_structure(records[0])

    print()
    print("=" * 60)
    print("  Key takeaway: docprep produces deterministic chunk IDs.")
    print("  Use build_export_delta() for incremental vector store updates.")
    print("=" * 60)


if __name__ == "__main__":
    main()
