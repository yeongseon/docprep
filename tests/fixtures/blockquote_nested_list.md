# Incident Review Notes

> Primary timeline summary:
>
> 1. Alert fired at 09:12 UTC.
> 2. On-call validated checksum mismatch symptoms.
>    - Scope was limited to one ingestion shard.
>    - Backfill jobs were paused to avoid duplicate writes.
>
> Additional context paragraph inside the same quote block. It captures rationale for delaying restarts until queue depth stabilized.

1. Immediate actions
   - Acknowledge alert in pager system.
   - Capture affected source URIs.

   This paragraph belongs to the same list item and explains why preserving paragraph continuity matters.

2. Recovery actions
   1. Restart parser workers.
   2. Re-run failed ingestion window.
   3. Confirm section and chunk counts align with baseline.

- Postmortem checklist
  - [x] Timeline drafted
  - [x] Stakeholders informed
  - [ ] Add invariant regression tests
