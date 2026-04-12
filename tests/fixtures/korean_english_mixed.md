# 문서 수집 파이프라인 개요

이 문서는 Markdown ingestion pipeline의 동작을 설명합니다. 섹션 분할은 heading 기반으로 동작하고, chunking은 max_chars 제한을 따릅니다.

## 처리 단계 Processing Stages

로드(load) -> 파싱(parse) -> 청킹(chunk) -> 저장(persist) 순서로 실행됩니다.

```python
from docprep import ingest

result = ingest("docs/")
print(result.processed_count)
```

## 품질 확인 Quality Checks

UUID determinism, content coverage, 그리고 ordering invariants를 함께 검증해야 운영 중 회귀를 빨리 탐지할 수 있습니다.
