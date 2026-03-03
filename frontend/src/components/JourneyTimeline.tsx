import type { ShipmentLeg } from '@/types';
import StatusBadge from '@/components/StatusBadge';
import { formatDateTime } from '@/utils/format';

interface JourneyTimelineProps {
  legs: ShipmentLeg[];
}

function JourneyTimeline({ legs }: JourneyTimelineProps) {
  const sortedLegs = [...legs].sort((left, right) => left.leg_number - right.leg_number);

  return (
    <section className="panel p-5">
      <div className="mb-5">
        <h3 className="text-lg font-semibold text-slate-100">Journey Timeline</h3>
        <p className="mt-1 text-sm text-slate-400">Factory -&gt; Port -&gt; Warehouse -&gt; Customer</p>
      </div>

      {sortedLegs.length === 0 ? (
        <p className="rounded-xl border border-slate-700 bg-surface-800/70 px-3 py-2 text-sm text-slate-400">
          No legs available for this shipment.
        </p>
      ) : (
        <ol className="space-y-4">
          {sortedLegs.map((leg, index) => (
            <li key={leg.id} className="relative pl-8">
              {index < sortedLegs.length - 1 && (
                <span className="absolute left-[7px] top-6 h-[calc(100%+0.5rem)] w-px bg-slate-600" />
              )}
              <span className="absolute left-0 top-1.5 h-4 w-4 rounded-full border border-brand-300 bg-brand-500/25" />

              <div className="rounded-xl border border-slate-700/70 bg-surface-800/60 p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-semibold text-slate-100">
                    Leg {leg.leg_number}: {leg.from_location} {'->'} {leg.to_location}
                  </p>
                  <StatusBadge kind="leg" status={leg.status} />
                </div>
                <div className="mt-3 grid gap-2 text-xs text-slate-400 md:grid-cols-2">
                  <p>Started: {formatDateTime(leg.started_at)}</p>
                  <p>Completed: {formatDateTime(leg.completed_at)}</p>
                </div>
              </div>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

export default JourneyTimeline;
