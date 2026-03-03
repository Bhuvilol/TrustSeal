import type { SensorStats } from '@/utils/compliance';
import type { Shipment, ShipmentLeg } from '@/types';
import { formatDateTime, formatNumber } from '@/utils/format';

export function downloadShipmentReport(
  shipment: Shipment,
  stats: SensorStats,
  legCount: number,
  custodyCount: number,
): void {
  const lines = [
    `TrustSeal IoT Shipment Report`,
    `Generated At: ${new Date().toISOString()}`,
    '',
    `Shipment Code: ${shipment.shipment_code}`,
    `Status: ${shipment.status}`,
    `Origin: ${shipment.origin}`,
    `Destination: ${shipment.destination}`,
    `Created At: ${shipment.created_at}`,
    '',
    `Compliance: ${stats.complianceStatus}`,
    `Average Temperature: ${formatNumber(stats.averageTemperature)} C`,
    `Max Shock: ${formatNumber(stats.maxShock)} g`,
    `Last Sensor Update: ${formatDateTime(stats.lastUpdate)}`,
    '',
    `Journey Legs: ${legCount}`,
    `Custody Checkpoints: ${custodyCount}`,
  ];

  const blob = new Blob([lines.join('\n')], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = `shipment-${shipment.shipment_code}-report.txt`;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

export function buildJourneyPath(legs: ShipmentLeg[]): string {
  if (legs.length === 0) {
    return 'No legs recorded';
  }

  const first = legs[0];
  const last = legs[legs.length - 1];
  return `${first.from_location} -> ${last.to_location}`;
}

