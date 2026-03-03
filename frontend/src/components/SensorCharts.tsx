import { useMemo } from 'react';
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { SensorLog } from '@/types';
import { sortLogsByRecordedAt } from '@/utils/compliance';

interface SensorChartsProps {
  logs: SensorLog[];
}

interface ChartDataPoint {
  timestamp: string;
  label: string;
  temperature: number | null;
  humidity: number | null;
  shock: number | null;
  tilt: number | null;
}

interface GraphPanelProps {
  title: string;
  dataKey: keyof Omit<ChartDataPoint, 'timestamp' | 'label'>;
  color: string;
  unit: string;
  data: ChartDataPoint[];
}

function GraphPanel({ title, dataKey, color, unit, data }: GraphPanelProps) {
  return (
    <article className="panel-soft p-4">
      <div className="mb-3 flex items-center justify-between">
        <h4 className="text-sm font-semibold text-slate-100">{title}</h4>
        <span className="text-xs text-slate-400">{unit}</span>
      </div>
      <div className="h-56 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
            <XAxis dataKey="label" stroke="#94a3b8" fontSize={11} tickLine={false} />
            <YAxis stroke="#94a3b8" fontSize={11} tickLine={false} width={45} />
            <Tooltip
              contentStyle={{
                backgroundColor: '#0f1d2a',
                border: '1px solid #334155',
                borderRadius: '0.75rem',
                color: '#f8fafc',
              }}
              labelStyle={{ color: '#cbd5e1' }}
            />
            <Line
              type="monotone"
              dataKey={dataKey}
              stroke={color}
              strokeWidth={2.4}
              dot={false}
              isAnimationActive
              animationDuration={750}
              connectNulls
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </article>
  );
}

function SensorCharts({ logs }: SensorChartsProps) {
  const data = useMemo<ChartDataPoint[]>(() => {
    return sortLogsByRecordedAt(logs).map((entry) => {
      const parsed = new Date(entry.recorded_at);
      const label = Number.isNaN(parsed.getTime())
        ? 'Invalid'
        : parsed.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

      return {
        timestamp: entry.recorded_at,
        label,
        temperature: entry.temperature,
        humidity: entry.humidity,
        shock: entry.shock,
        tilt: entry.tilt_angle,
      };
    });
  }, [logs]);

  if (data.length === 0) {
    return (
      <div className="panel p-5">
        <h3 className="text-lg font-semibold text-slate-100">Sensor Graphs</h3>
        <p className="mt-3 rounded-xl border border-slate-700 bg-surface-800/70 px-3 py-2 text-sm text-slate-400">
          No sensor logs available yet.
        </p>
      </div>
    );
  }

  return (
    <section className="panel p-5">
      <div className="mb-5">
        <h3 className="text-lg font-semibold text-slate-100">Sensor Graphs</h3>
        <p className="mt-1 text-sm text-slate-400">Temperature, humidity, shock, and tilt over time.</p>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <GraphPanel title="Temperature" dataKey="temperature" color="#f97316" unit="C" data={data} />
        <GraphPanel title="Humidity" dataKey="humidity" color="#38bdf8" unit="%" data={data} />
        <GraphPanel title="Shock" dataKey="shock" color="#f43f5e" unit="g" data={data} />
        <GraphPanel title="Tilt" dataKey="tilt" color="#facc15" unit="deg" data={data} />
      </div>
    </section>
  );
}

export default SensorCharts;

