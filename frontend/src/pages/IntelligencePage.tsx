import { useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { AlertTriangle, BrainCircuit, ShieldAlert, ShieldCheck, ShieldX } from 'lucide-react';
import EmptyState from '@/components/EmptyState';
import ErrorState from '@/components/ErrorState';
import LoadingState from '@/components/LoadingState';
import { useDevices } from '@/hooks/useDevices';
import { buildDeviceIntelligence } from '@/utils/device-intelligence';
import { getErrorMessage } from '@/utils/errors';

function IntelligencePage() {
  const [searchParams] = useSearchParams();
  const focusedDeviceId = searchParams.get('device_id');
  const { data: devices, isLoading, isError, error, refetch } = useDevices();

  const intelligenceRows = useMemo(
    () =>
      (devices ?? []).map((device) => ({
        device,
        snapshot: buildDeviceIntelligence(device),
      })),
    [devices],
  );

  const riskSummary = useMemo(
    () => ({
      high: intelligenceRows.filter((row) => row.snapshot.riskLevel === 'high').length,
      medium: intelligenceRows.filter((row) => row.snapshot.riskLevel === 'medium').length,
      low: intelligenceRows.filter((row) => row.snapshot.riskLevel === 'low').length,
      anomalies: intelligenceRows.reduce(
        (count, row) => count + row.snapshot.logs.filter((log) => log.severity !== 'info').length,
        0,
      ),
    }),
    [intelligenceRows],
  );

  const riskChartData = useMemo(
    () =>
      intelligenceRows.map((row) => ({
        device: row.device.device_uid,
        health: row.snapshot.healthScore,
        anomalies: row.snapshot.logs.filter((log) => log.severity !== 'info').length,
      })),
    [intelligenceRows],
  );

  const systemTrendData = useMemo(() => {
    if (intelligenceRows.length === 0) {
      return [];
    }

    const points = intelligenceRows[0].snapshot.timeline.map((point, index) => {
      const healthAverage =
        intelligenceRows.reduce((total, row) => {
          const rowPoint = row.snapshot.timeline[index];
          const tempPenalty = rowPoint.temperature > 8 ? 8 : rowPoint.temperature > 7.4 ? 3 : 0;
          const shockPenalty = rowPoint.shock > 2.2 ? 12 : rowPoint.shock > 1.5 ? 5 : 0;
          const humidityPenalty = rowPoint.humidity > 75 ? 6 : rowPoint.humidity > 65 ? 2 : 0;
          return total + Math.max(30, 96 - tempPenalty - shockPenalty - humidityPenalty);
        }, 0) / intelligenceRows.length;

      return {
        t: point.label,
        health: Number(healthAverage.toFixed(1)),
      };
    });

    return points.slice(-14);
  }, [intelligenceRows]);

  const recentAnomalies = useMemo(
    () =>
      intelligenceRows
        .flatMap((row) =>
          row.snapshot.logs
            .filter((log) => log.severity !== 'info')
            .map((log) => ({
              ...log,
              deviceName: row.device.model,
              deviceUid: row.device.device_uid,
              risk: row.snapshot.riskLevel,
            })),
        )
        .sort((left, right) => right.timestamp.localeCompare(left.timestamp))
        .slice(0, 12),
    [intelligenceRows],
  );

  if (isLoading) {
    return <LoadingState message="Loading intelligence layer..." />;
  }

  if (isError) {
    return (
      <ErrorState
        message={getErrorMessage(error, 'Unable to load intelligence metrics.')}
        onRetry={() => void refetch()}
      />
    );
  }

  if (!devices || devices.length === 0) {
    return (
      <EmptyState
        title="No devices for intelligence analysis"
        description="Add devices to begin AI-driven risk monitoring."
      />
    );
  }

  return (
    <div className="space-y-6">
      <section className="panel p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold text-slate-100">Intelligence</h1>
            <p className="mt-1 text-sm text-slate-400">
              AI summary, anomaly distribution and predictive risk view across the full device fleet.
            </p>
          </div>
          <span className="inline-flex items-center gap-2 rounded-full border border-cyan-300/40 bg-cyan-400/15 px-3 py-1 text-xs font-semibold text-cyan-100">
            <BrainCircuit className="h-4 w-4" />
            Analytics Layer
          </span>
        </div>

        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <article className="rounded-2xl border border-red-300/35 bg-red-500/10 p-3">
            <p className="text-xs uppercase tracking-[0.14em] text-red-100/80">High Risk Devices</p>
            <p className="mt-2 text-2xl font-semibold text-red-100">{riskSummary.high}</p>
          </article>
          <article className="rounded-2xl border border-amber-300/35 bg-amber-500/10 p-3">
            <p className="text-xs uppercase tracking-[0.14em] text-amber-100/80">Medium Risk</p>
            <p className="mt-2 text-2xl font-semibold text-amber-100">{riskSummary.medium}</p>
          </article>
          <article className="rounded-2xl border border-emerald-300/35 bg-emerald-500/10 p-3">
            <p className="text-xs uppercase tracking-[0.14em] text-emerald-100/80">Low Risk</p>
            <p className="mt-2 text-2xl font-semibold text-emerald-100">{riskSummary.low}</p>
          </article>
          <article className="rounded-2xl border border-cyan-300/35 bg-cyan-500/10 p-3">
            <p className="text-xs uppercase tracking-[0.14em] text-cyan-100/80">Recent Anomalies</p>
            <p className="mt-2 text-2xl font-semibold text-cyan-100">{riskSummary.anomalies}</p>
          </article>
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.3fr_1fr]">
        <article className="panel p-4">
          <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Risk Distribution by Device</p>
          <div className="mt-3 h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={riskChartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.12)" />
                <XAxis dataKey="device" tick={{ fill: '#94a3b8', fontSize: 11 }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} tickLine={false} axisLine={false} width={30} />
                <RechartsTooltip
                  contentStyle={{
                    background: 'rgba(9, 16, 28, 0.95)',
                    border: '1px solid rgba(148,163,184,0.2)',
                    borderRadius: 12,
                  }}
                />
                <Bar dataKey="health" fill="#22d3ee" radius={[8, 8, 0, 0]} name="Health %" />
                <Bar dataKey="anomalies" fill="#f59e0b" radius={[8, 8, 0, 0]} name="Anomalies" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </article>

        <article className="panel p-4">
          <p className="text-xs uppercase tracking-[0.14em] text-slate-400">System Health Trend</p>
          <div className="mt-3 h-72">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={systemTrendData}>
                <XAxis dataKey="t" tick={{ fill: '#94a3b8', fontSize: 11 }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} tickLine={false} axisLine={false} width={30} />
                <RechartsTooltip
                  contentStyle={{
                    background: 'rgba(9, 16, 28, 0.95)',
                    border: '1px solid rgba(148,163,184,0.2)',
                    borderRadius: 12,
                  }}
                />
                <Line type="monotone" dataKey="health" stroke="#34d399" strokeWidth={2.5} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </article>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-slate-100">Risk Summary per Device</h2>
        <div className="grid gap-4 xl:grid-cols-2">
          {intelligenceRows.map((row) => {
            const isFocused = focusedDeviceId === row.device.id;
            const anomalies = row.snapshot.logs.filter((log) => log.severity !== 'info').length;

            return (
              <motion.article
                key={row.device.id}
                whileHover={{ y: -3 }}
                className={`rounded-2xl border p-4 transition ${
                  isFocused
                    ? 'border-cyan-300/55 bg-cyan-500/10 shadow-[0_0_24px_rgba(34,211,238,0.18)]'
                    : 'border-white/10 bg-slate-900/35'
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-base font-semibold text-slate-100">{row.device.model}</p>
                    <p className="text-xs uppercase tracking-[0.14em] text-slate-400">{row.device.device_uid}</p>
                  </div>
                  <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-semibold uppercase tracking-[0.1em] ${
                    row.snapshot.riskLevel === 'high'
                      ? 'border-red-300/45 bg-red-500/15 text-red-100'
                      : row.snapshot.riskLevel === 'medium'
                        ? 'border-amber-300/45 bg-amber-500/15 text-amber-100'
                        : 'border-emerald-300/45 bg-emerald-500/15 text-emerald-100'
                  }`}>
                    {row.snapshot.riskLevel === 'high' ? (
                      <ShieldX className="h-3.5 w-3.5" />
                    ) : row.snapshot.riskLevel === 'medium' ? (
                      <ShieldAlert className="h-3.5 w-3.5" />
                    ) : (
                      <ShieldCheck className="h-3.5 w-3.5" />
                    )}
                    {row.snapshot.riskLevel}
                  </span>
                </div>

                <div className="mt-3 grid gap-2 text-sm text-slate-300 sm:grid-cols-3">
                  <div className="rounded-xl border border-white/10 bg-white/5 p-2">
                    <p className="text-[11px] uppercase tracking-[0.12em] text-slate-400">Health</p>
                    <p className="mt-1 font-semibold text-slate-100">{row.snapshot.healthScore}%</p>
                  </div>
                  <div className="rounded-xl border border-white/10 bg-white/5 p-2">
                    <p className="text-[11px] uppercase tracking-[0.12em] text-slate-400">Anomalies</p>
                    <p className="mt-1 font-semibold text-slate-100">{anomalies}</p>
                  </div>
                  <div className="rounded-xl border border-white/10 bg-white/5 p-2">
                    <p className="text-[11px] uppercase tracking-[0.12em] text-slate-400">Predictive Alert</p>
                    <p className="mt-1 font-semibold text-slate-100">
                      {row.snapshot.riskLevel === 'high' ? 'Action Required' : row.snapshot.riskLevel === 'medium' ? 'Monitor Closely' : 'Stable'}
                    </p>
                  </div>
                </div>
              </motion.article>
            );
          })}
        </div>
      </section>

      <section className="panel p-4">
        <h2 className="text-lg font-semibold text-slate-100">Recent Anomalies</h2>
        {recentAnomalies.length === 0 ? (
          <p className="mt-2 text-sm text-slate-400">No recent anomaly events detected.</p>
        ) : (
          <div className="mt-3 max-h-[360px] space-y-2 overflow-y-auto pr-1">
            {recentAnomalies.map((item) => (
              <article key={item.id} className="rounded-xl border border-white/10 bg-slate-900/35 p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-semibold text-slate-100">{item.type}</p>
                  <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-semibold uppercase tracking-[0.1em] ${
                    item.severity === 'critical'
                      ? 'border-red-300/45 bg-red-500/15 text-red-100'
                      : 'border-amber-300/45 bg-amber-500/15 text-amber-100'
                  }`}>
                    <AlertTriangle className="h-3 w-3" />
                    {item.severity}
                  </span>
                </div>
                <p className="mt-1 text-xs text-slate-300">{item.deviceName} ({item.deviceUid})</p>
                <p className="mt-1 text-sm text-slate-300">{item.description}</p>
                <p className="mt-1 text-xs text-slate-400">{new Date(item.timestamp).toLocaleString()}</p>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

export default IntelligencePage;
