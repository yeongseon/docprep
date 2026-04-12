# ADR-0003: Chunking Strategy

**Status**: Accepted
**Date**: 2025-04-12
**Deciders**: Core team

## Context

LLMs and embedding models have context windows measured in tokens. Source documents must be split into chunks that fit these windows. Naive fixed-size chunking (split every N characters) creates several problems:

- **Broken syntax**: a chunk boundary can land in the middle of a code fence, table, or blockquote, producing fragments that confuse LLMs.
- **Lost context**: without heading hierarchy, a chunk like "See the example below" has no indication of what section it belongs to.
- **Inconsistent sizing**: paragraphs, code blocks, and tables vary wildly in length, making fixed-size cuts unreliable.

We needed chunking that respects document structure while staying within token budgets.

## Decision

Chunking happens in two stages, implemented as composable chunker components:

1. **HeadingChunker** (structural): Splits a document into sections based on Markdown headings. Each section inherits its heading hierarchy as metadata (`heading_path`). This establishes the document's logical structure.

2. **SizeChunker / TokenChunker** (budget): Splits sections into token-budget-constrained chunks. Splitting happens at natural boundaries in priority order: paragraph breaks, sentence endings, then newlines. A shared `_markdown.py` module identifies Markdown block boundaries (fenced code blocks, blockquotes, tables) to prevent mid-syntax splits.

Key rules:

- Chunks never split in the middle of a fenced code block, table, or blockquote.
- Each chunk carries `heading_path` from its parent section for context.
- Multiple chunkers can be composed in sequence (heading first, then size/token).
- The `Chunker` protocol is simple: `chunk(document: Document) -> Document`.

## Consequences

**Easier:**

- Chunks are self-contained and LLM-friendly.
- Heading hierarchy is preserved as metadata, enabling section-aware retrieval.
- Composable chunker chain lets users tune the strategy without modifying core.
- Markdown syntax is never broken across chunk boundaries.

**Harder:**

- Very short sections (e.g., a one-line heading with a brief paragraph) produce very small chunks that may be below the useful size threshold.
- Extremely long code blocks that exceed the token budget cannot be split further -- they become oversized chunks.
- The Markdown-aware boundary analysis adds complexity compared to naive splitting.
- Non-Markdown content (RST, HTML) is converted to Markdown-like headings before chunking, which may lose some structural nuance.
