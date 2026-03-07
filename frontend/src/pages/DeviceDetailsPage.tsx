import { useMemo } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from 'recharts';
import EmptyState from '@/components/EmptyState';
import ErrorState from '@/components/ErrorState';
import LoadingState from '@/components/LoadingState';
import ProofPanel from '@/components/ProofPanel';
import { getLatestShipmentProof } from '@/api/proofs';
import StatusBadge from '@/components/StatusBadge';
import { useDevice } from '@/hooks/useDevices';
import {
  useDeviceShipments,
  useShipmentOverview,
  useShipmentSensorStats,
  useShipmentTelemetry,
} from '@/hooks/useShipments';
import { sensorStatsFromBackend } from '@/utils/compliance';
import { getErrorMessage } from '@/utils/errors';
import { formatDate, formatDateTime } from '@/utils/format';

function DeviceDetailsPage() {
  const navigate = useNavigate();
  const { deviceId } = useParams<{ deviceId: string }>();
  const {
    data: device,
    isLoading: deviceLoading,
    isError: deviceError,
    error: deviceErrorObj,
    refetch: refetchDevice,
  } = useDevice(deviceId);
  const {
    data: shipments,
    isLoading: shipmentsLoading,
    isError: shipmentsError,
    error: shipmentsErrorObj,
    refetch: refetchShipments,
  } = useDeviceShipments(deviceId);
  const shipmentList = shipments ?? [];
  const primaryShipment = useMemo(() => {
    if (shipmentList.length === 0) {
      return null;
    }
    const inTransit = shipmentList.find((shipment) => shipment.status === 'in_transit');
    if (inTransit) {
      return inTransit;
    }
    return [...shipmentList].sort(
      (left, right) => new Date(right.created_at).getTime() - new Date(left.created_at).getTime(),
    )[0];
  }, [shipmentList]);
  const {
    data: telemetry,
    isLoading: telemetryLoading,
    isError: telemetryError,
    error: telemetryErrorObj,
    refetch: refetchTelemetry,
  } = useShipmentTelemetry(primaryShipment?.id, { limit: 200 });
  const { data: sensorStatsSnapshot } = useShipmentSensorStats(primaryShipment?.id);
  const { data: shipmentOverview } = useShipmentOverview(primaryShipment?.id);
  const {
    data: latestProof,
    isLoading: proofLoading,
    isError: proofError,
    error: proofErrorObj,
    refetch: refetchProof,
  } = useQuery({
    queryKey: ['proof', 'shipment-latest', primaryShipment?.id],
    queryFn: () => getLatestShipmentProof(primaryShipment?.id as string),
    enabled: Boolean(primaryShipment?.id),
    retry: 0,
    staleTime: 30_000,
    gcTime: 5 * 60_000,
  });

  const snapshotData = useMemo(
    () =>
      (telemetry ?? []).slice(-12).map((event) => ({
        label: formatDateTime(event.ts),
        timestamp: event.ts,
        temperature: event.temperature_c ?? 0,
        humidity: event.humidity_pct ?? 0,
        shock: event.shock_g ?? 0,
        tilt: event.tilt_deg ?? 0,
      })),
    [telemetry],
  );
  const latestPoint = snapshotData[snapshotData.length - 1];
  const sensorStats = sensorStatsSnapshot ? sensorStatsFromBackend(sensorStatsSnapshot, primaryShipment?.status) : null;

  if (!deviceId) {
    return <ErrorState message="Device ID is missing." />;
  }

  if (deviceLoading) {
    return <LoadingState message="Loading device details..." />;
  }

  if (deviceError) {
    const message =
      deviceErrorObj instanceof Error ? deviceErrorObj.message : 'Failed to load device.';
    return <ErrorState message={message} onRetry={() => void refetchDevice()} />;
  }

  if (!device) {
    return (
      <EmptyState
        title="Device not found"
        description="This device does not exist or you do not have access to it."
        action={
          <Link className="btn-secondary" to="/devices">
            Back to Devices
          </Link>
        }
      />
    );
  }

  return (
    <div className="space-y-6">
      <header className="space-y-3">
        <Link to="/devices" className="text-sm font-medium text-brand-300 transition hover:text-brand-400">
          &larr; Back to devices
        </Link>
        <section className="panel p-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Device Overview</p>
              <h1 className="mt-1 text-2xl font-semibold text-slate-100">{device.model}</h1>
              <p className="mt-1 text-sm uppercase tracking-[0.16em] text-slate-400">{device.device_uid}</p>
              <p className="mt-2 text-sm text-slate-300">
                Firmware: <span className="font-mono">{device.firmware_version}</span>
              </p>
            </div>
            <StatusBadge kind="device" status={device.status} />
          </div>

          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <article className="rounded-xl border border-white/10 bg-white/5 p-3">
              <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Battery Pack</p>
              <p className="mt-1 text-lg font-semibold text-slate-100">
                {device.battery_capacity_mAh === null ? 'Unknown' : `${device.battery_capacity_mAh} mAh`}
              </p>
            </article>
            <article className="rounded-xl border border-white/10 bg-white/5 p-3">
              <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Active Shipment</p>
              <p className="mt-1 text-lg font-semibold text-slate-100">
                {primaryShipment?.shipment_code ?? 'None'}
              </p>
            </article>
            <article className="rounded-xl border border-white/10 bg-white/5 p-3">
              <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Total Shipments</p>
              <p className="mt-1 text-lg font-semibold text-slate-100">{shipmentList.length}</p>
            </article>
            <article className="rounded-xl border border-white/10 bg-white/5 p-3">
              <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Created</p>
              <p className="mt-1 text-sm font-semibold text-slate-100">{formatDate(device.created_at)}</p>
            </article>
          </div>
        </section>
      </header>

      <section className="panel p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-slate-100">Canonical Telemetry Snapshot</h2>
            <p className="text-sm text-slate-400">
              Latest real telemetry from the most relevant linked shipment.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className="btn-secondary px-3 py-2 text-xs"
              onClick={() => primaryShipment && navigate(`/device-logs?shipment_id=${primaryShipment.id}`)}
              disabled={!primaryShipment}
            >
              View Full Logs
            </button>
            <button
              type="button"
              className="btn-secondary px-3 py-2 text-xs"
              onClick={() => navigate('/intelligence')}
            >
              View Intelligence
            </button>
          </div>
        </div>
        {!primaryShipment ? (
          <p className="mt-4 rounded-xl border border-slate-700 bg-surface-800/70 px-3 py-2 text-sm text-slate-400">
            This device has no linked shipments yet.
          </p>
        ) : telemetryLoading ? (
          <LoadingState message="Loading real telemetry snapshot..." />
        ) : telemetryError ? (
          <ErrorState
            message={getErrorMessage(telemetryErrorObj, 'Unable to load canonical telemetry for this device.')}
            onRetry={() => void refetchTelemetry()}
          />
        ) : telemetry && telemetry.length > 0 ? (
          <div className="mt-4 space-y-4">
            <div className="grid gap-3 text-sm text-slate-300 md:grid-cols-2 xl:grid-cols-4">
              <div className="rounded-xl border border-white/10 bg-white/5 p-3">
                <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Shipment</p>
                <p className="mt-2 font-semibold text-slate-100">{primaryShipment.shipment_code}</p>
              </div>
              <div className="rounded-xl border border-white/10 bg-white/5 p-3">
                <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Last Telemetry</p>
                <p className="mt-2 font-semibold text-slate-100">{formatDateTime(telemetry.at(-1)?.ts)}</p>
              </div>
              <div className="rounded-xl border border-white/10 bg-white/5 p-3">
                <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Bundle Status</p>
                <p className="mt-2 font-semibold text-slate-100">
                  {shipmentOverview?.latest_bundle?.status ?? 'No bundle'}
                </p>
              </div>
              <div className="rounded-xl border border-white/10 bg-white/5 p-3">
                <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Compliance</p>
                <p className="mt-2 font-semibold text-slate-100">
                  {sensorStats?.complianceStatus ?? 'Unknown'}
                </p>
              </div>
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              <article className="rounded-2xl border border-white/10 bg-slate-900/35 p-3">
                <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Temperature and Humidity</p>
                <div className="mt-3 h-44">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={snapshotData}>
                      <XAxis dataKey="label" tick={{ fill: '#94a3b8', fontSize: 11 }} tickLine={false} axisLine={false} />
                      <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} tickLine={false} axisLine={false} width={30} />
                      <RechartsTooltip
                        contentStyle={{
                          background: 'rgba(9, 16, 28, 0.95)',
                          border: '1px solid rgba(148,163,184,0.2)',
                          borderRadius: 12,
                        }}
                      />
                      <Line dataKey="temperature" type="monotone" stroke="#22d3ee" strokeWidth={2} dot={false} />
                      <Line dataKey="humidity" type="monotone" stroke="#60a5fa" strokeWidth={2} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
                {latestPoint && (
                  <p className="mt-2 text-xs text-slate-300">
                    Latest: {latestPoint.temperature.toFixed(1)} C | {latestPoint.humidity.toFixed(1)}%
                  </p>
                )}
              </article>

              <article className="rounded-2xl border border-white/10 bg-slate-900/35 p-3">
                <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Shock and Tilt</p>
                <div className="mt-3 h-44">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={snapshotData}>
                      <XAxis dataKey="label" tick={{ fill: '#94a3b8', fontSize: 11 }} tickLine={false} axisLine={false} />
                      <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} tickLine={false} axisLine={false} width={30} />
                      <RechartsTooltip
                        contentStyle={{
                          background: 'rgba(9, 16, 28, 0.95)',
                          border: '1px solid rgba(148,163,184,0.2)',
                          borderRadius: 12,
                        }}
                      />
                      <Line dataKey="shock" type="monotone" stroke="#f59e0b" strokeWidth={2} dot={false} />
                      <Line dataKey="tilt" type="monotone" stroke="#34d399" strokeWidth={2} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
                {latestPoint && (
                  <p className="mt-2 text-xs text-slate-300">
                    Latest: {latestPoint.shock.toFixed(2)} g | {latestPoint.tilt.toFixed(1)} deg
                  </p>
                )}
              </article>
            </div>
          </div>
        ) : (
          <p className="mt-4 rounded-xl border border-slate-700 bg-surface-800/70 px-3 py-2 text-sm text-slate-400">
            Linked shipment exists, but no canonical telemetry events are available yet.
          </p>
        )}
      </section>

      {primaryShipment && (
        proofLoading ? (
          <div className="panel p-5">
            <p className="text-sm text-slate-400">Loading latest proof...</p>
          </div>
        ) : proofError ? (
          <div className="panel p-5">
            <h2 className="mb-3 text-lg font-semibold text-slate-100">Latest Shipment Proof</h2>
            <p className="rounded-xl border border-slate-700 bg-surface-800/70 px-3 py-2 text-sm text-slate-400">
              {getErrorMessage(proofErrorObj, 'No latest proof is available for the active shipment.')}
            </p>
          </div>
        ) : latestProof ? (
          <ProofPanel proof={latestProof} onRefresh={() => void refetchProof()} isRefreshing={proofLoading} />
        ) : null
      )}

      <section className="space-y-4">
        <div>
          <h2 className="text-xl font-semibold text-slate-100">Linked Shipments</h2>
          <p className="text-sm text-slate-400">Open shipment journeys tracked by this device.</p>
        </div>

        {shipmentsLoading ? (
          <LoadingState message="Loading linked shipments..." />
        ) : shipmentsError ? (
          <ErrorState
            message={
              shipmentsErrorObj instanceof Error
                ? shipmentsErrorObj.message
                : 'Failed to load linked shipments.'
            }
            onRetry={() => void refetchShipments()}
          />
        ) : shipmentList.length === 0 ? (
          <EmptyState
            title="No shipments for this device"
            description="No shipment currently references this device."
          />
        ) : (
          <div className="grid gap-4">
            {shipmentList.map((shipment) => (
              <article key={shipment.id} className="panel animate-fade-up p-5">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Shipment Code</p>
                    <h3 className="mt-1 text-lg font-semibold text-slate-100">{shipment.shipment_code}</h3>
                    <p className="mt-2 text-sm text-slate-300">
                      {shipment.origin} {'->'} {shipment.destination}
                    </p>
                    <p className="text-xs text-slate-400">Created: {formatDate(shipment.created_at)}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <StatusBadge kind="shipment" status={shipment.status} />
                    <button
                      type="button"
                      className="btn-primary"
                      onClick={() => navigate(`/shipments/${shipment.id}`)}
                    >
                      Open
                    </button>
                  </div>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

export default DeviceDetailsPage;
