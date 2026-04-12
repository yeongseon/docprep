# Plugin System

docprep uses Python [entry points](https://packaging.python.org/en/latest/specifications/entry-points/) for plugin discovery. Third-party packages can provide custom loaders, parsers, chunkers, sinks, and adapters — no core modification required.

## Entry-Point Groups

| Group | Protocol | Description |
|-------|----------|-------------|
| `docprep.loaders` | `Loader` | Load raw content from sources |
| `docprep.parsers` | `Parser` | Parse loaded sources into Documents |
| `docprep.chunkers` | `Chunker` | Split documents into sections/chunks |
| `docprep.sinks` | `Sink` | Persist documents to storage |
| `docprep.adapters` | `Adapter` | Convert external formats to Documents |

## Creating a Plugin

### 1. Implement the Protocol

Each component type has a protocol defined in `docprep`. Your class must implement the required methods.

**Loader** — loads raw content from a source path:

```python
from collections.abc import Iterable
from pathlib import Path
from docprep.loaders.types import LoadedSource

class MyLoader:
    def load(self, source: str | Path) -> Iterable[LoadedSource]:
        # Yield LoadedSource objects for each file
        yield LoadedSource(
            source_path=str(source),
            source_uri=f"file:{source}",
            raw_text="...",
            checksum="...",
            media_type="text/markdown",
        )
```

**Parser** — converts a `LoadedSource` into a `Document`:

```python
from docprep.loaders.types import LoadedSource
from docprep.models.domain import Document

class MyParser:
    def parse(self, loaded_source: LoadedSource) -> Document:
        return Document(
            id=...,
            source_uri=loaded_source.source_uri,
            title="...",
            source_checksum=loaded_source.checksum,
            body_markdown=loaded_source.raw_text,
        )
```

**Chunker** — transforms a Document (adds sections and/or chunks):

```python
from docprep.models.domain import Document

class MyChunker:
    def chunk(self, document: Document) -> Document:
        # Split document into sections/chunks and return
        # a new Document with populated sections and chunks
        ...
```

**Sink** — persists documents to a storage backend:

```python
from collections.abc import Sequence
import uuid
from docprep.models.domain import Document, SinkUpsertResult

class MySink:
    def upsert(
        self,
        documents: Sequence[Document],
        *,
        run_id: uuid.UUID | None = None,
    ) -> SinkUpsertResult:
        # Persist documents and return result
        return SinkUpsertResult(
            updated_source_uris=tuple(d.source_uri for d in documents),
        )
```

**Adapter** — converts external tool output into docprep Documents:

```python
from collections.abc import Iterable
from pathlib import Path
from docprep.models.domain import Document

class MyAdapter:
    def convert(self, source: str | Path) -> Iterable[Document]:
        # Convert source files to Documents
        ...

    @property
    def supported_extensions(self) -> frozenset[str]:
        return frozenset({".docx", ".pptx"})
```

### 2. Register the Entry Point

In your package's `pyproject.toml`:

```toml
[project.entry-points."docprep.parsers"]
my-format = "my_package.parser:MyFormatParser"

[project.entry-points."docprep.chunkers"]
semantic = "my_package.chunker:SemanticChunker"

[project.entry-points."docprep.loaders"]
s3 = "my_package.loader:S3Loader"

[project.entry-points."docprep.sinks"]
qdrant = "my_package.sink:QdrantSink"

[project.entry-points."docprep.adapters"]
docling = "my_package.adapter:DoclingAdapter"
```

Or in `setup.cfg`:

```ini
[options.entry_points]
docprep.parsers =
    my-format = my_package.parser:MyFormatParser
```

### 3. Install and Use

After installing your plugin package, docprep discovers it automatically:

```python
from docprep import get_all_parsers

parsers = get_all_parsers()
print(parsers)
# {'markdown': <class 'MarkdownParser'>, ..., 'my-format': <class 'MyFormatParser'>}
```

## Built-in Components

docprep ships with these built-in components:

### Loaders

| Name | Class | Description |
|------|-------|-------------|
| `markdown` | `MarkdownLoader` | Loads `.md` files with glob pattern |
| `filesystem` | `FileSystemLoader` | Multi-format loader with include/exclude globs |

### Parsers

| Name | Class | Description |
|------|-------|-------------|
| `markdown` | `MarkdownParser` | Frontmatter extraction, heading hierarchy |
| `plaintext` | `PlainTextParser` | First non-empty line as title |
| `html` | `HtmlParser` | Strips script/style, converts headings |
| `rst` | `RstParser` | Heading adornments, field lists |
| `auto` | `MultiFormatParser` | Auto-dispatch by media type |

### Chunkers

| Name | Class | Description |
|------|-------|-------------|
| `heading` | `HeadingChunker` | Split by headings into sections |
| `size` | `SizeChunker` | Character-count splitting |
| `token` | `TokenChunker` | Token-budget splitting |

### Sinks

| Name | Class | Description |
|------|-------|-------------|
| `sqlalchemy` | `SQLAlchemySink` | SQLAlchemy persistence + revision tracking |

## Error Handling

Plugin import failures produce warnings but **never break** built-in components. If a plugin fails to load, docprep logs a warning and continues:

```
WARNING: Failed to load plugin 'my-format' from 'docprep.parsers'
(my_package.parser:MyFormatParser). Check that the package and its
dependencies are installed correctly. Error: ModuleNotFoundError(...)
```

## Discovering Plugins Programmatically

```python
from docprep.plugins import discover_entry_points

# Discover all installed plugins for a group
plugins = discover_entry_points("docprep.parsers")
for name, obj in plugins.items():
    print(f"{name}: {obj}")
```

The `discover_entry_points()` function returns a dict mapping entry-point names to loaded objects. It only returns externally registered plugins — use `get_all_parsers()` etc. for the combined built-in + plugin listing.
