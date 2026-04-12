---
title: Frontmatter Heavy Fixture
author: Ada Lovelace
date: 2026-01-15
tags:
  - ingestion
  - markdown
  - regression
nested:
  product:
    name: docprep
    tier: enterprise
  owners:
    primary: docs-platform
    backups:
      - search-team
      - ml-platform
metadata:
  runbook: https://example.com/runbooks/docprep
  alert_window_minutes: 30
---

# Overview

This fixture validates that rich frontmatter survives normalization while heading-based sectioning still follows body structure.

The narrative includes enough prose to look like a real technical document.

## Data Model

`Document`, `Section`, and `Chunk` form a deterministic graph.

Stable IDs ensure downstream storage can perform upserts without semantic drift.

## Operational Notes

When a parser upgrade changes output shape, this fixture should fail loudly and force explicit review.
