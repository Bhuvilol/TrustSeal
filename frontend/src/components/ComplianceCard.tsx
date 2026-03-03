import type { SensorStats } from '@/utils/compliance';
import { TEMPERATURE_THRESHOLD_C } from '@/utils/constants';

interface ComplianceCardProps {
  stats: SensorStats;
}

function ComplianceCard({ stats }: ComplianceCardProps) {
  const compromised = stats.complianceStatus === 'Compromised';

  return (
    <article className="panel p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-slate-100">Compliance Status</h3>
          <p className="mt-1 text-sm text-slate-400">Threshold temperature: {TEMPERATURE_THRESHOLD_C} C</p>
        </div>
        <span
          className={`rounded-full border px-3 py-1 text-sm font-semibold ${
            compromised
              ? 'border-status-red/40 bg-status-red/20 text-status-red'
              : 'border-status-green/40 bg-status-green/20 text-status-green'
          }`}
        >
          {stats.complianceStatus}
        </span>
      </div>

      {stats.hasTemperatureBreach ? (
        <p className="mt-4 rounded-xl border border-status-red/35 bg-status-red/10 px-3 py-2 text-sm text-status-red">
          Temperature exceeded safe threshold.
        </p>
      ) : (
        <p className="mt-4 rounded-xl border border-status-green/35 bg-status-green/10 px-3 py-2 text-sm text-status-green">
          No temperature violation detected.
        </p>
      )}
    </article>
  );
}

export default ComplianceCard;

