from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from docprep.ingest import Ingestor
from docprep.models.domain import IngestResult


def _ingest_fixture(name: str) -> IngestResult:
    fixture_path = Path(__file__).parent / "fixtures" / name
    return Ingestor().run(fixture_path)


@dataclass(frozen=True)
class FixtureExpectation:
    title: str
    section_headings: tuple[str | None, ...]
    chunks: tuple[str, ...]


_GOLDEN_EXPECTATIONS: dict[str, FixtureExpectation] = {
    "frontmatter_heavy.md": FixtureExpectation(
        title="Frontmatter Heavy Fixture",
        section_headings=("Overview", "Data Model", "Operational Notes"),
        chunks=(
            "This fixture validates that rich frontmatter survives normalization while heading-based sectioning still follows body structure.\n\nThe narrative includes enough prose to look like a real technical document.",
            "`Document`, `Section`, and `Chunk` form a deterministic graph.\n\nStable IDs ensure downstream storage can perform upserts without semantic drift.",
            "When a parser upgrade changes output shape, this fixture should fail loudly and force explicit review.",
        ),
    ),
    "heading_free.md": FixtureExpectation(
        title="heading_free",
        section_headings=(None,),
        chunks=(
            "This document intentionally has no Markdown headings. It starts with a plain paragraph that includes **bold text**, *italic text*, and `inline code` to make sure inline syntax does not affect section splitting.\n\nA second paragraph references release cadence, schema migration timing, and alert handling. None of this should create additional sections because there are still no heading markers.\n\nFinal paragraph: ingest pipelines often process messy prose documents, and this fixture simulates that shape without introducing structural markers.",
        ),
    ),
    "fenced_code_blocks.md": FixtureExpectation(
        title="Fenced Code Blocks",
        section_headings=("Fenced Code Blocks",),
        chunks=(
            'This fixture mixes prose and fenced code so the chunker must preserve ordering while splitting oversized sections.\n\n```python\nrecords = [\n    "line-001",\n    "line-002",\n    "line-003",\n    "line-004",\n    "line-005",\n    "line-006",\n    "line-007",\n    "line-008",\n    "line-009",\n    "line-010",\n    "line-011",\n    "line-012",\n    "line-013",\n    "line-014",\n    "line-015",\n    "line-016",\n    "line-017",\n    "line-018",\n    "line-019",\n    "line-020",\n    "line-021",\n    "line-022",\n    "line-023",\n    "line-024",\n    "line-025",\n    "line-026",\n    "line-027",\n    "line-028",\n    "line-029",\n    "line-030",\n    "line-031",\n    "line-032",\n    "line-033",\n    "line-034",\n    "line-035",\n    "line-036",\n    "line-037",\n    "line-038",\n    "line-039",\n    "line-040",\n    "line-041",\n    "line-042",\n    "line-043",\n    "line-044",\n    "line-045",\n    "line-046",\n    "line-047",\n    "line-048",\n    "line-049",\n    "line-050",\n    "line-051",\n    "line-052",\n    "line-053",\n    "line-054",\n    "line-055",\n]\n\nfor entry in records:\n    payload = {"entry": entry, "ok": True}\n    print(payload)\n```\n\nThe section above has a long fenced block that should cross the default max chunk size.\n\n```json\n{\n  "service": "docprep",\n  "pipeline": ["load", "parse", "chunk", "persist"],\n  "owner": "docs-platform"\n}\n```\n\n```bash\npython -m docprep preview docs/\npython -m docprep ingest docs/ --db sqlite:///docs.db\n```',
        ),
    ),
    "large_table.md": FixtureExpectation(
        title="Service Matrix",
        section_headings=("Service Matrix", "Core Services", "Supporting Services"),
        chunks=(
            "The tables below mimic compatibility grids used during migration planning.",
            "| Service | Owner | SLA | Region | Notes |\n| --- | --- | --- | --- | --- |\n| ingest-api | docs | 99.9% | us-east-1 | Primary endpoint |\n| parser-worker | docs | 99.5% | us-east-1 | Parse frontmatter |\n| chunk-worker | search | 99.5% | us-east-1 | Split sections |\n| vector-writer | ml | 99.0% | us-east-1 | Persist vectors |\n| metadata-sync | platform | 99.9% | us-west-2 | Nightly cleanup |\n| audit-export | compliance | 99.0% | eu-central-1 | Signed package |\n| retry-queue | platform | 99.9% | us-east-1 | Retry orchestration |\n| checksum-cache | platform | 99.5% | us-east-1 | Dedup support |\n| docs-webhook | docs | 99.0% | ap-northeast-2 | CMS trigger |\n| index-warmup | search | 98.0% | us-west-2 | Preload index |\n| schema-registry | platform | 99.9% | us-east-1 | Contract checks |",
            "| Service | Owner | SLA | Region | Notes |\n| --- | --- | --- | --- | --- |\n| batch-loader | docs | 99.0% | us-east-1 | Backfill ingest |\n| stream-loader | docs | 99.0% | us-east-1 | Near realtime |\n| pii-redactor | compliance | 99.9% | eu-west-1 | Data minimization |\n| locale-detector | ml | 98.5% | ap-south-1 | Language hints |\n| quality-scorer | ml | 98.5% | us-east-1 | Quality gate |\n| retention-janitor | platform | 99.9% | us-west-2 | TTL cleanup |\n| event-bridge | platform | 99.5% | us-east-1 | Event fan-out |\n| status-dashboard | sre | 99.9% | global | Visibility |\n| pager-router | sre | 99.9% | global | Incident routing |\n| docs-validator | docs | 99.0% | us-east-1 | Lint markdown |\n| release-notifier | docs | 99.0% | us-east-1 | Team updates |\n\nFollow-up text ensures table parsing does not swallow trailing prose.",
        ),
    ),
    "blockquote_nested_list.md": FixtureExpectation(
        title="Incident Review Notes",
        section_headings=("Incident Review Notes",),
        chunks=(
            "> Primary timeline summary:\n>\n> 1. Alert fired at 09:12 UTC.\n> 2. On-call validated checksum mismatch symptoms.\n>    - Scope was limited to one ingestion shard.\n>    - Backfill jobs were paused to avoid duplicate writes.\n>\n> Additional context paragraph inside the same quote block. It captures rationale for delaying restarts until queue depth stabilized.\n\n1. Immediate actions\n   - Acknowledge alert in pager system.\n   - Capture affected source URIs.\n\n   This paragraph belongs to the same list item and explains why preserving paragraph continuity matters.\n\n2. Recovery actions\n   1. Restart parser workers.\n   2. Re-run failed ingestion window.\n   3. Confirm section and chunk counts align with baseline.\n\n- Postmortem checklist\n  - [x] Timeline drafted\n  - [x] Stakeholders informed\n  - [ ] Add invariant regression tests",
        ),
    ),
    "korean_english_mixed.md": FixtureExpectation(
        title="문서 수집 파이프라인 개요",
        section_headings=(
            "문서 수집 파이프라인 개요",
            "처리 단계 Processing Stages",
            "품질 확인 Quality Checks",
        ),
        chunks=(
            "이 문서는 Markdown ingestion pipeline의 동작을 설명합니다. 섹션 분할은 heading 기반으로 동작하고, chunking은 max_chars 제한을 따릅니다.",
            '로드(load) -> 파싱(parse) -> 청킹(chunk) -> 저장(persist) 순서로 실행됩니다.\n\n```python\nfrom docprep import ingest\n\nresult = ingest("docs/")\nprint(result.processed_count)\n```',
            "UUID determinism, content coverage, 그리고 ordering invariants를 함께 검증해야 운영 중 회귀를 빨리 탐지할 수 있습니다.",
        ),
    ),
    "unicode_emoji.md": FixtureExpectation(
        title="Unicode Playground",
        section_headings=("Unicode Playground",),
        chunks=(
            "CJK sample: 漢字とかな交じり文で挙動を確認します。\n\nArabic sample: هذا سطر عربي لاختبار معالجة النصوص واتجاه الكتابة.\n\nCyrillic sample: Проверяем стабильность разбиения и идентификаторов.\n\nEmoji sample: 🚀✅🧪📚  These markers appear in many engineering docs.\n\nSpecial symbols: © ™ § ¶ • ∞ ≈ != <= >=",
        ),
    ),
    "link_heavy.md": FixtureExpectation(
        title="Link Inventory",
        section_headings=("Link Inventory", "Secondary References"),
        chunks=(
            'Inline links: [Project Home](https://example.com/home), [Runbook](https://example.com/runbook), and [Status](https://status.example.com).\n\nReference links appear throughout this paragraph to emulate documentation style: [API Docs][api], [Schema][schema], [On-call Rotation][oncall], and [Incident Archive][archive].\n\nAutolinks are also common: <https://docs.python.org/3/library/pathlib.html> and <mailto:alerts@example.com>.\n\n![Architecture Diagram](https://example.com/images/architecture.png "system architecture")',
            "See [Chunking Guide][chunking] and [Parser Notes][parser-notes] for implementation details.\n\n[api]: https://example.com/api\n[schema]: https://example.com/schema\n[oncall]: https://example.com/oncall\n[archive]: https://example.com/incidents\n[chunking]: https://example.com/chunking\n[parser-notes]: https://example.com/parser-notes",
        ),
    ),
    "single_long_paragraph.md": FixtureExpectation(
        title="single_long_paragraph",
        section_headings=(None,),
        chunks=(
            "This fixture contains a single intentionally long paragraph with no headings and no structural delimiters so the size chunker must perform deterministic hard splits when the content exceeds the default character budget used by the ingestion pipeline and this sentence keeps extending with operational language about checksums ordering idempotency retries observability and schema evolution to resemble realistic technical prose in production documentation where engineers write dense narratives without stopping for section markers and where downstream systems still need stable chunk boundaries for embedding generation and retrieval quality analysis across repeated ingest runs in continuous integration environments this fixture contains a single intentionally long paragraph with no headings and no structural delimiters so the size chunker must perform deterministic hard splits when the content exceeds the default character budget used by the ingestion pipeline and this sentence keeps extending with operational language about checksums ordering idempotency retries observability and schema evolution to resemble realistic technical prose in production documentation where engineers write dense narratives without stopping for section markers and where downstream systems still need stable chunk boundaries for embedding generation and retrieval quality analysis across repeated ingest runs in continuous integration environments this fixture contains a single intentionally long paragraph wi",
            "th no headings and no structural delimiters so the size chunker must perform deterministic hard splits when the content exceeds the default character budget used by the ingestion pipeline and this sentence keeps extending with operational language about checksums ordering idempotency retries observability and schema evolution to resemble realistic technical prose in production documentation where engineers write dense narratives without stopping for section markers and where downstream systems still need stable chunk boundaries for embedding generation and retrieval quality analysis across repeated ingest runs in continuous integration environments this fixture contains a single intentionally long paragraph with no headings and no structural delimiters so the size chunker must perform deterministic hard splits when the content exceeds the default character budget used by the ingestion pipeline and this sentence keeps extending with operational language about checksums ordering idempotency retries observability and schema evolution to resemble realistic technical prose in production documentation where engineers write dense narratives without stopping for section markers and where downstream systems still need stable chunk boundaries for embedding generation and retrieval quality analysis across repeated ingest runs in continuous integration environments this fixture contains a single intentionally long paragraph with no headings and no structural delimiters so the size chunke",
            "r must perform deterministic hard splits when the content exceeds the default character budget used by the ingestion pipeline and this sentence keeps extending with operational language about checksums ordering idempotency retries observability and schema evolution to resemble realistic technical prose in production documentation where engineers write dense narratives without stopping for section markers and where downstream systems still need stable chunk boundaries for embedding generation and retrieval quality analysis across repeated ingest runs in continuous integration environments",
        ),
    ),
}


@pytest.mark.parametrize("fixture_name", sorted(_GOLDEN_EXPECTATIONS))
def test_golden_fixture_outputs_are_snapshot_pinned(fixture_name: str) -> None:
    expected = _GOLDEN_EXPECTATIONS[fixture_name]
    result = _ingest_fixture(fixture_name)

    assert len(result.documents) == 1
    document = result.documents[0]
    assert document.title == expected.title
    assert len(document.sections) == len(expected.section_headings)
    assert len(document.chunks) == len(expected.chunks)
    assert tuple(section.heading for section in document.sections) == expected.section_headings
    assert [section.order_index for section in document.sections] == list(
        range(len(document.sections))
    )
    assert [chunk.order_index for chunk in document.chunks] == list(range(len(document.chunks)))
    assert tuple(chunk.content_text for chunk in document.chunks) == expected.chunks


def test_golden_fixture_empty_file_current_behavior_is_pinned() -> None:
    result = _ingest_fixture("empty.md")

    assert len(result.documents) == 0
    assert result.processed_count == 0
    assert result.failed_count == 1
    assert len(result.failed_source_uris) == 1
    assert result.failed_source_uris[0] == "file:empty.md"
