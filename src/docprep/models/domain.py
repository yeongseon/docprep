"""Domain dataclasses for the docprep pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import sys

if sys.version_info >= (3, 11):
    from enum import StrEnum  # pyright: ignore[reportUnknownImportSymbol]
else:
    from enum import Enum

    class StrEnum(str, Enum):
        """Backport for Python < 3.11."""

        pass


from typing import final
import uuid

from ..metadata import Metadata


@final
class PipelineStage(StrEnum):  # pyright: ignore[reportUntypedBaseClass]
    LOAD = "load"
    PARSE = "parse"
    CHUNK = "chunk"
    PERSIST = "persist"
    RUN = "run"


@final
class ErrorMode(StrEnum):  # pyright: ignore[reportUntypedBaseClass]
    FAIL_FAST = "fail_fast"
    CONTINUE_ON_ERROR = "continue_on_error"


@final
class StructureKind(StrEnum):  # pyright: ignore[reportUntypedBaseClass]
    CODE_FENCE = "code_fence"
    TABLE = "table"
    LIST = "list"


@dataclass(frozen=True, kw_only=True, slots=True)
class Section:
    """A heading-delimited section within a document."""

    id: uuid.UUID
    document_id: uuid.UUID
    order_index: int
    parent_id: uuid.UUID | None = None
    heading: str | None = None
    heading_level: int = 0
    anchor: str = ""
    content_hash: str = ""
    heading_path: tuple[str, ...] = ()
    lineage: tuple[str, ...] = ()
    content_markdown: str = ""


@dataclass(frozen=True, kw_only=True, slots=True)
class Chunk:
    """A sized text chunk derived from a section."""

    id: uuid.UUID
    document_id: uuid.UUID
    section_id: uuid.UUID
    order_index: int
    section_chunk_index: int
    anchor: str = ""
    content_hash: str = ""
    content_text: str
    char_start: int = 0
    char_end: int = 0
    token_count: int | None = None
    heading_path: tuple[str, ...] = ()
    lineage: tuple[str, ...] = ()
    structure_types: tuple[str, ...] = ()


@dataclass(frozen=True, kw_only=True, slots=True)
class DocumentError:
    source_uri: str
    stage: PipelineStage
    error_type: str
    message: str


@dataclass(frozen=True, kw_only=True, slots=True)
class StructuralAnnotation:
    """A structural element span within body_markdown."""

    kind: StructureKind
    char_start: int
    char_end: int


@dataclass(frozen=True, kw_only=True, slots=True)
class Document:
    """A fully parsed and optionally chunked document."""

    id: uuid.UUID
    source_uri: str
    title: str
    source_checksum: str
    source_type: str = "markdown"
    frontmatter: Metadata = field(default_factory=dict)
    source_metadata: Metadata = field(default_factory=dict)
    body_markdown: str = ""
    structural_annotations: tuple[StructuralAnnotation, ...] = ()
    sections: tuple[Section, ...] = ()
    chunks: tuple[Chunk, ...] = ()


@dataclass(frozen=True, kw_only=True, slots=True)
class DocumentRevision:
    """A snapshot of a document's structural state at a point in time."""

    id: uuid.UUID
    document_id: uuid.UUID
    source_uri: str
    source_checksum: str
    revision_number: int
    ingestion_run_id: uuid.UUID | None = None
    section_anchors: tuple[str, ...] = ()
    chunk_anchors: tuple[str, ...] = ()
    section_hashes: tuple[str, ...] = ()
    chunk_hashes: tuple[str, ...] = ()
    is_current: bool = True
    timestamp: str = ""


@dataclass(frozen=True, kw_only=True, slots=True)
class SectionDelta:
    """Change status of a single section between revisions."""

    anchor: str
    status: str
    previous_hash: str | None = None
    current_hash: str | None = None


@dataclass(frozen=True, kw_only=True, slots=True)
class ChunkDelta:
    """Change status of a single chunk between revisions."""

    anchor: str
    status: str
    previous_hash: str | None = None
    current_hash: str | None = None


@dataclass(frozen=True, kw_only=True, slots=True)
class DiffSummary:
    """Aggregate counts per status category."""

    sections_added: int = 0
    sections_removed: int = 0
    sections_modified: int = 0
    sections_unchanged: int = 0
    chunks_added: int = 0
    chunks_removed: int = 0
    chunks_modified: int = 0
    chunks_unchanged: int = 0


@dataclass(frozen=True, kw_only=True, slots=True)
class RevisionDiff:
    """Structural diff between two revisions of the same document."""

    source_uri: str
    previous_revision: str
    current_revision: str
    section_deltas: tuple[SectionDelta, ...] = ()
    chunk_deltas: tuple[ChunkDelta, ...] = ()
    summary: DiffSummary = field(default_factory=DiffSummary)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, kw_only=True, slots=True)
class Page:
    """A bounded page of results with cursor info."""

    items: tuple[object, ...] = ()
    total: int = 0
    offset: int = 0
    limit: int = 50
    has_more: bool = False


@final
class DeletePolicy(StrEnum):  # pyright: ignore[reportUntypedBaseClass]
    HARD_DELETE = "hard_delete"
    IGNORE = "ignore"


@dataclass(frozen=True, kw_only=True, slots=True)
class DeleteResult:
    """Result of a delete operation."""

    deleted_source_uris: tuple[str, ...] = ()
    deleted_document_count: int = 0
    deleted_section_count: int = 0
    deleted_chunk_count: int = 0
    deleted_revision_count: int = 0
    dry_run: bool = False


@dataclass(frozen=True, kw_only=True, slots=True)
class SyncResult:
    """Result of a sync operation - upsert + prune stale."""

    upsert_result: SinkUpsertResult
    delete_result: DeleteResult


@dataclass(frozen=True, kw_only=True, slots=True)
class VectorRecord:
    """A vector-ready record for embedding and retrieval."""

    id: uuid.UUID
    text: str
    metadata: Metadata = field(default_factory=dict)


@final
class TextPrependStrategy(StrEnum):  # pyright: ignore[reportUntypedBaseClass]
    NONE = "none"
    TITLE_ONLY = "title_only"
    HEADING_PATH = "heading_path"
    TITLE_AND_HEADING_PATH = "title_and_heading_path"


@dataclass(frozen=True, kw_only=True, slots=True)
class VectorRecordV1:
    id: uuid.UUID
    document_id: uuid.UUID
    section_id: uuid.UUID
    chunk_anchor: str
    section_anchor: str
    text: str
    content_hash: str
    char_count: int
    source_uri: str
    title: str
    section_path: tuple[str, ...]
    schema_version: int
    pipeline_version: str
    created_at: str
    user_metadata: Metadata = field(default_factory=dict)


@dataclass(frozen=True, kw_only=True, slots=True)
class SinkUpsertResult:
    """Result of a sink upsert operation with classified outcomes."""

    skipped_source_uris: tuple[str, ...] = ()
    updated_source_uris: tuple[str, ...] = ()
    deleted_source_uris: tuple[str, ...] = ()


@dataclass(frozen=True, kw_only=True, slots=True)
class SourceScope:
    """The set of source URIs a given run is authoritative for."""

    prefixes: tuple[str, ...]
    explicit: bool = False


@dataclass(frozen=True, kw_only=True, slots=True)
class RunManifest:
    """Records what happened during an ingestion run."""

    run_id: uuid.UUID
    scope: SourceScope
    source_uris_seen: tuple[str, ...]
    timestamp: str


@dataclass(frozen=True, kw_only=True, slots=True)
class IngestStageReport:
    """Timing and counts for a single pipeline stage."""

    stage: PipelineStage
    elapsed_ms: float
    input_count: int = 0
    output_count: int = 0
    failed_count: int = 0


@dataclass(frozen=True, kw_only=True, slots=True)
class IngestResult:
    """Summary of an ingest pipeline run."""

    documents: tuple[Document, ...]
    processed_count: int = 0
    skipped_count: int = 0
    updated_count: int = 0
    deleted_count: int = 0
    failed_count: int = 0
    skipped_source_uris: tuple[str, ...] = ()
    updated_source_uris: tuple[str, ...] = ()
    deleted_source_uris: tuple[str, ...] = ()
    failed_source_uris: tuple[str, ...] = ()
    errors: tuple[DocumentError, ...] = ()
    stage_reports: tuple[IngestStageReport, ...] = ()
    persisted: bool = False
    sink_name: str | None = None
    run_manifest: RunManifest | None = None
