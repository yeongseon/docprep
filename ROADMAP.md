# Roadmap

docprep is currently in **Alpha**. The core pipeline — deterministic chunk IDs, incremental sync, changed-only export — is stable and tested (95%+ branch coverage). This roadmap outlines what's next.

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
- [x] Built-in progress reporting with callback hooks
- [ ] Schema migration tooling for sink database upgrades
- [ ] Export format plugins (Parquet, CSV)
- [ ] Documentation site hosted on GitHub Pages via MkDocs

## Beta Entry Criteria

docprep will move to Beta when:

1. **Stability** — No breaking API changes for 3+ minor releases
2. **Coverage** — 95%+ branch coverage maintained (currently met)
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
- **SQLAlchemy sink only.** Vector database sinks are intentionally third-party — see [ADR-0007](docs/decisions/0007-sqlalchemy-canonical-persistence.md) for the rationale.

### What May Change Before Beta

These areas are functional but not yet stabilized:

| Area | Current State | What May Change | Impact |
|------|--------------|-----------------|--------|
| `docprep.toml` schema | Working, all options documented | Keys may be renamed or restructured | Re-edit config file |
| Plugin entry-point contracts | Functional for all 4 component types | Protocol method signatures may evolve | Update third-party plugins |
| Sink database schema | SQLite/PostgreSQL working | No migration tooling yet | Re-ingest to rebuild |
| `VectorRecordV1` export | Stable, 15 fields documented | Future V2 would be additive, not breaking | No action needed |
| CLI command surface | 9 commands available | Flags/options may change | Update scripts |

Pin your docprep version (`docprep==0.1.1`) and test upgrades in a staging environment before production use.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to get involved. Feature requests and plugin contributions are welcome.
