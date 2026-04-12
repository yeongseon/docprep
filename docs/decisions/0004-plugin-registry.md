# ADR-0004: Plugin Registry

**Status**: Accepted
**Date**: 2025-04-12
**Deciders**: Core team

## Context

docprep has four extension points: loaders, parsers, chunkers, and sinks. Third-party packages should be able to provide new implementations without modifying docprep's source code. We considered two approaches:

1. **Manual registration**: users call `registry.register("my-loader", MyLoader)` in their setup code. Simple, but requires boilerplate and doesn't work from config files or CLI.

2. **Entry-point discovery**: third-party packages declare their components in `pyproject.toml` metadata. docprep discovers them automatically at startup via `importlib.metadata.entry_points()`.

## Decision

We chose entry-point based discovery. Components are registered under these groups:

- `docprep.loaders`
- `docprep.parsers`
- `docprep.chunkers`
- `docprep.sinks`
- `docprep.adapters`

Built-in components are also registered as entry points in docprep's own `pyproject.toml`, so built-ins and third-party plugins use the same discovery mechanism.

Plugin import failures are handled gracefully: a warning is emitted, but the failure never prevents built-in components from loading. This means a broken plugin cannot take down the entire pipeline.

The registry provides:

- `discover_entry_points(group)` -- low-level discovery returning a name-to-class mapping.
- `get_all_loaders()`, `get_all_parsers()`, etc. -- merge built-ins with discovered plugins.
- `resolve_component(group, name)` -- look up a single component by name, with a clear error message listing available options if not found.

## Consequences

**Easier:**

- Third-party plugins work with `pip install` alone -- no setup code required.
- Config files and CLI can reference plugins by name.
- Built-in and third-party components are treated uniformly.
- Broken plugins degrade gracefully with actionable warnings.

**Harder:**

- Entry-point registration requires package metadata (`pyproject.toml`), which adds friction for quick prototyping.
- Plugin discovery adds startup overhead (scanning installed packages). This is mitigated by caching in `importlib.metadata`.
- Debugging plugin load failures requires understanding the entry-point system, which may be unfamiliar to some users.
