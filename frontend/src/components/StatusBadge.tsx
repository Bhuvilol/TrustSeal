import clsx from 'clsx';
import type { DeviceStatus, LegStatus, ShipmentStatus } from '@/types';
import {
  getDeviceStatusClasses,
  getLegStatusClasses,
  getShipmentStatusClasses,
  getStatusLabel,
} from '@/utils/status';

type BadgeKind = 'shipment' | 'device' | 'leg';
type StatusValue = ShipmentStatus | DeviceStatus | LegStatus;

interface StatusBadgeProps {
  kind: BadgeKind;
  status: StatusValue;
}

function StatusBadge({ kind, status }: StatusBadgeProps) {
  const classes =
    kind === 'shipment'
      ? getShipmentStatusClasses(status as ShipmentStatus)
      : kind === 'device'
        ? getDeviceStatusClasses(status as DeviceStatus)
        : getLegStatusClasses(status as LegStatus);

  return (
    <span
      className={clsx(
        'status-badge inline-flex rounded-full border px-2.5 py-1 text-xs font-medium transition-all duration-300',
        classes,
      )}
    >
      {getStatusLabel(status)}
    </span>
  );
}

export default StatusBadge;
