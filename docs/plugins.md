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

### Adapters

docprep does not ship with any built-in adapters — this is by design. The `docprep.adapters` entry-point group is reserved for third-party packages. See [Adapters](adapters.md) for the rationale and how to write one.

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

## Protocol Contract Reference

Each protocol is decorated with `@runtime_checkable`, so you can verify conformance at runtime with `isinstance()`. All protocols live under `docprep.<component>.protocol`.

### Loader Protocol

```python
# docprep.loaders.protocol
class Loader(Protocol):
    def load(self, source: str | Path) -> Iterable[LoadedSource]: ...
```

**Contract:**

- Receive a file or directory path via `source`.
- Yield one `LoadedSource` per discovered file. Must not return an empty iterable for valid sources.
- Each `LoadedSource` must populate all required fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `source_path` | `str` | Yes | Filesystem path to the file |
| `source_uri` | `str` | Yes | Stable URI identifier (e.g. `file:docs/guide.md`) |
| `raw_text` | `str` | Yes | Full file contents as text |
| `checksum` | `str` | Yes | Content hash for change detection |
| `media_type` | `str` | No | MIME type (default: `text/markdown`) |
| `source_metadata` | `dict[str, object]` | No | Arbitrary metadata |

- Must not raise on empty directories — return an empty iterable instead.
- The `checksum` must be deterministic: same content → same checksum.

### Parser Protocol

```python
# docprep.parsers.protocol
class Parser(Protocol):
    def parse(self, loaded_source: LoadedSource) -> Document: ...
```

**Contract:**

- Receive a single `LoadedSource` and return a single `Document`.
- Must populate at minimum: `id`, `source_uri`, `title`, `source_checksum`, `body_markdown`.
- The `id` should be deterministic — same input must produce the same document ID.
- Sections and chunks should be left empty (`()`) — chunkers populate those.
- Raise on truly unrecoverable input (e.g. binary file passed as text). Use pipeline error handling for graceful degradation.

### Chunker Protocol

```python
# docprep.chunkers.protocol
class Chunker(Protocol):
    def chunk(self, document: Document) -> Document: ...
```

**Contract:**

- Receive a `Document` and return a **new** `Document` (documents are frozen dataclasses).
- The returned document must preserve all fields from the input except `sections` and/or `chunks`.
- Chunkers are chained: the first creates sections from `body_markdown`, subsequent ones split sections into chunks. Your chunker receives the output of the previous one.
- If the document has no `body_markdown` or no `sections`, return it unchanged.
- Each `Section` must have a deterministic `id` and a unique `anchor`.
- Each `Chunk` must have a deterministic `id`, `content_hash`, and `content_text`.

### Sink Protocol

```python
# docprep.sinks.protocol
class Sink(Protocol):
    def upsert(
        self,
        documents: Sequence[Document],
        *,
        run_id: uuid.UUID | None = None,
    ) -> SinkUpsertResult: ...
```

**Contract:**

- Receive a sequence of fully-chunked documents and persist them.
- Return a `SinkUpsertResult` with classified outcomes:

| Field | Type | Description |
|-------|------|-------------|
| `updated_source_uris` | `tuple[str, ...]` | URIs that were inserted or updated |
| `skipped_source_uris` | `tuple[str, ...]` | URIs skipped (checksum unchanged) |
| `deleted_source_uris` | `tuple[str, ...]` | URIs deleted during this operation |

- Must be idempotent: upserting the same documents twice should skip them on the second call.
- The `run_id` parameter is optional and used for revision tracking.

### Adapter Protocol

```python
# docprep.adapters.protocol
class Adapter(Protocol):
    def convert(self, source: str | Path) -> Iterable[Document]: ...

    @property
    def supported_extensions(self) -> frozenset[str]: ...
```

**Contract:**

- Convert external-format files into docprep `Document` objects.
- `supported_extensions` must return a frozenset of file extensions (with leading dot, e.g. `{".docx", ".pptx"}`).
- The returned documents should have `body_markdown` populated — adapters convert *to* Markdown, then the normal chunking pipeline takes over.
- See [Adapters](adapters.md) for the full rationale and design.

## Testing Your Plugin

### Protocol Conformance Check

Since all protocols are `@runtime_checkable`, you can verify conformance with a one-line assert:

```python
from docprep.chunkers.protocol import Chunker
from my_plugin import SentenceChunker

def test_protocol_conformance():
    assert isinstance(SentenceChunker(), Chunker)
```

This checks that your class has all required methods with compatible signatures. If it fails, you're missing a method or have an incompatible signature.

### Functional Test

Test your plugin with real data to verify behavior:

```python
import uuid
from docprep.models.domain import Document, Section

def test_chunker_produces_chunks():
    doc = Document(
        id=uuid.uuid5(uuid.NAMESPACE_DNS, "test"),
        source_uri="file:test.md",
        title="Test",
        source_checksum="abc123",
        body_markdown="First sentence. Second sentence.\n\nAnother paragraph.",
        sections=(
            Section(
                id=uuid.uuid5(uuid.NAMESPACE_DNS, "s1"),
                document_id=uuid.uuid5(uuid.NAMESPACE_DNS, "test"),
                order_index=0,
                anchor="root",
                content_markdown="First sentence. Second sentence.\n\nAnother paragraph.",
            ),
        ),
    )

    from my_plugin import SentenceChunker
    result = SentenceChunker().chunk(doc)

    assert len(result.chunks) > 0
    assert result.id == doc.id  # document identity preserved
    assert result.sections == doc.sections  # sections preserved
    for chunk in result.chunks:
        assert chunk.content_text  # no empty chunks
        assert chunk.content_hash  # hash populated
```

### Determinism Test

docprep relies on deterministic IDs. Verify your plugin produces identical output for identical input:

```python
def test_deterministic_output():
    chunker = SentenceChunker()
    result1 = chunker.chunk(doc)
    result2 = chunker.chunk(doc)
    assert result1.chunks == result2.chunks
```

## Local Development Workflow

### 1. Create Your Plugin Package

Use the [plugin template](https://github.com/yeongseon/docprep/tree/main/examples/plugin-template) as a starting point:

```bash
cp -r examples/plugin-template my-docprep-plugin
cd my-docprep-plugin
```

### 2. Install in Editable Mode

Install your plugin alongside docprep so changes take effect immediately:

```bash
pip install -e .
```

### 3. Verify Discovery

Check that docprep finds your plugin:

```python
from docprep import get_all_chunkers
print(get_all_chunkers())
# Should include your plugin's entry-point name
```

### 4. Use in Configuration

Reference your plugin by its entry-point name in `docprep.toml`:

```toml
[[chunkers]]
type = "sentence"
```

### 5. Run Tests

```bash
pytest tests/
```

## Complete Example

See [`examples/custom_plugin.py`](https://github.com/yeongseon/docprep/blob/main/examples/custom_plugin.py) for a full working example that implements a `ParagraphChunker`, demonstrates protocol conformance, compares output against built-in chunkers, and shows entry-point registration.

For a minimal project template you can copy and customize, see [`examples/plugin-template/`](https://github.com/yeongseon/docprep/tree/main/examples/plugin-template).
