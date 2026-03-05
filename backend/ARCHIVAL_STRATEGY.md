# TrustSeal Archival Strategy (Step 21)

This policy defines how telemetry pipeline data moves from hot operational storage to cold archive and eventual purge.

## Goals

- Keep dashboard and proof queries fast on hot datasets.
- Preserve audit evidence for compliance windows.
- Control storage growth and long-term costs.

## Retention Classes

1. Hot retention:
- Records newer than `ARCHIVE_HOT_RETENTION_DAYS` remain in operational Postgres for fast query.
- Default: `30` days.

2. Cold archive candidate:
- Records older than hot cutoff become candidates for offloading to low-cost archive storage.
- Recommended archive format: partitioned JSONL/Parquet by table + date.

3. Deep archive candidate:
- Records older than `ARCHIVE_COLD_RETENTION_DAYS`.
- Default: `365` days.
- Keep only proof-critical metadata in hot DB where possible.

4. Purge candidate:
- Records older than `ARCHIVE_PURGE_RETENTION_DAYS`.
- Default: `1095` days.
- Purge is disabled by default and must be explicitly enabled (`ARCHIVE_ENABLE_PURGE=true`).

## Tables Covered

- `telemetry_events`
- `custody_transfers`
- `telemetry_batches`
- `ipfs_objects`
- `chain_anchors`

## Non-Purge Invariant

Proof chain must remain reconstructable:
- Never delete `bundle_id -> ipfs_cid -> tx_hash` linkage unless an equivalent immutable archive index exists.

## Operational Endpoint

`GET /api/v1/ops/archival-plan` returns:
- active policy values
- computed UTC cutoffs
- candidate counts per table for cold/deep/purge tiers

Use this endpoint before enabling any purge operation.
