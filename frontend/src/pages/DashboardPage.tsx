import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import { Activity, Battery, Database, Shield } from 'lucide-react';
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from 'recharts';
import DeviceCard from '@/components/DeviceCard';
import EmptyState from '@/components/EmptyState';
import ErrorState from '@/components/ErrorState';
import LoadingState from '@/components/LoadingState';
import { getSystemHealth } from '@/api/ops';
import { useDevices } from '@/hooks/useDevices';
import { useShipments } from '@/hooks/useShipments';
import type { HealthResponse, Shipment } from '@/types';
import { getErrorMessage } from '@/utils/errors';

function buildShipmentCountMap(shipments: Shipment[] | undefined): Map<string, number> {
  return (shipments ?? []).reduce((map, shipment) => {
    const currentCount = map.get(shipment.device_id) ?? 0;
    map.set(shipment.device_id, currentCount + 1);
    return map;
  }, new Map<string, number>());
}

function startOfDayIso(daysAgo: number): string {
  const date = new Date();
  date.setHours(0, 0, 0, 0);
  date.setDate(date.getDate() - daysAgo);
  return date.toISOString();
}

function buildCoverageData(devices: { id: string; status: string; created_at: string }[], shipments: Shipment[] | undefined) {
  const shipmentSetByDevice = buildShipmentCountMap(shipments);
  return Array.from({ length: 7 }).map((_, index) => {
    const daysAgo = 6 - index;
    const cutoff = startOfDayIso(daysAgo);
    const eligible = devices.filter((device) => device.created_at <= cutoff);
    const active = eligible.filter((device) => device.status === 'active').length;
    const attached = eligible.filter((device) => (shipmentSetByDevice.get(device.id) ?? 0) > 0).length;
    const total = eligible.length;
    const activeCoverage = total > 0 ? Number(((active / total) * 100).toFixed(1)) : 0;
    const shipmentCoverage = total > 0 ? Number(((attached / total) * 100).toFixed(1)) : 0;
    return {
      label: new Date(cutoff).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
      activeCoverage,
      shipmentCoverage,
    };
  });
}

function summarizeSystemHealth(health: HealthResponse | undefined) {
  if (!health) {
    return {
      label: 'Unavailable',
      tone: 'text-slate-300',
      detail: 'Health status not loaded yet.',
      items: [] as Array<{ label: string; status: string }>,
    };
  }

  const services = [
    ['Postgres', health.services.postgres.status],
    ['Redis', health.services.redis.status],
    ['Workers', health.services.workers.status],
    ['IPFS', health.services.ipfs.status],
    ['Polygon', health.services.polygon.status],
  ] as const;

  const degraded = services.filter(([, status]) => status !== 'ok' && status !== 'disabled');
  return {
    label: health.status === 'ok' ? 'Healthy' : 'Degraded',
    tone: health.status === 'ok' ? 'text-emerald-300' : 'text-amber-200',
    detail:
      degraded.length === 0
        ? 'All critical backend services are responding normally.'
        : `${degraded.map(([label, status]) => `${label}: ${status}`).join(' | ')}`,
    items: services.map(([label, status]) => ({ label, status })),
  };
}

function DashboardPage() {
  const navigate = useNavigate();
  const { data: devices, isLoading, isError, error, refetch } = useDevices();
  const { data: shipments } = useShipments();
  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: getSystemHealth,
    staleTime: 15_000,
    refetchInterval: 30_000,
    retry: 1,
  });
  const shipmentCountByDevice = useMemo(() => buildShipmentCountMap(shipments), [shipments]);
  const deviceList = devices ?? [];
  const totalDevices = deviceList.length;
  const activeDevices = deviceList.filter((device) => device.status === 'active').length;
  const maintenanceDevices = deviceList.filter((device) => device.status === 'maintenance').length;
  const coverageData = useMemo(() => buildCoverageData(deviceList, shipments), [deviceList, shipments]);
  const healthSummary = summarizeSystemHealth(health);

  if (isLoading) {
    return <LoadingState message="Loading IoT devices..." />;
  }

  if (isError) {
    const message = getErrorMessage(error, 'Unable to load devices.');
    return <ErrorState message={message} onRetry={() => void refetch()} />;
  }

  return (
    <div className="space-y-6">
      <section className="grid gap-4 md:grid-cols-3">
        <article className="glass-card glow-border p-4">
          <div className="flex items-center justify-between">
            <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Total Devices</p>
            <Shield className="h-4 w-4 text-cyan-300" />
          </div>
          <p className="mt-2 text-3xl font-semibold text-slate-100">{totalDevices}</p>
          <p className="text-xs text-slate-500">Across all fleets</p>
        </article>
        <article className="glass-card glow-border p-4">
          <div className="flex items-center justify-between">
            <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Active</p>
            <Activity className="h-4 w-4 text-emerald-300" />
          </div>
          <p className="mt-2 text-3xl font-semibold text-emerald-300">{activeDevices}</p>
          <p className="text-xs text-slate-500">Reporting within SLA</p>
        </article>
        <article className="glass-card glow-border p-4">
          <div className="flex items-center justify-between">
            <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Maintenance</p>
            <Battery className="h-4 w-4 text-amber-300" />
          </div>
          <p className="mt-2 text-3xl font-semibold text-amber-200">{maintenanceDevices}</p>
          <p className="text-xs text-slate-500">Awaiting service</p>
        </article>
      </section>

      <section className="grid gap-4 lg:grid-cols-[2fr_1fr]">
        <div className="glass-card p-5">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Fleet Coverage</p>
              <h3 className="text-lg font-semibold text-slate-100">Active and shipment-linked devices</h3>
            </div>
            <span className="rounded-full bg-cyan-400/20 px-3 py-1 text-xs font-semibold text-cyan-200">
              Real Data
            </span>
          </div>
          <div className="mt-4 h-40">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={coverageData}>
                <defs>
                  <linearGradient id="activeCoverageGradient" x1="0" x2="0" y1="0" y2="1">
                    <stop offset="5%" stopColor="#22d3ee" stopOpacity={0.8} />
                    <stop offset="95%" stopColor="#22d3ee" stopOpacity={0.05} />
                  </linearGradient>
                  <linearGradient id="shipmentCoverageGradient" x1="0" x2="0" y1="0" y2="1">
                    <stop offset="5%" stopColor="#34d399" stopOpacity={0.7} />
                    <stop offset="95%" stopColor="#34d399" stopOpacity={0.05} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="rgba(148,163,184,0.12)" vertical={false} />
                <XAxis dataKey="label" tick={{ fill: '#94a3b8', fontSize: 11 }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} tickLine={false} axisLine={false} domain={[0, 100]} />
                <RechartsTooltip
                  contentStyle={{
                    background: '#0b1220',
                    border: '1px solid rgba(255,255,255,0.08)',
                    borderRadius: 12,
                  }}
                  labelStyle={{ color: '#cbd5f5' }}
                  formatter={(value: number, name: string) => [`${value.toFixed(1)} %`, name]}
                />
                <Area
                  type="monotone"
                  dataKey="activeCoverage"
                  name="Active devices"
                  stroke="#22d3ee"
                  strokeWidth={2}
                  fill="url(#activeCoverageGradient)"
                />
                <Area
                  type="monotone"
                  dataKey="shipmentCoverage"
                  name="Shipment-linked devices"
                  stroke="#34d399"
                  strokeWidth={2}
                  fill="url(#shipmentCoverageGradient)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <p className="mt-3 text-sm text-slate-300">
            Derived from real device inventory and shipment assignments over the last 7 days.
          </p>
        </div>
        <div className="glass-card p-5">
          <div className="flex items-center gap-3">
            <div className="rounded-xl bg-white/5 p-3">
              <Database className="h-5 w-5 text-cyan-300" />
            </div>
            <div>
              <p className="text-xs uppercase tracking-[0.14em] text-slate-400">System Health</p>
              <h3 className={`text-lg font-semibold ${healthSummary.tone}`}>{healthSummary.label}</h3>
            </div>
          </div>
          <p className="mt-3 text-sm text-slate-300">{healthSummary.detail}</p>
          <div className="mt-4 space-y-2 text-xs text-slate-300">
            {healthSummary.items.map((item) => (
              <div key={item.label} className="flex items-center justify-between rounded-lg border border-white/10 bg-white/5 px-3 py-2">
                <span>{item.label}</span>
                <span className={item.status === 'ok' ? 'text-emerald-300' : item.status === 'disabled' ? 'text-slate-400' : 'text-amber-200'}>
                  {item.status}
                </span>
              </div>
            ))}
          </div>
          {health?.services.polygon.latest_block ? (
            <p className="mt-3 text-xs text-slate-400">
              Polygon latest block: {health.services.polygon.latest_block.toLocaleString()}
            </p>
          ) : null}
        </div>
      </section>

      <section className="space-y-4">
        <div>
          <h2 className="text-xl font-semibold text-slate-100">Device Fleet</h2>
          <p className="text-sm text-slate-400">Overview cards for operational visibility across your device fleet.</p>
        </div>

        {totalDevices === 0 ? (
          <EmptyState
            title="No devices found"
            description="No registered IoT devices are available for your account yet."
          />
        ) : (
          <motion.div
            initial="hidden"
            animate="visible"
            variants={{
              hidden: { opacity: 0 },
              visible: {
                opacity: 1,
                transition: { staggerChildren: 0.06 },
              },
            }}
            className="grid gap-4 xl:grid-cols-2"
          >
            {deviceList.map((device) => (
              <motion.div key={device.id} variants={{ hidden: { opacity: 0, y: 10 }, visible: { opacity: 1, y: 0 } }}>
                <DeviceCard
                  device={device}
                  linkedShipmentCount={shipmentCountByDevice.get(device.id) ?? 0}
                  onOpen={(id) => navigate(`/devices/${id}`)}
                />
              </motion.div>
            ))}
          </motion.div>
        )}
      </section>
    </div>
  );
}

export default DashboardPage;
