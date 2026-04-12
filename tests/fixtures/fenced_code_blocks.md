# Fenced Code Blocks

This fixture mixes prose and fenced code so the chunker must preserve ordering while splitting oversized sections.

```python
records = [
    "line-001",
    "line-002",
    "line-003",
    "line-004",
    "line-005",
    "line-006",
    "line-007",
    "line-008",
    "line-009",
    "line-010",
    "line-011",
    "line-012",
    "line-013",
    "line-014",
    "line-015",
    "line-016",
    "line-017",
    "line-018",
    "line-019",
    "line-020",
    "line-021",
    "line-022",
    "line-023",
    "line-024",
    "line-025",
    "line-026",
    "line-027",
    "line-028",
    "line-029",
    "line-030",
    "line-031",
    "line-032",
    "line-033",
    "line-034",
    "line-035",
    "line-036",
    "line-037",
    "line-038",
    "line-039",
    "line-040",
    "line-041",
    "line-042",
    "line-043",
    "line-044",
    "line-045",
    "line-046",
    "line-047",
    "line-048",
    "line-049",
    "line-050",
    "line-051",
    "line-052",
    "line-053",
    "line-054",
    "line-055",
]

for entry in records:
    payload = {"entry": entry, "ok": True}
    print(payload)
```

The section above has a long fenced block that should cross the default max chunk size.

```json
{
  "service": "docprep",
  "pipeline": ["load", "parse", "chunk", "persist"],
  "owner": "docs-platform"
}
```

```bash
python -m docprep preview docs/
python -m docprep ingest docs/ --db sqlite:///docs.db
```
