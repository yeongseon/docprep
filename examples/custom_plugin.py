#!/usr/bin/env python3
"""Example: Create a custom chunker plugin for docprep.

This demonstrates how to extend docprep with custom components:
  1. A custom Chunker that splits by paragraph boundaries
  2. How to register it as a plugin via entry points
  3. How to use it programmatically (without entry points)

Usage:
    python examples/custom_plugin.py
"""

from __future__ import annotations

from pathlib import Path
import tempfile
import uuid

from docprep import (
    Chunk,
    Document,
    Ingestor,
    get_all_chunkers,
    get_all_loaders,
    get_all_parsers,
    get_all_sinks,
    ingest,
)
from docprep.chunkers.protocol import Chunker
from docprep.ids import DOCPREP_NAMESPACE

# ---------------------------------------------------------------------------
# Custom Chunker: Split by paragraphs
# ---------------------------------------------------------------------------


class ParagraphChunker:
    """Splits document sections into chunks at paragraph boundaries.

    Unlike the built-in token chunker (which splits by token count),
    this chunker preserves natural paragraph boundaries. Each paragraph
    becomes its own chunk.

    To use as a plugin, register in your package's pyproject.toml:

        [project.entry-points."docprep.chunkers"]
        paragraph = "my_package.chunkers:ParagraphChunker"
    """

    def __init__(self, *, min_chars: int = 20) -> None:
        self.min_chars = min_chars

    def chunk(self, document: Document) -> Document:
        """Split each section's content into paragraph-based chunks."""
        # If no sections exist, create a root section first
        if not document.sections:
            return document

        chunks: list[Chunk] = []
        chunk_index = 0

        for section in document.sections:
            if not section.content_markdown:
                continue

            paragraphs = self._split_paragraphs(section.content_markdown)

            for para_idx, paragraph in enumerate(paragraphs):
                if len(paragraph.strip()) < self.min_chars:
                    continue

                # Generate deterministic chunk ID
                import hashlib

                content_hash = hashlib.sha256(paragraph.encode("utf-8")).hexdigest()[:16]
                anchor = f"{section.anchor}:p{para_idx}"
                chunk_id = uuid.uuid5(
                    DOCPREP_NAMESPACE,
                    f"{document.id}:chunk:{anchor}",
                )

                chunks.append(
                    Chunk(
                        id=chunk_id,
                        document_id=document.id,
                        section_id=section.id,
                        order_index=chunk_index,
                        section_chunk_index=para_idx,
                        anchor=anchor,
                        content_hash=content_hash,
                        content_text=paragraph.strip(),
                        char_start=0,
                        char_end=len(paragraph.strip()),
                        heading_path=section.heading_path,
                        lineage=section.lineage,
                    )
                )
                chunk_index += 1

        # Return a new document with the paragraph-based chunks
        return Document(
            id=document.id,
            source_uri=document.source_uri,
            title=document.title,
            source_checksum=document.source_checksum,
            source_type=document.source_type,
            frontmatter=document.frontmatter,
            source_metadata=document.source_metadata,
            body_markdown=document.body_markdown,
            structural_annotations=document.structural_annotations,
            sections=document.sections,
            chunks=tuple(chunks),
        )

    @staticmethod
    def _split_paragraphs(text: str) -> list[str]:
        """Split text into paragraphs (separated by blank lines)."""
        paragraphs = []
        current: list[str] = []

        for line in text.split("\n"):
            if line.strip() == "":
                if current:
                    paragraphs.append("\n".join(current))
                    current = []
            else:
                current.append(line)

        if current:
            paragraphs.append("\n".join(current))

        return paragraphs


# Verify it satisfies the Chunker protocol
assert isinstance(ParagraphChunker(), Chunker), "Must satisfy Chunker protocol"


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------


def main() -> None:
    print("=" * 60)
    print("  docprep Custom Plugin Example")
    print("=" * 60)

    # ── Show built-in components ──
    print("\n── Built-in Components ──\n")
    print(f"  Loaders:  {sorted(get_all_loaders().keys())}")
    print(f"  Parsers:  {sorted(get_all_parsers().keys())}")
    print(f"  Chunkers: {sorted(get_all_chunkers().keys())}")
    print(f"  Sinks:    {sorted(get_all_sinks().keys())}")

    # ── Create sample docs ──
    with tempfile.TemporaryDirectory() as tmpdir:
        docs_dir = Path(tmpdir) / "docs"
        docs_dir.mkdir()
        (docs_dir / "guide.md").write_text(
            """\
---
title: Deployment Guide
---

# Deployment Guide

## Prerequisites

You need Docker installed on your system. Make sure you have version
20.10 or later. You also need access to the container registry.

Check your Docker version:

```bash
docker --version
```

## Building the Image

Build the production Docker image using the provided Dockerfile.
The build process compiles assets, runs tests, and creates an
optimized image.

```bash
docker build -t myapp:latest .
```

The build takes approximately 3-5 minutes depending on your machine.

## Deploying to Production

Push the image to the registry and update the deployment manifest.
The rolling update strategy ensures zero downtime.

```bash
docker push registry.example.com/myapp:latest
kubectl apply -f deploy/production.yaml
```

Monitor the rollout status:

```bash
kubectl rollout status deployment/myapp
```

## Rollback

If something goes wrong, roll back to the previous version:

```bash
kubectl rollout undo deployment/myapp
```

Always check logs after a rollback to understand what went wrong.
""",
            encoding="utf-8",
        )

        # ── Compare built-in vs custom chunker ──
        print("\n── Built-in Chunker (heading) ──\n")
        result_builtin = ingest(str(docs_dir))
        for doc in result_builtin.documents:
            print(f"  {doc.title}: {len(doc.chunks)} chunks")
            for chunk in doc.chunks:
                preview = chunk.content_text[:60].replace("\n", " ")
                print(f"    [{chunk.order_index}] {preview}...")

        print("\n── Custom ParagraphChunker ──\n")
        # Use Ingestor with HeadingChunker (creates sections) + ParagraphChunker
        from docprep.chunkers.heading import HeadingChunker

        heading_chunker = HeadingChunker()
        custom_chunker = ParagraphChunker(min_chars=30)
        ingestor = Ingestor(chunkers=[heading_chunker, custom_chunker])
        result_custom = ingestor.run(str(docs_dir))

        for doc in result_custom.documents:
            print(f"  {doc.title}: {len(doc.chunks)} chunks")
            for chunk in doc.chunks:
                preview = chunk.content_text[:60].replace("\n", " ")
                print(f"    [{chunk.order_index}] {preview}...")

    # ── Show plugin registration ──
    print("\n── Registering as a Plugin ──\n")
    print("  To distribute your custom chunker as a pip-installable plugin,")
    print("  add this to your package's pyproject.toml:\n")
    print('  [project.entry-points."docprep.chunkers"]')
    print('  paragraph = "my_package.chunkers:ParagraphChunker"')
    print()
    print("  Then users can reference it in their docprep.toml:\n")
    print("  [[chunkers]]")
    print('  type = "paragraph"')
    print()
    print("  Available entry point groups:")
    print("    docprep.loaders   — custom file loaders")
    print("    docprep.parsers   — custom document parsers")
    print("    docprep.chunkers  — custom chunking strategies")
    print("    docprep.sinks     — custom persistence backends")


if __name__ == "__main__":
    main()
