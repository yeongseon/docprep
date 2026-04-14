# docprep Documentation

Welcome to the docprep documentation. docprep is a document ingestion layer for RAG pipelines — deterministic chunk IDs, incremental sync, and changed-only export.

## Guides

| Guide | Description |
|-------|-------------|
| [Getting Started](getting-started.md) | Installation, first ingestion, basic usage |
| [Configuration](configuration.md) | `docprep.toml` reference, all options |
| [CLI Reference](cli-reference.md) | All commands, flags, and examples |
| [Python API](python-api.md) | Types, functions, and usage patterns |

## Concepts

| Topic | Description |
|-------|-------------|
| [Architecture](architecture.md) | Pipeline flow, module map, identity model |
| [Export](export.md) | VectorRecordV1, JSONL, changed-only export |
| [Plugins](plugins.md) | Entry-point plugin system, custom components |
| [Adapters](adapters.md) | External converter integration (MarkItDown, Docling, etc.) |
| [Lifecycle](lifecycle.md) | Deletion, sync, prune, and change detection semantics |
| [Performance](performance.md) | Benchmark results, cost savings, concurrency |

## Design Decisions

Architecture Decision Records (ADRs) document key design choices:

| ADR | Decision |
|-----|----------|
| [0001 — Identity Model](decisions/0001-identity-model.md) | Anchor-based stable IDs with position-based chunk anchors |
| [0002 — Adapter-Not-Parser](decisions/0002-adapter-not-parser.md) | External tools parse, docprep normalizes |
| [0003 — Chunking Strategy](decisions/0003-chunking-strategy.md) | Markdown-aware boundaries, then token budgets |
| [0004 — Plugin Registry](decisions/0004-plugin-registry.md) | Entry-point discovery via `importlib.metadata` |
| [0005 — Diff-Then-Sync](decisions/0005-diff-then-sync.md) | Structural diff for incremental updates |
| [0006 — Export Contract](decisions/0006-export-contract.md) | VectorRecordV1 with mandatory provenance |

## Examples

Ready-to-run examples are in the [`examples/`](https://github.com/yeongseon/docprep/tree/main/examples) directory:

| Example | Description |
|---------|-------------|
| [`markdown_to_sqlite.py`](https://github.com/yeongseon/docprep/blob/main/examples/markdown_to_sqlite.py) | Ingest Markdown files into SQLite |
| [`changed_only_export.py`](https://github.com/yeongseon/docprep/blob/main/examples/changed_only_export.py) | Export only changed chunks |
| [`incremental_sync_demo.py`](https://github.com/yeongseon/docprep/blob/main/examples/incremental_sync_demo.py) | Step-by-step incremental sync walkthrough |
| [`benchmark_incremental_sync.py`](https://github.com/yeongseon/docprep/blob/main/examples/benchmark_incremental_sync.py) | Benchmark: re-embedding savings with incremental sync |
| [`configs/minimal.toml`](https://github.com/yeongseon/docprep/blob/main/examples/configs/minimal.toml) | Minimal configuration |
| [`configs/standard.toml`](https://github.com/yeongseon/docprep/blob/main/examples/configs/standard.toml) | Standard project configuration |
| [`configs/advanced.toml`](https://github.com/yeongseon/docprep/blob/main/examples/configs/advanced.toml) | Advanced multi-format configuration |
| [`quickstart.py`](https://github.com/yeongseon/docprep/blob/main/examples/quickstart.py) | Hello World — minimal 5-line ingest example |
| [`cli_quickstart.sh`](https://github.com/yeongseon/docprep/blob/main/examples/cli_quickstart.sh) | CLI workflow walkthrough (preview → ingest → export → diff) |
| [`adapter_markitdown.py`](https://github.com/yeongseon/docprep/blob/main/examples/adapter_markitdown.py) | Custom adapter (CSV→Markdown + MarkItDown pattern) |
| [`vector_store_integration.py`](https://github.com/yeongseon/docprep/blob/main/examples/vector_store_integration.py) | Qdrant, ChromaDB, and JSONL export patterns |
| [`custom_plugin.py`](https://github.com/yeongseon/docprep/blob/main/examples/custom_plugin.py) | Custom chunker plugin with entry-point registration |
| [`error_handling.py`](https://github.com/yeongseon/docprep/blob/main/examples/error_handling.py) | Error modes, progress callbacks, exception hierarchy |
| [`large_corpus.py`](https://github.com/yeongseon/docprep/blob/main/examples/large_corpus.py) | Parallel ingestion, checkpoints, streaming export |
| [`sample_docs/`](https://github.com/yeongseon/docprep/tree/main/examples/sample_docs) | Sample Markdown files used by examples |

## Contributing

See [CONTRIBUTING.md](https://github.com/yeongseon/docprep/blob/main/CONTRIBUTING.md) for development setup, code style, and pull request guidelines.

## Security

See [SECURITY.md](https://github.com/yeongseon/docprep/blob/main/SECURITY.md) for vulnerability reporting.
