# Service Matrix

The tables below mimic compatibility grids used during migration planning.

## Core Services

| Service | Owner | SLA | Region | Notes |
| --- | --- | --- | --- | --- |
| ingest-api | docs | 99.9% | us-east-1 | Primary endpoint |
| parser-worker | docs | 99.5% | us-east-1 | Parse frontmatter |
| chunk-worker | search | 99.5% | us-east-1 | Split sections |
| vector-writer | ml | 99.0% | us-east-1 | Persist vectors |
| metadata-sync | platform | 99.9% | us-west-2 | Nightly cleanup |
| audit-export | compliance | 99.0% | eu-central-1 | Signed package |
| retry-queue | platform | 99.9% | us-east-1 | Retry orchestration |
| checksum-cache | platform | 99.5% | us-east-1 | Dedup support |
| docs-webhook | docs | 99.0% | ap-northeast-2 | CMS trigger |
| index-warmup | search | 98.0% | us-west-2 | Preload index |
| schema-registry | platform | 99.9% | us-east-1 | Contract checks |

## Supporting Services

| Service | Owner | SLA | Region | Notes |
| --- | --- | --- | --- | --- |
| batch-loader | docs | 99.0% | us-east-1 | Backfill ingest |
| stream-loader | docs | 99.0% | us-east-1 | Near realtime |
| pii-redactor | compliance | 99.9% | eu-west-1 | Data minimization |
| locale-detector | ml | 98.5% | ap-south-1 | Language hints |
| quality-scorer | ml | 98.5% | us-east-1 | Quality gate |
| retention-janitor | platform | 99.9% | us-west-2 | TTL cleanup |
| event-bridge | platform | 99.5% | us-east-1 | Event fan-out |
| status-dashboard | sre | 99.9% | global | Visibility |
| pager-router | sre | 99.9% | global | Incident routing |
| docs-validator | docs | 99.0% | us-east-1 | Lint markdown |
| release-notifier | docs | 99.0% | us-east-1 | Team updates |

Follow-up text ensures table parsing does not swallow trailing prose.
