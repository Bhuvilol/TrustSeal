import { motion } from 'framer-motion';
import { BatteryMedium, Cpu, ShieldAlert, ShieldCheck, ShieldX } from 'lucide-react';
import type { Device } from '@/types';

interface DeviceCardProps {
  device: Device;
  onOpen: (id: string) => void;
  linkedShipmentCount?: number;
  onEdit?: (device: Device) => void;
  onDelete?: (device: Device) => void;
  deleting?: boolean;
}

function getStatusVisual(status: Device['status']) {
  if (status === 'active') {
    return {
      label: 'Active',
      dot: 'bg-emerald-300',
      badge: 'border-emerald-300/40 bg-emerald-400/15 text-emerald-100',
      edge: 'from-emerald-300/90 to-cyan-300/70',
      icon: ShieldCheck,
    };
  }

  if (status === 'maintenance') {
    return {
      label: 'Warning',
      dot: 'bg-amber-300',
      badge: 'border-amber-300/45 bg-amber-400/15 text-amber-100',
      edge: 'from-amber-300/90 to-orange-300/65',
      icon: ShieldAlert,
    };
  }

  return {
    label: 'Offline',
    dot: 'bg-slate-300',
    badge: 'border-slate-300/45 bg-slate-400/15 text-slate-200',
    edge: 'from-slate-400/80 to-slate-300/40',
    icon: ShieldX,
  };
}

function DeviceCard({
  device,
  onOpen,
  linkedShipmentCount = 0,
  onEdit,
  onDelete,
  deleting,
}: DeviceCardProps) {
  const statusVisual = getStatusVisual(device.status);
  const StatusIcon = statusVisual.icon;

  return (
    <motion.article
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -4 }}
      transition={{ duration: 0.22, ease: 'easeOut' }}
      className="relative overflow-hidden rounded-3xl border border-white/10 bg-[linear-gradient(140deg,rgba(20,39,61,0.9),rgba(14,26,43,0.9))] p-5 shadow-[0_22px_50px_rgba(0,0,0,0.35)] backdrop-blur-xl"
    >
      <div className={`absolute left-0 top-0 h-full w-[3px] bg-gradient-to-b ${statusVisual.edge}`} />
      <div className="pointer-events-none absolute -right-12 top-[-65px] h-40 w-40 rounded-full bg-cyan-300/10 blur-3xl" />

      <div className="relative flex items-start justify-between gap-3">
        <div>
          <h3 className="text-2xl font-semibold text-slate-100">{device.model}</h3>
          <p className="mt-1 text-xs uppercase tracking-[0.18em] text-slate-400">{device.device_uid}</p>
        </div>

        <span className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold ${statusVisual.badge}`}>
          <span className={`h-2 w-2 animate-pulse rounded-full ${statusVisual.dot}`} />
          {statusVisual.label}
        </span>
      </div>

      <div className="mt-4 grid gap-2 sm:grid-cols-3">
        <div className="rounded-xl border border-white/10 bg-white/5 px-3 py-2.5">
          <p className="text-[11px] uppercase tracking-[0.14em] text-slate-400">Battery Pack</p>
          <p className="mt-1 inline-flex items-center gap-1.5 text-base font-semibold text-slate-100">
            <BatteryMedium className="h-4 w-4 text-cyan-200" />
            {device.battery_capacity_mAh === null ? 'Unknown' : `${device.battery_capacity_mAh} mAh`}
          </p>
        </div>
        <div className="rounded-xl border border-white/10 bg-white/5 px-3 py-2.5">
          <p className="text-[11px] uppercase tracking-[0.14em] text-slate-400">Firmware</p>
          <p className="mt-1 inline-flex items-center gap-1.5 text-base font-semibold text-slate-100">
            <Cpu className="h-4 w-4 text-cyan-200" />
            {device.firmware_version}
          </p>
        </div>
        <div className="rounded-xl border border-white/10 bg-white/5 px-3 py-2.5">
          <p className="text-[11px] uppercase tracking-[0.14em] text-slate-400">Linked Shipments</p>
          <p className="mt-1 inline-flex items-center gap-1.5 text-base font-semibold text-slate-100">
            <StatusIcon className="h-4 w-4 text-cyan-200" />
            {linkedShipmentCount}
          </p>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <button type="button" className="btn-primary px-4 py-2 text-sm" onClick={() => onOpen(device.id)}>
          View Details
        </button>

        {onEdit && (
          <button type="button" className="btn-secondary px-3 py-2 text-xs" onClick={() => onEdit(device)}>
            Edit
          </button>
        )}

        {onDelete && (
          <button
            type="button"
            className="rounded-xl border border-red-300/45 bg-red-500/15 px-3 py-2 text-xs font-semibold text-red-100 transition hover:bg-red-500/25 disabled:cursor-not-allowed disabled:opacity-60"
            onClick={() => onDelete(device)}
            disabled={deleting}
          >
            {deleting ? 'Deleting...' : 'Delete'}
          </button>
        )}
      </div>
    </motion.article>
  );
}

export default DeviceCard;
