# Roadmap

docprep is currently in **Alpha**. The core pipeline — deterministic chunk IDs, incremental sync, changed-only export — is stable and tested (90%+ branch coverage). This roadmap outlines what's next.

## Current Status (Alpha)

What works today:

- Markdown, Plaintext, HTML, RST parsing
- Heading, Size, Token chunking strategies
- SQLAlchemy sink (SQLite, PostgreSQL)
- Deterministic chunk IDs and revision tracking
- Incremental sync with structural diff
- Changed-only JSONL export (VectorRecordV1)
- Entry-point plugin system for all component types
- CLI with ingest, preview, diff, export, stats, inspect, prune, delete, migrate
- Environment variable overrides (`DOCPREP_*`)

## Compatibility Matrix

| Component | Built-in | Planned | Community |
|-----------|----------|---------|-----------|
| **Loaders** | Markdown, FileSystem | — | — |
| **Parsers** | Markdown, Plaintext, HTML, RST, Auto | — | — |
| **Chunkers** | Heading, Size, Token | Semantic (LLM-guided) | — |
| **Sinks** | SQLAlchemy (SQLite, PostgreSQL) | — | — |
| **Adapters** | *(none — by design)* | — | MarkItDown, Docling |
| **Export** | JSONL (VectorRecordV1) | — | — |

## Short-Term (Next Minor Releases)

- [ ] Cross-platform CI (Windows, macOS runners)
- [ ] Plugin contract test suite (`docprep.testing`) for third-party plugin authors
- [ ] `docprep scaffold` CLI command for generating plugin project boilerplate
- [ ] Async sink support for high-throughput pipelines

## Medium-Term (Beta)

- [ ] Streaming pipeline mode (process documents without loading all into memory)
- [ ] Built-in progress reporting with callback hooks
- [ ] Schema migration tooling for sink database upgrades
- [ ] Export format plugins (Parquet, CSV)
- [ ] Documentation site hosted on GitHub Pages via MkDocs

## Beta Entry Criteria

docprep will move to Beta when:

1. **Stability** — No breaking API changes for 3+ minor releases
2. **Coverage** — 90%+ branch coverage maintained (currently met)
3. **Cross-platform** — CI passes on Ubuntu, macOS, and Windows
4. **Documentation** — All public APIs documented with examples
5. **Community** — At least one third-party plugin published

## Long-Term (Stable 1.0)

- [ ] Stable public API with semantic versioning guarantees
- [ ] Performance benchmarks in CI (regression detection)
- [ ] Plugin marketplace / registry
- [ ] Language server integration for `docprep.toml` validation

## Known Limitations

- **No built-in adapters.** docprep deliberately delegates format conversion to external tools (MarkItDown, Docling, Unstructured). See [Adapters](docs/adapters.md).
- **Single-process only.** No distributed processing support yet.
- **SQLAlchemy sink only.** Vector database sinks require third-party plugins.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to get involved. Feature requests and plugin contributions are welcome.
