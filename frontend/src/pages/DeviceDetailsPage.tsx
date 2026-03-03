import { useMemo } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
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
import StatusBadge from '@/components/StatusBadge';
import { useDevice } from '@/hooks/useDevices';
import { useDeviceShipments } from '@/hooks/useShipments';
import { formatDate } from '@/utils/format';
import { buildDeviceIntelligence, buildDeviceOverview } from '@/utils/device-intelligence';

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

  const intelligence = useMemo(() => (device ? buildDeviceIntelligence(device) : null), [device]);
  const overview = useMemo(() => (device ? buildDeviceOverview(device) : null), [device]);
  const snapshotData = intelligence?.timeline?.slice(-12) ?? [];
  const latestPoint = snapshotData[snapshotData.length - 1];
  const shipmentList = shipments ?? [];

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

  if (!device || !overview || !intelligence) {
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
              <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Battery</p>
              <p className="mt-1 text-lg font-semibold text-slate-100">{overview.batteryPercent}%</p>
            </article>
            <article className="rounded-xl border border-white/10 bg-white/5 p-3">
              <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Signal</p>
              <p className="mt-1 text-lg font-semibold text-slate-100">{overview.signalPercent}%</p>
            </article>
            <article className="rounded-xl border border-white/10 bg-white/5 p-3">
              <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Risk</p>
              <p className="mt-1 text-lg font-semibold text-slate-100">{overview.riskLevel.toUpperCase()}</p>
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
            <h2 className="text-lg font-semibold text-slate-100">Quick Telemetry Snapshot</h2>
            <p className="text-sm text-slate-400">Compact telemetry summary for current operational checks.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className="btn-secondary px-3 py-2 text-xs"
              onClick={() => navigate(`/device-logs?device_id=${device.id}`)}
            >
              View Full Logs
            </button>
            <button
              type="button"
              className="btn-secondary px-3 py-2 text-xs"
              onClick={() => navigate(`/intelligence?device_id=${device.id}`)}
            >
              View Intelligence
            </button>
          </div>
        </div>

        <div className="mt-4 grid gap-4 lg:grid-cols-2">
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
      </section>

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
