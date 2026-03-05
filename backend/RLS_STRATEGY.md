# TrustSeal Row-Level Access Control Strategy (Step 22)

This document defines the RLS strategy for Supabase/Postgres so each user can only query shipments they are authorized for.

## Model

- ACL table: `shipment_access`
  - `shipment_id`
  - `user_id`
  - `access_role` (`viewer`, `operator`, `auditor`, `owner`)
  - `granted_by`

`admin` and `authority` roles bypass ACL checks for operational oversight.

## Access Principle

User can read shipment-scoped data only if one of these is true:

1. JWT role is `admin` or `authority`.
2. User appears in `shipment_access` for that `shipment_id`.

## Shipment-Scoped Tables

RLS is applied on:

- `shipments`
- `shipment_legs`
- `sensor_logs`
- `custody_checkpoints`
- `telemetry_events`
- `telemetry_batches`
- `custody_transfers`
- `ipfs_objects`
- `chain_anchors`

## Policy SQL

See: `backend/sql/supabase_rls_policies.sql`

It includes:

- RLS enable statements
- helper functions:
  - `app.is_admin()`
  - `app.can_access_shipment(uuid)`
- select policies for all shipment-scoped tables
- write policies restricted to admin/authority paths

## Rollout Sequence

1. Apply migration creating `shipment_access`.
2. Backfill ACL rows for existing shipments.
3. Dry-run helper queries against sample users.
4. Apply RLS SQL in staging.
5. Validate dashboard read paths for:
   - authorized user (allowed)
   - unauthorized user (blocked)
   - admin (allowed)
6. Apply to production.

## Backend Runtime Note

Current backend uses direct DB credentials from server-side env.
RLS controls are most effective when requests are executed with user-bound JWT context (Supabase RPC/session) or when API enforces equivalent filters before DB query.
