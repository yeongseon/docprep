# ADR-0002: Adapter-not-Parser Philosophy

**Status**: Accepted
**Date**: 2025-04-12
**Deciders**: Core team

## Context

Document ingestion for RAG involves two distinct problems:

1. **Format conversion**: turning PDFs, DOCX, PPTX, HTML, and other formats into a structured text representation.
2. **Chunking and indexing**: splitting that text into appropriately sized, structurally aware chunks with stable identities, then persisting them.

Several mature tools already solve problem 1 well: MarkItDown (Microsoft), Docling (IBM), Unstructured, and others. Each has strengths for different format families. Competing on parsing quality would require enormous investment with uncertain returns.

## Decision

docprep is a **normalizer and orchestrator**, not a parser. It assumes its input is already in a text-native format (Markdown, plain text, HTML, or RST) and focuses entirely on problem 2.

For non-text formats (PDF, DOCX, etc.), external tools convert the source to Markdown first. docprep then handles Markdown-to-schema-to-chunks-to-export.

The connection point is the **Adapter protocol** (`Adapter.convert()`), which bridges external tools to docprep's pipeline:

```
External tool (MarkItDown, Docling, etc.)
  -> Markdown or structured text
    -> docprep Adapter
      -> docprep Document/Section/Chunk
        -> storage/export
```

Built-in parsers exist only for formats that are natively textual: Markdown, plain text, HTML, and reStructuredText. These parsers live in `src/docprep/parsers/` and use only the Python standard library (no external parsing dependencies).

## Consequences

**Easier:**

- Core stays small, testable, and dependency-light.
- Users choose the best parser for their format (MarkItDown for Office docs, Docling for scientific PDFs, etc.).
- Adding format support doesn't require changes to docprep core -- just a new adapter package.
- Security surface is smaller: no native PDF/DOCX parsing code.

**Harder:**

- Users must install and configure external tools separately.
- Adapter quality depends on the external tool's output fidelity.
- The two-step workflow (convert then ingest) adds operational complexity compared to all-in-one tools.
- docprep cannot optimize the conversion step since it doesn't control it.
