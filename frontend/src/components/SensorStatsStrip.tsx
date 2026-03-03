import type { SensorStats } from '@/utils/compliance';
import { formatDateTime, formatNumber } from '@/utils/format';

interface SensorStatsStripProps {
  stats: SensorStats;
}

function SensorStatsStrip({ stats }: SensorStatsStripProps) {
  return (
    <section className="grid gap-4 md:grid-cols-3 xl:grid-cols-5">
      <article className="panel-soft p-4">
        <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Last Sensor Update</p>
        <p className="mt-2 text-lg font-semibold text-slate-100">{formatDateTime(stats.lastUpdate)}</p>
      </article>
      <article className="panel-soft p-4">
        <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Average Temperature</p>
        <p className="mt-2 text-lg font-semibold text-slate-100">{formatNumber(stats.averageTemperature)} C</p>
      </article>
      <article className="panel-soft p-4">
        <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Min Temperature</p>
        <p className="mt-2 text-lg font-semibold text-slate-100">{formatNumber(stats.minTemperature)} C</p>
      </article>
      <article className="panel-soft p-4">
        <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Max Temperature</p>
        <p className="mt-2 text-lg font-semibold text-slate-100">{formatNumber(stats.maxTemperature)} C</p>
      </article>
      <article className="panel-soft p-4">
        <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Max Shock</p>
        <p className="mt-2 text-lg font-semibold text-slate-100">{formatNumber(stats.maxShock)} g</p>
      </article>
    </section>
  );
}

export default SensorStatsStrip;
