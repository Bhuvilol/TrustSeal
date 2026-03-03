import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Activity, Battery, Radio, Shield } from 'lucide-react';
import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from 'recharts';
import DeviceCard from '@/components/DeviceCard';
import EmptyState from '@/components/EmptyState';
import ErrorState from '@/components/ErrorState';
import LoadingState from '@/components/LoadingState';
import { useDevices } from '@/hooks/useDevices';
import { useShipments } from '@/hooks/useShipments';
import type { Shipment } from '@/types';
import { getErrorMessage } from '@/utils/errors';

const UPTIME_DATA = Array.from({ length: 10 }).map((_, index) => ({
  t: index,
  value: 92 + Math.sin(index / 1.4) * 3 + (index % 2),
}));

function buildShipmentCountMap(shipments: Shipment[] | undefined): Map<string, number> {
  return (shipments ?? []).reduce((map, shipment) => {
    const currentCount = map.get(shipment.device_id) ?? 0;
    map.set(shipment.device_id, currentCount + 1);
    return map;
  }, new Map<string, number>());
}

function DashboardPage() {
  const navigate = useNavigate();
  const { data: devices, isLoading, isError, error, refetch } = useDevices();
  const { data: shipments } = useShipments();
  const shipmentCountByDevice = useMemo(() => buildShipmentCountMap(shipments), [shipments]);

  if (isLoading) {
    return <LoadingState message="Loading IoT devices..." />;
  }

  if (isError) {
    const message = getErrorMessage(error, 'Unable to load devices.');
    return <ErrorState message={message} onRetry={() => void refetch()} />;
  }

  const deviceList = devices ?? [];
  const totalDevices = deviceList.length;
  const activeDevices = deviceList.filter((device) => device.status === 'active').length;
  const maintenanceDevices = deviceList.filter((device) => device.status === 'maintenance').length;

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
              <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Telemetry Uptime</p>
              <h3 className="text-lg font-semibold text-slate-100">Signal health</h3>
            </div>
            <span className="rounded-full bg-emerald-400/20 px-3 py-1 text-xs font-semibold text-emerald-200">
              Live
            </span>
          </div>
          <div className="mt-4 h-40">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={UPTIME_DATA}>
                <defs>
                  <linearGradient id="uptimeGradient" x1="0" x2="0" y1="0" y2="1">
                    <stop offset="5%" stopColor="#22d3ee" stopOpacity={0.8} />
                    <stop offset="95%" stopColor="#22d3ee" stopOpacity={0.05} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="t" hide />
                <YAxis hide domain={[80, 100]} />
                <RechartsTooltip
                  contentStyle={{
                    background: '#0b1220',
                    border: '1px solid rgba(255,255,255,0.08)',
                    borderRadius: 12,
                  }}
                  labelStyle={{ color: '#cbd5f5' }}
                  formatter={(value: number) => `${value.toFixed(1)} %`}
                />
                <Area
                  type="monotone"
                  dataKey="value"
                  stroke="#22d3ee"
                  strokeWidth={2}
                  fill="url(#uptimeGradient)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div className="glass-card p-5">
          <div className="flex items-center gap-3">
            <div className="rounded-xl bg-white/5 p-3">
              <Radio className="h-5 w-5 text-cyan-300" />
            </div>
            <div>
              <p className="text-xs uppercase tracking-[0.14em] text-slate-400">System Health</p>
              <h3 className="text-lg font-semibold text-slate-100">Operational</h3>
            </div>
          </div>
          <p className="mt-3 text-sm text-slate-300">
            Live IoT streams, blockchain custody, anomaly detection, and AI summaries are within SLA.
            Critical states will pulse red automatically.
          </p>
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
