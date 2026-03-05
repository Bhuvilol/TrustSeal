-- TrustSeal Step 22: Supabase/Postgres RLS Policy Pack
-- Apply manually in Supabase SQL editor after validating in staging.

-- 1) Enable RLS
alter table if exists public.shipments enable row level security;
alter table if exists public.shipment_legs enable row level security;
alter table if exists public.sensor_logs enable row level security;
alter table if exists public.custody_checkpoints enable row level security;
alter table if exists public.telemetry_events enable row level security;
alter table if exists public.telemetry_batches enable row level security;
alter table if exists public.custody_transfers enable row level security;
alter table if exists public.ipfs_objects enable row level security;
alter table if exists public.chain_anchors enable row level security;
alter table if exists public.shipment_access enable row level security;

-- 2) Helper: admin check from JWT role claim
create schema if not exists app;

create or replace function app.is_admin()
returns boolean
language sql
stable
as $$
  select coalesce((auth.jwt() ->> 'role') in ('admin','authority'), false);
$$;

-- 3) Helper: shipment access check via ACL table
create or replace function app.can_access_shipment(_shipment_id uuid)
returns boolean
language sql
stable
as $$
  select
    app.is_admin()
    or exists (
      select 1
      from public.shipment_access sa
      where sa.shipment_id = _shipment_id
        and sa.user_id::text = auth.uid()::text
    );
$$;

-- 4) Policies: shipments + lineage tables
drop policy if exists shipments_select on public.shipments;
create policy shipments_select on public.shipments
for select
using (app.can_access_shipment(id));

drop policy if exists shipments_write on public.shipments;
create policy shipments_write on public.shipments
for all
using (app.is_admin())
with check (app.is_admin());

drop policy if exists shipment_legs_select on public.shipment_legs;
create policy shipment_legs_select on public.shipment_legs
for select
using (app.can_access_shipment(shipment_id));

drop policy if exists sensor_logs_select on public.sensor_logs;
create policy sensor_logs_select on public.sensor_logs
for select
using (app.can_access_shipment(shipment_id));

drop policy if exists custody_checkpoints_select on public.custody_checkpoints;
create policy custody_checkpoints_select on public.custody_checkpoints
for select
using (app.can_access_shipment(shipment_id));

drop policy if exists telemetry_events_select on public.telemetry_events;
create policy telemetry_events_select on public.telemetry_events
for select
using (app.can_access_shipment(shipment_id));

drop policy if exists telemetry_batches_select on public.telemetry_batches;
create policy telemetry_batches_select on public.telemetry_batches
for select
using (app.can_access_shipment(shipment_id));

drop policy if exists custody_transfers_select on public.custody_transfers;
create policy custody_transfers_select on public.custody_transfers
for select
using (app.can_access_shipment(shipment_id));

drop policy if exists ipfs_objects_select on public.ipfs_objects;
create policy ipfs_objects_select on public.ipfs_objects
for select
using (app.can_access_shipment(shipment_id));

drop policy if exists chain_anchors_select on public.chain_anchors;
create policy chain_anchors_select on public.chain_anchors
for select
using (app.can_access_shipment(shipment_id));

-- 5) ACL table policies
drop policy if exists shipment_access_select on public.shipment_access;
create policy shipment_access_select on public.shipment_access
for select
using (app.is_admin() or user_id::text = auth.uid()::text);

drop policy if exists shipment_access_write on public.shipment_access;
create policy shipment_access_write on public.shipment_access
for all
using (app.is_admin())
with check (app.is_admin());

