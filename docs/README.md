# docprep Documentation

Welcome to the docprep documentation. docprep transforms source documents into structured, vector-ready chunks with deterministic IDs, Markdown-aware boundaries, and incremental sync.

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

## Design Decisions

Architecture Decision Records (ADRs) document key design choices:

| ADR | Decision |
|-----|----------|
| [0001 — Identity Model](decisions/0001-identity-model.md) | Anchor-based stable IDs with content hash |
| [0002 — Adapter-Not-Parser](decisions/0002-adapter-not-parser.md) | External tools parse, docprep normalizes |
| [0003 — Chunking Strategy](decisions/0003-chunking-strategy.md) | Markdown-aware boundaries, then token budgets |
| [0004 — Plugin Registry](decisions/0004-plugin-registry.md) | Entry-point discovery via `importlib.metadata` |
| [0005 — Diff-Then-Sync](decisions/0005-diff-then-sync.md) | Structural diff for incremental updates |
| [0006 — Export Contract](decisions/0006-export-contract.md) | VectorRecordV1 with mandatory provenance |

## Examples

Ready-to-run examples are in the [`examples/`](../examples/) directory:

| Example | Description |
|---------|-------------|
| [`markdown_to_sqlite.py`](../examples/markdown_to_sqlite.py) | Ingest Markdown files into SQLite |
| [`changed_only_export.py`](../examples/changed_only_export.py) | Export only changed chunks |
| [`configs/minimal.toml`](../examples/configs/minimal.toml) | Minimal configuration |
| [`configs/standard.toml`](../examples/configs/standard.toml) | Standard project configuration |
| [`configs/advanced.toml`](../examples/configs/advanced.toml) | Advanced multi-format configuration |

## Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md) for development setup, code style, and pull request guidelines.

## Security

See [SECURITY.md](../SECURITY.md) for vulnerability reporting.
