import type { DeviceStatus, LegStatus, ShipmentStatus } from '@/types';
import { toTitleCase } from '@/utils/format';

const shipmentStatusClasses: Record<ShipmentStatus, string> = {
  created: 'bg-status-gray/20 text-status-gray border-status-gray/40',
  in_transit: 'bg-status-blue/20 text-status-blue border-status-blue/40',
  docking: 'bg-status-yellow/20 text-status-yellow border-status-yellow/40',
  completed: 'bg-status-green/20 text-status-green border-status-green/40',
  compromised: 'bg-status-red/20 text-status-red border-status-red/40',
};

const deviceStatusClasses: Record<DeviceStatus, string> = {
  active: 'bg-status-green/20 text-status-green border-status-green/40',
  inactive: 'bg-status-gray/20 text-status-gray border-status-gray/40',
  maintenance: 'bg-status-yellow/20 text-status-yellow border-status-yellow/40',
};

const legStatusClasses: Record<LegStatus, string> = {
  pending: 'bg-status-gray/20 text-status-gray border-status-gray/40',
  in_progress: 'bg-status-blue/20 text-status-blue border-status-blue/40',
  settled: 'bg-status-green/20 text-status-green border-status-green/40',
};

export function getShipmentStatusClasses(status: ShipmentStatus): string {
  return shipmentStatusClasses[status];
}

export function getDeviceStatusClasses(status: DeviceStatus): string {
  return deviceStatusClasses[status];
}

export function getLegStatusClasses(status: LegStatus): string {
  return legStatusClasses[status];
}

export function getStatusLabel(value: string): string {
  if (value === 'factory') {
    return 'Manufacturer';
  }
  return toTitleCase(value);
}
